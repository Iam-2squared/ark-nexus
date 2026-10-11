"""Loopback-only HTTP boundary. Imported text never grants execution authority."""

import hmac
from ipaddress import ip_address

from starlette.responses import JSONResponse

from nexus.importers import MAX_UPLOAD_BYTES

LOCAL_AUTHORITIES = {
    f"{host}:{port}"
    for host in ("127.0.0.1", "localhost", "[::1]")
    for port in (8788, 5173)
}
LOCAL_ORIGINS = {f"http://{authority}" for authority in LOCAL_AUTHORITIES}
MAX_JSON_BODY = 64 * 1024
MAX_IMPORT_BODY = MAX_UPLOAD_BYTES + MAX_JSON_BODY


class LocalBoundary:
    def __init__(self, app, key):
        self.app = app
        self.key = key

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def private_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []),
                                      (b"cache-control", b"no-store"),
                                      (b"x-content-type-options", b"nosniff"),
                                      (b"x-frame-options", b"DENY")]
            await send(message)

        async def reject(status, detail):
            await JSONResponse({"detail": detail}, status_code=status)(scope, receive, private_send)

        pairs = scope.get("headers", [])
        headers = {k.lower(): v.decode("latin1") for k, v in pairs}
        # Reject ambiguous authority, Origin and length fields instead of picking one value.
        for field in (b"host", b"origin", b"content-length", b"x-nexus-request", b"authorization"):
            if sum(k.lower() == field for k, _ in pairs) > 1:
                await reject(400, "Ambiguous request headers")
                return
        peer = scope.get("client")
        try:
            local_peer = bool(peer) and ip_address(peer[0]).is_loopback
        except ValueError:
            local_peer = False
        if not local_peer or headers.get(b"host", "").lower() not in LOCAL_AUTHORITIES:
            await reject(403, "Local HTTP access only")
            return
        origin = headers.get(b"origin")
        if origin is not None and origin not in LOCAL_ORIGINS:
            await reject(403, "Cross-site access not permitted")
            return
        if headers.get(b"sec-fetch-site") == "cross-site":
            await reject(403, "Cross-site access not permitted")
            return
        # Health exposes only fixed service metadata, never private records or credentials.
        if scope["path"] != "/api/v1/health":
            expected = "Bearer " + self.key()
            supplied = headers.get(b"authorization", "")
            if not hmac.compare_digest(supplied.encode("latin1"), expected.encode("ascii")):
                await reject(401, "Local access key required")
                return
        if scope["method"] in {"POST", "PATCH", "PUT", "DELETE"}:
            if headers.get(b"x-nexus-request") != "1":
                await reject(403, "X-Nexus-Request: 1 is required for writes")
                return
        limit = MAX_IMPORT_BODY if scope["path"] == "/api/v1/imports" else MAX_JSON_BODY
        declared = headers.get(b"content-length")
        if declared is not None:
            if not declared.isascii() or not declared.isdecimal():
                await reject(400, "Invalid Content-Length")
                return
            if len(declared) > 10 or int(declared) > limit:
                await reject(413, "Request body exceeds safety limit")
                return
        # Bound the actual stream before FastAPI can parse or spool multipart input.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                await reject(413, "Request body exceeds safety limit")
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        if declared is not None and int(declared) != len(body):
            await reject(400, "Content-Length does not match body")
            return
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, private_send)
