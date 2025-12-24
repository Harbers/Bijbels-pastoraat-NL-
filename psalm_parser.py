from __future__ import annotations

import re
from typing import Dict, List, Tuple


class ParsedPsalmReference:
    def __init__(self, status: str, request: Dict[str, object] | None = None, message: str | None = None):
        self.status = status
        self.request = request or {"psalm_number": 1, "verses": []}
        self.message = message

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "intent": "psalm_lookup_1773",
            "status": self.status,
            "request": self.request,
        }
        if self.message:
            payload["result"] = {"message": self.message}
        return payload


def _normalize_verses_text(raw: str) -> str:
    text = raw.lower().strip()
    text = re.sub(r"\s*(t/m|t\s*m|tm|tot en met|tot-en-met)\s*", "-", text)
    text = re.sub(r"\s*(en|&|plus)\s*", ",", text)
    text = text.replace(";", ",")
    text = re.sub(r",+", ",", text)
    return text.strip()


def _parse_tokens(verse_part: str) -> Tuple[List[int], str | None]:
    tokens = [tok.strip() for tok in verse_part.split(",") if tok.strip()]
    if not tokens:
        return [], "Versdeel ontbreekt of is leeg"

    verses: List[int] = []
    for token in tokens:
        if "-" in token:
            pieces = token.split("-")
            if len(pieces) != 2:
                return [], f"Ongeldig bereik: {token}"
            start_str, end_str = pieces
            if not start_str.isdigit() or not end_str.isdigit():
                return [], f"Ongeldig bereik: {token}"
            start, end = int(start_str), int(end_str)
            if start < 1 or end < 1 or start > end:
                return [], f"Ongeldig bereik: {token}"
            verses.extend(range(start, end + 1))
        else:
            if not token.isdigit():
                return [], f"Ongeldig vers: {token}"
            verse = int(token)
            if verse < 1:
                return [], f"Ongeldig vers: {token}"
            verses.append(verse)
    return sorted(set(verses)), None


def parse_psalm_reference(text: str) -> ParsedPsalmReference:
    if not text or not text.strip():
        return ParsedPsalmReference("invalid_request", message="Input is leeg")

    candidates = [
        re.compile(r"^\s*(?:psalm|ps\.?|ps)?\s*(\d{1,3})\s*[:.]\s*(.+)$", re.IGNORECASE),
        re.compile(r"^\s*(?:psalm|ps\.?|ps)\s*(\d{1,3})\s*(?:vers|verzen)\s+(.+)$", re.IGNORECASE),
    ]

    match = None
    for pattern in candidates:
        match = pattern.match(text)
        if match:
            break

    if not match:
        return ParsedPsalmReference("invalid_request", message="Geen psalmverwijzing gevonden")

    psalm_number = int(match.group(1))
    if psalm_number < 1 or psalm_number > 150:
        safe_psalm = min(150, max(1, psalm_number))
        return ParsedPsalmReference(
            "invalid_request",
            request={"psalm_number": safe_psalm, "verses": []},
            message="Psalmnummer buiten bereik",
        )

    verse_part = match.group(2)
    normalized = _normalize_verses_text(verse_part)
    verses, error = _parse_tokens(normalized)
    if error:
        return ParsedPsalmReference(
            "invalid_request", request={"psalm_number": psalm_number, "verses": []}, message=error
        )
    if not verses:
        return ParsedPsalmReference(
            "invalid_request", request={"psalm_number": psalm_number, "verses": []}, message="Geen verzen herkend"
        )

    request = {"psalm_number": psalm_number, "verses": verses}
    return ParsedPsalmReference("ok", request=request)
