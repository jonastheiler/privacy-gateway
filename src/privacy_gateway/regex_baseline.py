"""Baseline: redact personal data with regular expressions only."""

import re

# Order matters: IBANs go first, because a phone pattern would match digits inside them.
PATTERNS = {
    "EMAIL": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "IBAN": r"\bCH\d{2}(?: ?\d){17}\b",
    "AHV": r"\b756\.?\d{4}\.?\d{4}\.?\d{2}\b",
    "PHONE": r"(?<!\d)(?:\+41 ?|0)\d{2}(?: ?\d){7}(?!\d)",
    # Street name ending in a common suffix, house number, optional postcode and town.
    "ADDRESS": r"\b[A-ZÄÖÜ]\w*(?:strasse|gasse|weg|platz) \d+\w?(?:, \d{4} [A-ZÄÖÜ][\w. ]*\w)?",
    # Names can only be found from context; the best a regex can do is a title before them.
    "PERSON": r"\b(?:Herr|Frau) [A-ZÄÖÜ]\w+",
}


def redact(text: str) -> str:
    for entity_type, pattern in PATTERNS.items():
        text = re.sub(pattern, f"<{entity_type}>", text)
    return text
