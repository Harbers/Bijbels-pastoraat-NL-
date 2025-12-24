from __future__ import annotations

from typing import Any, Dict, List


ALLOWED_STATUSES = {"ok", "not_found", "verification_failed", "invalid_request"}


def _ensure_condition(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_request(request: Dict[str, Any], *, allow_empty_verses: bool) -> None:
    _ensure_condition(isinstance(request, dict), "request moet een object zijn")
    _ensure_condition("psalm_number" in request, "psalm_number ontbreekt")
    _ensure_condition("verses" in request, "verses ontbreekt")

    psalm_number = request.get("psalm_number")
    _ensure_condition(isinstance(psalm_number, int), "psalm_number moet integer zijn")
    _ensure_condition(1 <= psalm_number <= 150, "psalm_number buiten bereik")

    verses = request.get("verses")
    _ensure_condition(isinstance(verses, list), "verses moet een array zijn")
    if not allow_empty_verses:
        _ensure_condition(len(verses) >= 1, "verses mag niet leeg zijn")
    for item in verses:
        _ensure_condition(isinstance(item, int) and item >= 1, "vers moet integer >= 1 zijn")
    _ensure_condition(len(verses) == len(set(verses)), "verses moeten uniek zijn")


def _validate_result(result: Dict[str, Any]) -> None:
    allowed_keys = {"verified", "verses", "message"}
    _ensure_condition(set(result).issubset(allowed_keys), "Onbekende velden in result")
    if "verified" in result:
        _ensure_condition(isinstance(result["verified"], bool), "verified moet boolean zijn")
    if "verses" in result:
        verses = result["verses"]
        _ensure_condition(isinstance(verses, list), "result.verses moet een array zijn")
        for item in verses:
            _ensure_condition(isinstance(item, dict), "result.verses items moeten objecten zijn")
            _ensure_condition({"verse", "text"}.issubset(item.keys()), "verse/text vereist in result")
            _ensure_condition(isinstance(item.get("verse"), int) and item["verse"] >= 1, "verse moet integer >=1")
            _ensure_condition(isinstance(item.get("text"), str), "text moet string zijn")
    if "message" in result:
        _ensure_condition(isinstance(result["message"], str), "message moet string zijn")


def ensure_response_matches_schema(payload: Dict[str, Any]) -> None:
    _ensure_condition(isinstance(payload, dict), "payload moet een object zijn")
    _ensure_condition(payload.get("intent") == "psalm_lookup_1773", "intent ongeldig")

    status = payload.get("status")
    _ensure_condition(status in ALLOWED_STATUSES, "status ongeldig")

    request = payload.get("request")
    allow_empty = status == "invalid_request"
    _validate_request(request, allow_empty_verses=allow_empty)

    if "result" in payload and payload["result"] is not None:
        _ensure_condition(isinstance(payload["result"], dict), "result moet een object zijn")
        _validate_result(payload["result"])
