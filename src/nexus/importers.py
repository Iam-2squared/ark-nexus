"""Safe input staging and synthetic adapter contracts; NOT live vendor adapters."""

import hashlib
import io
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_ZIP_FILES = 200
MAX_MESSAGES = 50000
PARSER_VERSION = "synthetic-fixture-1"


class ImportProblem(ValueError):
    pass


@dataclass(frozen=True)
class Message:
    external_id: str
    role: str
    content: str
    occurred_at: str | None
    content_sha256: str


@dataclass(frozen=True)
class Conversation:
    external_id: str
    title: str
    messages: list[Message]


def safe_json_payload(blob: bytes, filename: str) -> bytes:
    if len(blob) > MAX_UPLOAD_BYTES:
        raise ImportProblem("Upload exceeds the 8 MiB V1 limit")
    if not blob:
        raise ImportProblem("Empty upload")
    if filename.lower().endswith(".json"):
        return blob
    if not filename.lower().endswith(".zip"):
        raise ImportProblem("Only .json or .zip input is accepted")
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            files = z.infolist()
            if len(files) > MAX_ZIP_FILES:
                raise ImportProblem("ZIP file count exceeds the safety limit")
            total = 0
            json_names = []
            for info in files:
                name = info.filename
                path = PurePosixPath(name)
                if (
                    not name or name.startswith(("/", "\\")) or "\\" in name
                    or ":" in name or ".." in path.parts or "." in path.parts
                ):
                    raise ImportProblem("ZIP contains an unsafe archive path")
                if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                    raise ImportProblem("ZIP contains a symlink")
                if info.flag_bits & 0x1:
                    raise ImportProblem("Encrypted ZIP entries are not accepted")
                if info.is_dir():
                    continue
                total += info.file_size
                if total > MAX_UNCOMPRESSED_BYTES:
                    raise ImportProblem("ZIP expands beyond the 32 MiB safety limit")
                if info.file_size > 0 and info.compress_size == 0:
                    raise ImportProblem("Invalid compressed ZIP entry")
                if info.compress_size and info.file_size > 100 * info.compress_size:
                    raise ImportProblem("ZIP entry exceeds max compression ratio")
                if path.suffix.lower() == ".json":
                    json_names.append(info)
            if len(json_names) != 1:
                raise ImportProblem("Synthetic V1 archive must contain exactly one JSON file")
            info = json_names[0]
            with z.open(info) as fd:
                data = fd.read(MAX_UNCOMPRESSED_BYTES + 1)
            if len(data) > MAX_UNCOMPRESSED_BYTES:
                raise ImportProblem("ZIP JSON is too large")
            return data
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as exc:
        raise ImportProblem("Invalid ZIP archive") from exc


def require_str(value: object, name: str, max_length: int = 200000) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ImportProblem(f"Invalid required string: {name}")
    return value


def load_synthetic(blob: bytes, provider: str) -> list[Conversation]:
    if provider not in ("chatgpt", "claude"):
        raise ImportProblem("Provider must be chatgpt or claude")
    try:
        data = json.loads(blob.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ImportProblem("Invalid UTF-8 JSON") from exc
    if not isinstance(data, dict) or data.get("nexus_fixture") != "synthetic-v1":
        raise ImportProblem(
            "Unsupported real export format. V1 only supports synthetic-v1 test fixtures "
            "until redacted real exports have been reviewed."
        )
    if data.get("provider") != provider:
        raise ImportProblem("Requested provider and fixture provider differ")
    container_name = "conversations" if provider == "chatgpt" else "chats"
    threads = data.get(container_name)
    if not isinstance(threads, list) or len(threads) > 10000:
        raise ImportProblem("Invalid conversation collection")
    output = []
    seen = 0
    for idx, thread in enumerate(threads):
        if not isinstance(thread, dict):
            raise ImportProblem(f"Thread {idx} is not an object")
        identity = require_str(thread.get("id" if provider == "chatgpt" else "uuid"), "thread id", 1000)
        title = require_str(thread.get("title" if provider == "chatgpt" else "name"), "title", 1000)
        msgs = thread.get("messages")
        if not isinstance(msgs, list):
            raise ImportProblem("Missing messages array")
        parsed = []
        for pos, msg in enumerate(msgs):
            seen += 1
            if seen > MAX_MESSAGES:
                raise ImportProblem("Synthetic fixture exceeds message count limit")
            if not isinstance(msg, dict):
                raise ImportProblem(f"Message {pos} is not an object")
            msg_id = require_str(msg.get("id" if provider == "chatgpt" else "uuid"), "message id", 1000)
            role = require_str(msg.get("role" if provider == "chatgpt" else "sender"), "role", 60)
            content = require_str(msg.get("text" if provider == "chatgpt" else "content"), "content")
            occurred = msg.get("created_at")
            if occurred is not None and (not isinstance(occurred, str) or len(occurred) > 100):
                raise ImportProblem("Invalid created_at field")
            parsed.append(Message(msg_id, role, content, occurred,
                                  hashlib.sha256(content.encode("utf-8")).hexdigest()))
        output.append(Conversation(identity, title, parsed))
    return output


def validate_account_alias(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[\w .@+-]{1,100}", value, flags=re.UNICODE):
        raise ImportProblem("Invalid account alias")
    return value
