"""Bounded synthetic ZIP forensics; no extraction, private records, or provider calls."""

import io
import json
import struct
import zipfile
import zlib

import pytest

from nexus.importers import MAX_UNCOMPRESSED_BYTES, ImportProblem, safe_json_payload

METHODS = [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA]
COMPRESSED = METHODS[1:]


def fixture_blob():
    return json.dumps({"nexus_fixture": "synthetic-v1", "provider": "chatgpt",
                       "conversations": []}).encode()


def archive(payload, compression, *, descriptor=False, zip64=False):
    class NonSeekable(io.BytesIO):
        def seekable(self):
            return False

        def seek(self, *_args):
            raise io.UnsupportedOperation("synthetic non-seekable writer")

    stream = NonSeekable() if descriptor else io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as writer:
        if zip64:
            info = zipfile.ZipInfo("synthetic.json")
            info.compress_type = compression
            with writer.open(info, "w", force_zip64=True) as entry:
                entry.write(payload)
        else:
            writer.writestr("synthetic.json", payload)
    return stream.getvalue()


def corrupt_stream(case, compression):
    expected = fixture_blob()
    decoded = expected + (b" " * 5000 if case == "hidden-expansion" else b"")
    blob = bytearray(archive(decoded, compression))
    central = blob.index(b"PK\x01\x02")
    name_length, extra_length = struct.unpack_from("<HH", blob, 26)
    start = 30 + name_length + extra_length
    compressed_size = struct.unpack_from("<I", blob, central + 20)[0]
    if case == "truncated-terminal":
        del blob[start + compressed_size - 1]
        central -= 1
        compressed_size -= 1
    elif case == "compressed-tail":
        blob[start + compressed_size:start + compressed_size] = b"synthetic-tail"
        central += len(b"synthetic-tail")
        compressed_size += len(b"synthetic-tail")
    if case in {"truncated-terminal", "compressed-tail"}:
        struct.pack_into("<I", blob, 18, compressed_size)
        struct.pack_into("<I", blob, central + 20, compressed_size)
        end = blob.index(b"PK\x05\x06")
        struct.pack_into("<I", blob, end + 16, central)
    if case in {"hidden-expansion", "declared-too-long"}:
        size = len(expected) + int(case == "declared-too-long")
        crc = zlib.crc32(expected)
        struct.pack_into("<II", blob, 14, crc, compressed_size)
        struct.pack_into("<I", blob, 22, size)
        struct.pack_into("<I", blob, central + 16, crc)
        struct.pack_into("<I", blob, central + 24, size)
    return bytes(blob)


@pytest.mark.parametrize("compression", COMPRESSED, ids=["deflate", "bzip2", "lzma"])
@pytest.mark.parametrize("case", [
    "truncated-terminal", "hidden-expansion", "declared-too-long", "compressed-tail",
])
def test_compressed_zip_requires_actual_size_crc_and_complete_single_stream(
    client, case, compression,
):
    blob = corrupt_stream(case, compression)
    with pytest.raises(ImportProblem, match="Invalid ZIP archive"):
        safe_json_payload(blob, "synthetic.zip")
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("synthetic.zip", blob, "application/zip")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid ZIP archive"}
    assert all(value == 0 for value in client.get("/api/v1/overview").json()["counts"].values())
    assert client.get("/api/v1/integrity").json()["ok"] is True


@pytest.mark.parametrize("compression", METHODS, ids=["stored", "deflate", "bzip2", "lzma"])
@pytest.mark.parametrize("field", ["method", "flags"])
def test_local_header_and_directory_cannot_disagree_before_decompression(compression, field):
    blob = bytearray(archive(fixture_blob(), compression))
    if field == "method":
        struct.pack_into("<H", blob, 8, 99)
    else:
        # The central directory still declares plaintext while the local header
        # declares encryption. Neither interpretation is allowed to win silently.
        flags = struct.unpack_from("<H", blob, 6)[0]
        struct.pack_into("<H", blob, 6, flags | 1)
    with pytest.raises(ImportProblem, match="Invalid ZIP archive"):
        safe_json_payload(bytes(blob), "synthetic.zip")


@pytest.mark.parametrize("where", ["directory", "local-header"])
def test_invalid_utf8_archive_names_have_a_fixed_422_and_no_import(client, where):
    blob = bytearray(archive(fixture_blob(), zipfile.ZIP_STORED))
    central = blob.index(b"PK\x01\x02")
    if where == "directory":
        struct.pack_into("<H", blob, central + 8, 0x800)
        blob[central + 46] = 0xFF
    else:
        struct.pack_into("<H", blob, 6, 0x800)
        blob[30] = 0xFF
    with pytest.raises(ImportProblem, match="Invalid ZIP archive"):
        safe_json_payload(bytes(blob), "synthetic.zip")
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("synthetic.zip", bytes(blob), "application/zip")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid ZIP archive"}
    assert client.get("/api/v1/overview").json()["counts"]["imports"] == 0


def test_lzma_dictionary_is_checked_before_decoder_allocation(monkeypatch):
    import lzma

    blob = bytearray(archive(fixture_blob(), zipfile.ZIP_LZMA))
    name_length, extra_length = struct.unpack_from("<HH", blob, 26)
    start = 30 + name_length + extra_length
    struct.pack_into("<I", blob, start + 5, MAX_UNCOMPRESSED_BYTES + 1)
    called = []

    def forbidden_decoder(*_args, **_kwargs):
        called.append(True)
        raise AssertionError("Unqualified dictionary reached the native decoder")

    monkeypatch.setattr(lzma, "LZMADecompressor", forbidden_decoder)
    with pytest.raises(ImportProblem, match="ZIP LZMA dictionary exceeds safety limit"):
        safe_json_payload(bytes(blob), "synthetic.zip")
    assert called == []


def test_lzma_requires_an_explicit_eos_framing_contract():
    blob = bytearray(archive(fixture_blob(), zipfile.ZIP_LZMA))
    central = blob.index(b"PK\x01\x02")
    for offset in (6, central + 8):
        flags = struct.unpack_from("<H", blob, offset)[0]
        struct.pack_into("<H", blob, offset, flags & ~2)
    with pytest.raises(ImportProblem, match="Unsupported ZIP LZMA framing"):
        safe_json_payload(bytes(blob), "synthetic.zip")


@pytest.mark.parametrize("compression", METHODS, ids=["stored", "deflate", "bzip2", "lzma"])
@pytest.mark.parametrize("kind", ["ordinary", "data-descriptor", "zip64-header", "prefixed"])
def test_valid_complete_archives_preserve_all_supported_codecs_and_header_variants(
    client, compression, kind,
):
    expected = fixture_blob()
    blob = archive(expected, compression, descriptor=kind == "data-descriptor",
                   zip64=kind == "zip64-header")
    if kind == "prefixed":
        blob = b"synthetic-prefix" + blob
    assert safe_json_payload(blob, "synthetic.zip") == expected
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "test"},
                           files={"file": ("synthetic.zip", blob, "application/zip")})
    assert response.status_code == 201
    assert response.json()["counts"]["messages_inserted"] == 0
    assert client.get("/api/v1/integrity").json()["ok"] is True
