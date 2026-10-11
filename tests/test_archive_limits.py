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
