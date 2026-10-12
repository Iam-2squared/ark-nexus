"""Bounded, memory-only multipart staging. No tempfile factory or global TEMP changes.

The API boundary bounds the entire envelope before this route runs. A BytesIO
cannot roll over or supply a file descriptor; adding fileno() cannot spill it.
FastAPI's File/Form contract and validation stay in place. This small parser
subclass is exercised against the installed Starlette on every CI platform.
"""

import io
import re

from fastapi import HTTPException
from fastapi.routing import APIRoute
from python_multipart.multipart import parse_options_header
from starlette import formparsers
from starlette.datastructures import Headers

from nexus.importers import MAX_UPLOAD_BYTES

_TOKEN = rb"[!#$%&'*+\-.^_`|~0-9a-zA-Z]+"
_HEADER_TYPE = re.compile(_TOKEN + rb"(?:/" + _TOKEN + rb")?")
_PARAMETER = re.compile(
    rb";[ \t]*(" + _TOKEN + rb")[ \t]*=[ \t]*(?:" + _TOKEN
    + rb'|"(?:[\x20-\x21\x23-\x5b\x5d-\xff]|\\[\x20-\xff])*")[ \t]*',
)


def checked_options(value: str | bytes, allowed: set[bytes]):
    """Reject ambiguity before the upstream parser discards duplicate parameters.

    Quoted semicolons/escaped quotes remain valid. Extended parameter syntax,
    control bytes and unknown parameters have no V1 interpretation. The header
    stays bounded and no original value appears in the diagnostic.
    """
    raw = value.encode("latin-1") if isinstance(value, str) else value
    raw = raw.strip(b" \t")
    if not raw or len(raw) > 2048:
        raise formparsers.MultiPartException("Invalid multipart parameters")
    main = raw.split(b";", 1)[0].strip(b" \t")
    if not _HEADER_TYPE.fullmatch(main):
        raise formparsers.MultiPartException("Invalid multipart parameters")
    offset = raw.find(b";")
    seen = set()
    while offset != -1 and offset < len(raw):
        match = _PARAMETER.match(raw, offset)
        if match is None:
            raise formparsers.MultiPartException("Invalid multipart parameters")
        name = match[1].lower()
        if name not in allowed or name in seen:
            raise formparsers.MultiPartException("Ambiguous multipart parameters")
        seen.add(name)
        offset = match.end()
    return parse_options_header(raw)


def checked_multipart_type(value: str | bytes):
    content_type, options = checked_options(value, {b"boundary", b"charset"})
    boundary = options.get(b"boundary", b"")
    charset = options.get(b"charset", b"utf-8").lower()
    if (content_type != b"multipart/form-data" or not 1 <= len(boundary) <= 200
            or charset not in {b"utf-8", b"utf8"}):
        raise formparsers.MultiPartException("Unsupported multipart encoding")
    return content_type, options


class MemoryUpload(io.BytesIO):
    _rolled = False  # UploadFile uses this to select synchronous memory operations.
    _max_size = MAX_UPLOAD_BYTES

    def write(self, data):
        if self.tell() + len(data) > MAX_UPLOAD_BYTES:
            raise formparsers.MultiPartException("Upload exceeds safety limit")
        return super().write(data)


class MemoryMultipart(formparsers.MultiPartParser):
    """Only the four V1 fields, strict UTF-8, one file, and a complete final boundary."""

    def __init__(self, headers, stream):
        super().__init__(headers, stream, max_files=1, max_fields=3, max_part_size=4096)
        self.buffers: list[MemoryUpload] = []
        self.seen: set[str] = set()
        self.complete = False

    def on_header_field(self, data, start, end):
        if len(self._current_partial_header_name) + end - start > 100:
            raise formparsers.MultiPartException("Multipart header exceeds safety limit")
        super().on_header_field(data, start, end)

    def on_header_value(self, data, start, end):
        if len(self._current_partial_header_value) + end - start > 2048:
            raise formparsers.MultiPartException("Multipart header exceeds safety limit")
        super().on_header_value(data, start, end)

    def on_header_end(self):
        name = self._current_partial_header_name.lower()
        if name in {b"content-disposition", b"content-type"} and any(
            key == name for key, _ in self._current_part.item_headers
        ):
            raise formparsers.MultiPartException("Ambiguous multipart headers")
        super().on_header_end()

    def on_headers_finished(self):
        # Do not call the upstream allocation hook: its spool factory uses OS TEMP.
        disposition, options = checked_options(
            self._current_part.content_disposition, {b"name", b"filename"},
        )
        if disposition != b"form-data" or self._charset.lower() not in {"utf-8", "utf8"}:
            raise formparsers.MultiPartException("Unsupported multipart encoding")
        for header, value in self._current_part.item_headers:
            if header == b"content-transfer-encoding":
                raise formparsers.MultiPartException("Unsupported multipart encoding")
            if header == b"content-type":
                _, part_options = checked_options(value, {b"charset"})
                if part_options.get(b"charset", b"utf-8").lower() not in {b"utf-8", b"utf8"}:
                    raise formparsers.MultiPartException("Unsupported multipart encoding")
        name = options.get(b"name", b"").decode("utf-8")
        if name not in {"provider", "account_alias", "dry_run", "file"} or name in self.seen:
            raise formparsers.MultiPartException("Ambiguous multipart fields")
        self.seen.add(name)
        self._current_part.field_name = name
        filename = options.get(b"filename")
        if name == "file":
            if filename is None:
                raise formparsers.MultiPartException("File part requires a filename")
            text = filename.decode("utf-8")
            if len(text) > 1000 or "\x00" in text:
                raise formparsers.MultiPartException("Invalid upload filename")
            buffer = MemoryUpload()
            self.buffers.append(buffer)
            self._current_part.file = formparsers.UploadFile(
                buffer, size=0, filename=text, headers=Headers(raw=self._current_part.item_headers),
            )
        elif filename is not None:
            raise formparsers.MultiPartException("Unexpected multipart file")
        else:
            self._current_part.file = None

    def on_part_end(self):
        if self._current_part.file is None:
            text = self._current_part.data.decode("utf-8")
            if "\x00" in text:
                raise formparsers.MultiPartException("Invalid multipart text")
            self.items.append((self._current_part.field_name, text))
        else:
            super().on_part_end()

    def on_end(self):
        self.complete = True

    def close(self):
        # Synchronous, idempotent cleanup also runs on cancellation/SystemExit.
        for buffer in self.buffers:
            buffer.close()

    async def parse(self):
        try:
            checked_multipart_type(self.headers.get("content-type", ""))
            form = await super().parse()
            if not self.complete:
                raise formparsers.MultiPartException("Incomplete multipart envelope")
            return form
        except BaseException:
            self.close()
            raise


class MemoryImportRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        if self.path != "/api/v1/imports" or "POST" not in self.methods:
            return handler

        async def bounded_import(request):
            try:
                checked_multipart_type(request.headers.get("content-type", ""))
            except formparsers.MultiPartException:
                raise HTTPException(422, "Invalid multipart input") from None
            parser = MemoryMultipart(request.headers, request.stream())
            try:
                try:
                    # FastAPI will reuse this form, then perform its existing File/Form validation.
                    request._form = await parser.parse()
                except Exception:
                    raise HTTPException(422, "Invalid multipart input") from None
                return await handler(request)
            finally:
                parser.close()

        return bounded_import
