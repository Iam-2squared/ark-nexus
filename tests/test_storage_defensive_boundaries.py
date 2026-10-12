"""Independent corrupt-metadata and ZIP-header refusals, synthetic-only."""

import io
import json
import struct
import zipfile

import pytest


@pytest.mark.parametrize("identity", [None, "", "\x00", b"\xff"])
@pytest.mark.parametrize("route", ["/api/v1/overview", "/api/v1/projects",
                                   "/api/v1/search?q=synthetic", "/api/v1/conversations"])
def test_unreferenced_invalid_identity_refuses_public_reads(client, identity, route):
    store = client.app.state.store
    with store.connect() as db:
        db.execute("INSERT INTO projects(id,name) VALUES(?,?)", (identity, "Synthetic"))
    response = client.get(route)
    assert response.status_code == 503
    assert response.json() == {"detail": "Local storage unavailable"}
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 0


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED,
                                        zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA],
                         ids=["stored", "deflate", "bzip2", "lzma"])
@pytest.mark.parametrize("field,offset", [("crc", 14), ("compressed", 18), ("decoded", 22)])
def test_contradictory_non_descriptor_local_zip_sizes_and_crc_are_rejected(
    client, seed_chatgpt, compression, field, offset,
):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=compression) as archive:
        archive.writestr("synthetic.json", json.dumps(seed_chatgpt).encode())
    blob = bytearray(output.getvalue())
    assert not struct.unpack_from("<H", blob, 6)[0] & 8
    current = struct.unpack_from("<I", blob, offset)[0]
    struct.pack_into("<I", blob, offset, current ^ 1)
    response = client.post("/api/v1/imports", data={"provider": "chatgpt",
                                                "account_alias": "synthetic"},
                           files={"file": ("synthetic.zip", bytes(blob), "application/zip")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid ZIP archive"}
    with client.app.state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM source_instances").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM import_batches").fetchone()[0] == 0
