"""Synthetic ASGI lifecycle pressure, cancellation and runtime memory boundaries."""

import asyncio

import pytest
from starlette.datastructures import Headers
from starlette.formparsers import MultiPartException

from nexus.memory_upload import MemoryMultipart, MemoryUpload
from nexus.security import LocalBoundary

TOKEN = "synthetic-memory-quota-token-not-a-secret"


def scope():
    return {"type": "http", "path": "/api/v1/imports", "method": "POST",
            "client": ("127.0.0.1", 10000), "headers": [
                (b"host", b"127.0.0.1:8788"), (b"authorization", b"Bearer " + TOKEN.encode()),
                (b"x-nexus-request", b"1"),
            ]}


def test_import_memory_capacity_is_bounded_and_releases_after_completion():
    async def check():
        entered = 0
        ready = asyncio.Event()
        release = asyncio.Event()
        results = [[], [], [], []]

        async def handler(_scope, _receive, send):
            nonlocal entered
            entered += 1
            if entered == 2:
                ready.set()
            await release.wait()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        boundary = LocalBoundary(handler, lambda: TOKEN)

        async def run(index):
            async def receive():
                return {"type": "http.request", "body": b""}

            async def send(message):
                results[index].append(message)

            await boundary(scope(), receive, send)

        active = [asyncio.create_task(run(i)) for i in range(2)]
        try:
            await asyncio.wait_for(ready.wait(), 1)
            await asyncio.wait_for(run(2), 1)
            assert results[2][0]["status"] == 429
        finally:
            release.set()
            await asyncio.gather(*active)
        await run(3)
        assert results[3][0]["status"] == 200

    asyncio.run(check())


def test_slow_incomplete_body_expires_without_parsing(monkeypatch):
    from nexus import security

    monkeypatch.setattr(security, "MAX_BODY_SECONDS", 0.01, raising=False)

    async def check():
        responses = []

        async def forbidden(*_args):
            pytest.fail("Expired body must never reach a parser or store")

        async def receive():
            await asyncio.sleep(0.1)
            return {"type": "http.request", "body": b"synthetic-private-partial", "more_body": True}

        async def send(message):
            responses.append(message)

        await asyncio.wait_for(LocalBoundary(forbidden, lambda: TOKEN)(scope(), receive, send), 0.5)
        assert responses[0]["status"] == 408
        assert b"synthetic-private" not in responses[-1]["body"]

    asyncio.run(check())


@pytest.mark.parametrize("exception", [asyncio.CancelledError, KeyboardInterrupt, SystemExit,
                                      OSError])
def test_partial_multipart_closes_only_owned_memory_on_any_interruption(exception):
    async def check():
        async def stream():
            yield (b'--synthetic\r\nContent-Disposition: form-data; name="file"; '
                   b'filename="synthetic.json"\r\n\r\nsynthetic-partial')
            raise exception("SYNTHETIC-SENTINEL")

        parser = MemoryMultipart(Headers({"content-type": "multipart/form-data; boundary=synthetic"}),
                                 stream())
        with pytest.raises(exception):
            await parser.parse()
        assert parser.buffers and all(buffer.closed for buffer in parser.buffers)

    asyncio.run(check())


def test_memory_upload_cannot_roll_to_disk_or_expose_a_file_descriptor():
    from nexus.importers import MAX_UPLOAD_BYTES

    buffer = MemoryUpload()
    buffer.write(b"synthetic")
    with pytest.raises(OSError):
        buffer.fileno()
    assert not hasattr(buffer, "rollover")
    buffer.seek(MAX_UPLOAD_BYTES)
    with pytest.raises(MultiPartException):
        buffer.write(b"x")
    buffer.close()
