import sys
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """
    Spins up the FastAPI app against a fresh, isolated SQLite file per test
    (never touches the real dev split.db) and tears down cleanly afterward.

    app.database reads DATABASE_URL at import time, so we set the env var
    first and then force a clean re-import of the whole `app` package.
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]

    main = importlib.import_module("app.main")

    with TestClient(main.app) as test_client:
        yield test_client

    for mod_name in list(sys.modules):
        if mod_name == "app" or mod_name.startswith("app."):
            del sys.modules[mod_name]


@pytest.fixture()
def trip(client):
    """Creates a trip with three members and returns its JSON body."""
    res = client.post("/api/trips", json={
        "name": "Goa Trip",
        "member_names": ["Alice", "Bob", "Carol"],
    })
    assert res.status_code == 200
    return res.json()
