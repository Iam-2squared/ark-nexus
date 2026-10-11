"""Safe input staging and synthetic adapter contracts; NOT live vendor adapters."""

import hashlib
import io
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class SyntheticAdapter:
    provider: str
    collection: str
    identity: str
    title: str
    role: str
    text: str
    parser_version: str = PARSER_VERSION
    data_kind: str = "synthetic"

    def load(self, blob: bytes) -> list[Conversation]:
        return _load_fixture(blob, self)


ADAPTERS = {
    "chatgpt": SyntheticAdapter("chatgpt", "conversations", "id", "title", "role", "text"),
    "claude": SyntheticAdapter("claude", "chats", "uuid", "name", "sender", "content"),
}


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
            seen_paths = set()
            for info in files:
                name = info.filename
                path = PurePosixPath(name)
                if (
                    not name or name.startswith(("/", "\\")) or "\\" in name
                    or ":" in name or ".." in name.split("/") or "." in name.split("/")
                    or "\x00" in info.orig_filename
                ):
                    raise ImportProblem("ZIP contains an unsafe archive path")
                if name in seen_paths:
                    raise ImportProblem("ZIP contains duplicate archive paths")
                seen_paths.add(name)
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
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError, NotImplementedError) as exc:
        raise ImportProblem("Invalid ZIP archive") from exc


def require_str(value: object, name: str, max_length: int = 200000) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise ImportProblem(f"Invalid required string: {name}")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ImportProblem(f"Invalid Unicode in: {name}") from exc
    if "\x00" in value:
        raise ImportProblem(f"NUL is not allowed in: {name}")
    return value


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ImportProblem("Duplicate JSON object key")
        result[key] = value
    return result


def invalid_constant(_value):
    raise ImportProblem("Non-finite JSON numbers are not accepted")


def source_timestamp(value: object) -> str | None:
    if value is None:
        return None
    text = require_str(value, "created_at", 100)
    try:
        parsed = datetime.fromisoformat(text)
        if "T" not in text or parsed.utcoffset() is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise ImportProblem("created_at must be a timezone-aware ISO 8601 timestamp") from exc
    return text  # Preserve the source representation as well as its instant.


def load_synthetic(blob: bytes, provider: str) -> list[Conversation]:
    adapter = ADAPTERS.get(provider)
    if adapter is None:
        raise ImportProblem("Provider must be chatgpt or claude")
    return adapter.load(blob)


def _load_fixture(blob: bytes, adapter: SyntheticAdapter) -> list[Conversation]:
    if len(blob) > MAX_UNCOMPRESSED_BYTES:
        raise ImportProblem("JSON exceeds the 32 MiB safety limit")
    try:
        data = json.loads(blob.decode("utf-8-sig"), object_pairs_hook=strict_object,
                          parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, ImportProblem):
            raise
        raise ImportProblem("Invalid UTF-8 JSON") from exc
    stack = [iter((data,))]
    nodes = 0
    while stack:
        try:
            value = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue
        nodes += 1
        if nodes > 1_000_000:
            raise ImportProblem("JSON node count exceeds safety limit")
        if len(stack) > 65:
            raise ImportProblem("JSON nesting exceeds safety limit")
        if isinstance(value, dict):
            stack.append(iter(value.values()))
        elif isinstance(value, list):
            stack.append(iter(value))
    if not isinstance(data, dict) or data.get("nexus_fixture") != "synthetic-v1":
        raise ImportProblem(
            "Unsupported real export format. V1 only supports synthetic-v1 test fixtures "
            "until redacted real exports have been reviewed."
        )
    if data.get("provider") != adapter.provider:
        raise ImportProblem("Requested provider and fixture provider differ")
    threads = data.get(adapter.collection)
    if not isinstance(threads, list) or len(threads) > 10000:
        raise ImportProblem("Invalid conversation collection")
    output = []
    seen = 0
    thread_ids = set()
    for idx, thread in enumerate(threads):
        if not isinstance(thread, dict):
            raise ImportProblem(f"Thread {idx} is not an object")
        identity = require_str(thread.get(adapter.identity), "thread id", 1000)
        if identity in thread_ids:
            raise ImportProblem("Duplicate conversation ID in one fixture")
        thread_ids.add(identity)
        title = require_str(thread.get(adapter.title), "title", 1000)
        msgs = thread.get("messages")
        if not isinstance(msgs, list):
            raise ImportProblem("Missing messages array")
        parsed = []
        message_ids = set()
        for pos, msg in enumerate(msgs):
            seen += 1
            if seen > MAX_MESSAGES:
                raise ImportProblem("Synthetic fixture exceeds message count limit")
            if not isinstance(msg, dict):
                raise ImportProblem(f"Message {pos} is not an object")
            msg_id = require_str(msg.get(adapter.identity), "message id", 1000)
            if msg_id in message_ids:
                raise ImportProblem("Duplicate message ID in one conversation")
            message_ids.add(msg_id)
            role = require_str(msg.get(adapter.role), "role", 60)
            content = require_str(msg.get(adapter.text), "content")
            occurred = source_timestamp(msg.get("created_at"))
            parsed.append(Message(msg_id, role, content, occurred,
                                  hashlib.sha256(content.encode("utf-8")).hexdigest()))
        output.append(Conversation(identity, title, parsed))
    return output


def validate_account_alias(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"[\w .@+-]{1,100}", value, flags=re.UNICODE):
        raise ImportProblem("Invalid account alias")
    return value
