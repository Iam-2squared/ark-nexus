import io
import json
import struct
import warnings
import zipfile

import pytest

from nexus.importers import MAX_UNCOMPRESSED_BYTES, ImportProblem, safe_json_payload


def archive(entries, compression=zipfile.ZIP_STORED):
    out = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(out, "w", compression=compression) as z:
            for name, text in entries:
                z.writestr(name, text)
    return out.getvalue()


@pytest.mark.parametrize("payload", [
    archive([("a.json", "{}"), ("a.json", "{}")]),
    archive([(f"file{i}.json", "{}") for i in range(201)]),
    archive([("bomb.json", "0" * 100000)], zipfile.ZIP_DEFLATED),
    archive([("./dot.json", "{}")]),
    b"not-a-zip",
], ids=["duplicate-paths", "201-entries", "compression-bomb", "dot-path", "corrupt-zip"])
def test_abusive_archives_never_extract_files(tmp_path, payload):
    with pytest.raises(ImportProblem):
        safe_json_payload(payload, "unsafe.zip")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["encrypted", "oversize", "unsupported_compression", "bad_crc"])
def test_corrupt_archive_metadata_is_safely_rejected(kind):
    payload = bytearray(archive([("one.json", json.dumps({"example": "fixture"}))]))
    central = payload.index(bytes([80, 75, 1, 2]))
    if kind == "encrypted":
        struct.pack_into("<H", payload, central + 8, 1)
        struct.pack_into("<H", payload, 6, 1)
    elif kind == "oversize":
        struct.pack_into("<I", payload, central + 24, MAX_UNCOMPRESSED_BYTES + 1)
    elif kind == "unsupported_compression":
        struct.pack_into("<H", payload, central + 10, 99)
        struct.pack_into("<H", payload, 8, 99)
    else:
        struct.pack_into("<I", payload, central + 16, 0)
    with pytest.raises(ImportProblem):
        safe_json_payload(bytes(payload), "bad.zip")


@pytest.mark.parametrize("kind,compression", [
    ("deflate", zipfile.ZIP_DEFLATED),
    ("lzma", zipfile.ZIP_LZMA),
    ("bzip2", zipfile.ZIP_BZIP2),
])
def test_corrupt_compressed_stream_is_rejected_without_any_records(client, kind, compression):
    fixture = json.dumps({"nexus_fixture": "synthetic-v1", "provider": "chatgpt",
                          "conversations": []})
    payload = bytearray(archive([("fixture.json", fixture)], compression))
    name_length, extra_length = struct.unpack_from("<HH", payload, 26)
    start = 30 + name_length + extra_length
    if kind == "deflate":
        payload[start] = (payload[start] & ~6) | 6  # Reserved DEFLATE block type.
    elif kind == "lzma":
        payload[start + 4:start + 9] = b"\xff" * 5  # Invalid LZMA properties.
    else:
        payload[start:start + 3] = b"BAD"  # Invalid BZip2 signature.
    with pytest.raises(ImportProblem, match="Invalid ZIP archive"):
        safe_json_payload(bytes(payload), "bad-stream.zip")
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("bad-stream.zip", bytes(payload), "application/zip")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid ZIP archive"}
    assert client.get("/api/v1/overview").json()["counts"] == {
        "sources": 0, "conversations": 0, "messages": 0, "projects": 0, "imports": 0,
    }
    assert client.get("/api/v1/imports").json()["items"] == []
