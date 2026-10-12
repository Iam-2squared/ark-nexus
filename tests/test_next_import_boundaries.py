"""Synthetic request framing and multipart parameter ambiguity regressions."""

import asyncio
import json

import pytest
from starlette.datastructures import Headers

from nexus.memory_upload import MemoryMultipart
from nexus.security import MAX_JSON_BODY, LocalBoundary

TOKEN = "synthetic-next-boundary-token-not-a-private-key"
BOUNDARY = b"nexus-next-synthetic-boundary"


def boundary_request(method, body, headers=()):
    observations = {"handler_calls": 0, "body_reads": 0}
    responses = []

    async def handler(_scope, receive, send):
        observations["handler_calls"] += 1
        assert (await receive())["body"] == body
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def receive():
        observations["body_reads"] += 1
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        responses.append(message)

    scope = {"type": "http", "path": "/api/v1/imports", "method": method,
             "client": ("127.0.0.1", 10000), "headers": [
                 (b"host", b"127.0.0.1:8788"),
                 (b"authorization", b"Bearer " + TOKEN.encode()),
                 (b"x-nexus-request", b"1"), *headers,
             ]}
    asyncio.run(LocalBoundary(handler, lambda: TOKEN)(scope, receive, send))
    return responses, observations


@pytest.mark.parametrize("method", ["GET", "PATCH", "HEAD"])
@pytest.mark.parametrize("framing", ["declared", "chunked"])
def test_only_post_imports_receives_the_larger_upload_envelope(method, framing):
    body = b"x" * (MAX_JSON_BODY + 1)
    headers = [(b"content-length", str(len(body)).encode())] if framing == "declared" else [
        (b"transfer-encoding", b"chunked"),
    ]
    responses, observations = boundary_request(method, body, headers)
    assert responses[0]["status"] == 413
    assert observations == {"handler_calls": 0, "body_reads": int(framing == "chunked")}
    assert json.loads(responses[-1]["body"]) == {"detail": "Request body exceeds safety limit"}


def test_post_import_larger_envelope_still_reaches_its_capacity_bounded_handler():
    body = b"x" * (MAX_JSON_BODY + 1)
    responses, observations = boundary_request("POST", body)
    assert responses[0]["status"] == 200
    assert observations == {"handler_calls": 1, "body_reads": 1}


@pytest.mark.parametrize("value", [
    b"gzip", b"gzip, chunked", b"chunked, chunked", b"chunked\xa0", b"\nchunked",
])
def test_boundary_refuses_unsupported_transfer_codings_before_body(value):
    # Raw ASGI tests supplement the upstream HTTP parser's existing framing checks.
    responses, observations = boundary_request("POST", b"", [(b"transfer-encoding", value)])
    assert responses[0]["status"] == 400
    assert observations == {"handler_calls": 0, "body_reads": 0}
    assert json.loads(responses[-1]["body"]) == {"detail": "Unsupported request framing"}


def test_valid_case_insensitive_chunked_coding_is_preserved():
    responses, observations = boundary_request("POST", b"synthetic", [
        (b"transfer-encoding", b"ChUnKeD"),
    ])
    assert responses[0]["status"] == 200
    assert observations == {"handler_calls": 1, "body_reads": 1}


def multipart_body(payload, *, provider_options=b'name="provider"',
                   filename_options=b'name="file"; filename="synthetic.json"',
                   provider_headers=b"", file_headers=b"", file_first=False):
    parts = [
        (provider_options, provider_headers, b"chatgpt"),
        (b'name="account_alias"', b"", b"synthetic"),
        (filename_options, file_headers, json.dumps(payload, ensure_ascii=False).encode()),
    ]
    if file_first:
        parts = [parts[-1], *parts[:-1]]
    return b"".join(
        b"--" + BOUNDARY + b"\r\nContent-Disposition: form-data; " + options
        + b"\r\n" + extra + b"\r\n" + content + b"\r\n"
        for options, extra, content in parts
    ) + b"--" + BOUNDARY + b"--\r\n"


@pytest.mark.parametrize("kind", [
    "boundary-same", "boundary-different", "charset-same", "charset-different",
    "name-same", "name-different", "name-case", "filename-same", "filename-different",
])
def test_duplicate_multipart_parameters_are_rejected_before_any_import(
    client, seed_chatgpt, kind,
):
    content_type = b"multipart/form-data; boundary=" + BOUNDARY
    options = {}
    if kind == "boundary-same":
        content_type += b"; boundary=" + BOUNDARY
    elif kind == "boundary-different":
        content_type = b"multipart/form-data; boundary=ignored; BOUNDARY=" + BOUNDARY
    elif kind.startswith("charset"):
        first = b"utf-8" if kind == "charset-same" else b"iso-8859-1"
        content_type += b"; charset=" + first + b"; CHARSET=utf-8"
    elif kind.startswith("name"):
        first = b"provider" if kind == "name-same" else b"unsupported"
        duplicate = b"NAME" if kind == "name-case" else b"name"
        options["provider_options"] = b'name="' + first + b'"; ' + duplicate + b'="provider"'
    else:
        first = b"synthetic.json" if kind == "filename-same" else b"synthetic.zip"
        options["filename_options"] = (b'name="file"; filename="' + first
                                       + b'"; FILENAME="synthetic.json"')
    response = client.post("/api/v1/imports", content=multipart_body(seed_chatgpt, **options),
                           headers={"Content-Type": content_type.decode()})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid multipart input"}
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0
    assert client.get("/api/v1/integrity").json()["ok"] is True


@pytest.mark.parametrize("extra", [
    b"Content-Type: text/plain; charset=iso-8859-1\r\n",
    b"Content-Type: text/plain; charset=iso-8859-1; CHARSET=utf-8\r\n",
    b"Content-Transfer-Encoding: base64\r\n",
])
@pytest.mark.parametrize("part", ["provider", "file"])
def test_field_encoding_cannot_disagree_with_the_utf8_only_import_contract(
    client, seed_chatgpt, extra, part,
):
    response = client.post("/api/v1/imports",
                           content=multipart_body(seed_chatgpt, **{part + "_headers": extra}),
                           headers={"Content-Type": "multipart/form-data; boundary="
                                    + BOUNDARY.decode()})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid multipart input"}
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0


@pytest.mark.parametrize("options", [
    b'name="provider"; unexpected=synthetic',
    b'name="provider"; name*=utf-8\'\'unsupported',
    b'name="provider"; name="unterminated',
    b'name="provider"; name=provider garbage',
    b'name="provider"; ignored="synthetic\x00marker"',
])
def test_unsupported_or_malformed_parameter_syntax_has_a_fixed_redacted_error(
    client, seed_chatgpt, options,
):
    response = client.post("/api/v1/imports",
                           content=multipart_body(seed_chatgpt, provider_options=options),
                           headers={"Content-Type": "multipart/form-data; boundary="
                                    + BOUNDARY.decode()})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid multipart input"}
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0


def test_late_parameter_failure_closes_owned_buffer_and_releases_import_capacity(
    client, seed_chatgpt, monkeypatch,
):
    from nexus import memory_upload

    buffers = []
    original = memory_upload.MemoryUpload

    def observed():
        buffer = original()
        buffers.append(buffer)
        return buffer

    monkeypatch.setattr(memory_upload, "MemoryUpload", observed)
    bad = multipart_body(seed_chatgpt, file_first=True,
                         provider_options=b'name="unsupported"; name="provider"')
    headers = {"Content-Type": "multipart/form-data; boundary=" + BOUNDARY.decode()}
    for _ in range(3):
        response = client.post("/api/v1/imports", content=bad, headers=headers)
        assert response.status_code == 422
    assert len(buffers) == 3 and all(buffer.closed for buffer in buffers)
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0
    response = client.post("/api/v1/imports", content=multipart_body(seed_chatgpt), headers=headers)
    assert response.status_code == 201
    assert response.json()["counts"]["messages_inserted"] == 2
    assert len(buffers) == 4 and all(buffer.closed for buffer in buffers)
    assert client.get("/api/v1/integrity").json()["ok"] is True


@pytest.mark.parametrize("chunk_size", [1, 7, 65536])
def test_multipart_parameter_validation_preserves_quoted_names_utf8_and_chunk_boundaries(
    seed_chatgpt, chunk_size,
):
    filename = '合成; quoted " name.json'
    body = multipart_body(
        seed_chatgpt,
        filename_options=b'name="file"; filename="'
        + filename.replace('"', '\\"').encode() + b'"',
        provider_headers=b"Content-Type: text/plain; charset=UTF-8\r\n",
        file_headers=b"Content-Type: application/json\r\n",
    )

    async def scenario():
        async def stream():
            for index in range(0, len(body), chunk_size):
                yield body[index:index + chunk_size]

        parser = MemoryMultipart(Headers({"content-type": "multipart/form-data; boundary="
                                         + BOUNDARY.decode() + "; charset=utf-8"}), stream())
        try:
            form = await parser.parse()
            assert form["provider"] == "chatgpt"
            assert form["account_alias"] == "synthetic"
            assert form["file"].filename == filename
            assert json.loads(await form["file"].read()) == seed_chatgpt
        finally:
            parser.close()
        assert parser.buffers and all(buffer.closed for buffer in parser.buffers)

    asyncio.run(scenario())
