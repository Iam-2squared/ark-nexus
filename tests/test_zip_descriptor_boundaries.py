"""ZIP data descriptors: synthetic mismatch/missing refusals and valid controls."""

import io
import json
import struct
import zipfile

import pytest

from nexus.importers import _zip_descriptor

CODECS = [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA]


def descriptor_archive(payload, compression, wide):
    class NonSeeking(io.BytesIO):
        def seekable(self):
            return False

        def seek(self, *_args):
            raise io.UnsupportedOperation("Synthetic non-seeking writer")

    output = NonSeeking()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        with archive.open("synthetic.json", "w", force_zip64=wide) as stream:
            stream.write(json.dumps(payload).encode())
    blob = bytearray(output.getvalue())
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        info = archive.infolist()[0]
        offset = 30 + struct.unpack_from("<H", blob, 26)[0] + struct.unpack_from("<H", blob, 28)[0]
        offset += info.compress_size
    assert struct.unpack_from("<H", blob, 6)[0] & 8
    assert blob[offset:offset + 4] == b"PK\x07\x08"
    return blob, offset


def remove_before_directory(blob, start, size):
    del blob[start:start + size]
    end = blob.rfind(b"PK\x05\x06")
    assert end >= 0
    directory = struct.unpack_from("<I", blob, end + 16)[0]
    struct.pack_into("<I", blob, end + 16, directory - size)


def upload(client, blob):
    return client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "synthetic"},
                       files={"file": ("synthetic.zip", bytes(blob), "application/zip")})


@pytest.mark.parametrize("compression", CODECS)
@pytest.mark.parametrize("wide", [False, True], ids=["ordinary", "zip64"])
@pytest.mark.parametrize("field", ["crc", "compressed", "decoded"])
def test_contradictory_descriptor_fields_refuse_before_any_import(client, seed_chatgpt,
                                                                 compression, wide, field):
    blob, descriptor = descriptor_archive(seed_chatgpt, compression, wide)
    width = 8 if wide else 4
    offset = descriptor + {"crc": 4, "compressed": 8, "decoded": 8 + width}[field]
    format = "<Q" if wide and field != "crc" else "<I"
    struct.pack_into(format, blob, offset, struct.unpack_from(format, blob, offset)[0] ^ 1)
    response = upload(client, blob)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid ZIP archive"}
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM source_instances").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


@pytest.mark.parametrize("compression", CODECS)
@pytest.mark.parametrize("wide", [False, True], ids=["ordinary", "zip64"])
def test_missing_required_descriptor_is_not_ignored(client, seed_chatgpt, compression, wide):
    blob, descriptor = descriptor_archive(seed_chatgpt, compression, wide)
    remove_before_directory(blob, descriptor, 24 if wide else 16)
    response = upload(client, blob)
    assert response.status_code == 422 and response.json() == {"detail": "Invalid ZIP archive"}


@pytest.mark.parametrize("compression", CODECS)
@pytest.mark.parametrize("wide", [False, True], ids=["ordinary", "zip64"])
def test_valid_descriptor_without_optional_signature_still_imports(client, seed_chatgpt,
                                                                  compression, wide):
    blob, descriptor = descriptor_archive(seed_chatgpt, compression, wide)
    remove_before_directory(blob, descriptor, 4)
    response = upload(client, blob)
    assert response.status_code == 201


@pytest.mark.parametrize("wide", [False, True])
@pytest.mark.parametrize("signed", [False, True])
def test_signature_valued_crc_is_not_confused_with_optional_signature(wide, signed):
    info = zipfile.ZipInfo("synthetic.json")
    info.CRC, info.compress_size, info.file_size = 0x08074b50, 17, 23
    descriptor = struct.pack("<IQQ" if wide else "<III", info.CRC, 17, 23)
    if signed:
        descriptor = b"PK\x07\x08" + descriptor
    info._end_offset = len(descriptor)
    _zip_descriptor(descriptor, info, 0, wide)
