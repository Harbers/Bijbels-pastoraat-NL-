import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from fastapi.testclient import TestClient
    from main import app
except ImportError:  # pragma: no cover - allows skipping when deps ontbreken
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
from psalm_parser import parse_psalm_reference
from response_validation import ensure_response_matches_schema


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Psalm 118: 1, 2 en 5", {"psalm_number": 118, "verses": [1, 2, 5]}),
        ("ps 118:1-3,5", {"psalm_number": 118, "verses": [1, 2, 3, 5]}),
        ("Ps. 23 vers 1 t/m 3 en 6", {"psalm_number": 23, "verses": [1, 2, 3, 6]}),
        ("psalm 91 verzen 1-4; 6", {"psalm_number": 91, "verses": [1, 2, 3, 4, 6]}),
        ("ps 119: 105", {"psalm_number": 119, "verses": [105]}),
        ("PSALM 1:1", {"psalm_number": 1, "verses": [1]}),
        ("ps 12:1 t/m 2", {"psalm_number": 12, "verses": [1, 2]}),
        ("ps.150:5 plus 6", {"psalm_number": 150, "verses": [5, 6]}),
        ("psalm 3 verzen 2 en 4", {"psalm_number": 3, "verses": [2, 4]}),
        ("ps 118:1-3, 5", {"psalm_number": 118, "verses": [1, 2, 3, 5]}),
    ],
)
def test_parse_psalm_reference_happy(text, expected):
    parsed = parse_psalm_reference(text)
    assert parsed.status == "ok"
    assert parsed.request == expected


def test_parse_invalid_missing_verses():
    parsed = parse_psalm_reference("psalm 118:")
    assert parsed.status == "invalid_request"


@pytest.mark.parametrize("text", ["psalm 0:1", "ps 151:1", "", "   ", "foo bar"])
def test_parse_invalid_inputs(text):
    parsed = parse_psalm_reference(text)
    assert parsed.status == "invalid_request"


def test_response_schema_ok():
    payload = {
        "intent": "psalm_lookup_1773",
        "status": "ok",
        "request": {"psalm_number": 118, "verses": [1, 2, 5]},
        "result": {
            "verified": True,
            "verses": [
                {"verse": 1, "text": "tekst"},
                {"verse": 2, "text": "tekst"},
            ],
        },
    }
    ensure_response_matches_schema(payload)


def test_response_schema_invalid_request():
    payload = {
        "intent": "psalm_lookup_1773",
        "status": "invalid_request",
        "request": {"psalm_number": 118, "verses": []},
        "result": {"message": "Geen verzen"},
    }
    ensure_response_matches_schema(payload)


def test_response_schema_not_found():
    payload = {
        "intent": "psalm_lookup_1773",
        "status": "not_found",
        "request": {"psalm_number": 5, "verses": [7]},
        "result": {
            "verified": False,
            "message": "Vers niet gevonden",
            "verses": [],
        },
    }
    ensure_response_matches_schema(payload)


def test_response_schema_verification_failed():
    payload = {
        "intent": "psalm_lookup_1773",
        "status": "verification_failed",
        "request": {"psalm_number": 5, "verses": [1]},
        "result": {"verified": False, "message": "mismatch"},
    }
    ensure_response_matches_schema(payload)


@pytest.mark.skipif(TestClient is None or app is None, reason="fastapi niet geïnstalleerd")
def test_psalm_lookup_integration(monkeypatch):
    calls = {"max": 0, "vers": []}

    def fake_max(psalm: int) -> int:
        calls["max"] += 1
        return 10

    def fake_vers(psalm: int, vers: int) -> str:
        calls["vers"].append(vers)
        return f"Psalm {psalm} vers {vers}"

    monkeypatch.setattr("psalms.client.get_max_vers", fake_max)
    monkeypatch.setattr("psalms.client.get_vers", fake_vers)

    client_http = TestClient(app)
    response = client_http.get("/api/psalm/lookup", params={"query": "Psalm 118: 1, 2 en 5"})

    assert response.status_code == 200
    data = response.json()
    ensure_response_matches_schema(data)
    assert data["status"] == "ok"
    assert data["request"] == {"psalm_number": 118, "verses": [1, 2, 5]}
    assert [v["verse"] for v in data["result"]["verses"]] == [1, 2, 5]
    assert calls == {"max": 1, "vers": [1, 2, 5]}
