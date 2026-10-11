import json

import pytest


@pytest.mark.parametrize("number", ["1e9999", "-1e9999"])
def test_overflow_json_number_rejected_even_in_unknown_metadata(client, seed_chatgpt, number):
    fixture = {**seed_chatgpt, "unknown_metadata": "REPLACE-NUMBER"}
    blob = json.dumps(fixture).replace('"REPLACE-NUMBER"', number).encode("utf-8")
    response = client.post("/api/v1/imports", data={"provider": "chatgpt", "account_alias": "probe"},
                           files={"file": ("synthetic.json", blob, "application/json")})
    assert response.status_code == 422
    assert response.json() == {"detail": "Non-finite JSON numbers are not accepted"}
    assert all(value == 0 for value in client.get("/api/v1/overview").json()["counts"].values())
