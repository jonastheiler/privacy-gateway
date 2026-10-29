"""Measure what a redaction method lets through (privacy) and what it destroys (utility)."""

import argparse
import re
from collections import Counter

from privacy_gateway import regex_baseline
from privacy_gateway.data import PII_SLOTS, load_docs

METHODS = {"regex": regex_baseline.redact}


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def leaked(entity: dict, redacted: str) -> bool:
    """True if the identifying part of the entity is still in the redacted text."""
    value = entity["type"], entity["value"]
    match value:
        case "PERSON", name:  # the surname identifies; "Anna" alone does not
            return re.search(rf"\b{re.escape(name.split()[-1])}\b", redacted) is not None
        case "ADDRESS", address:  # street and number; the town alone does not
            return address.split(",")[0] in redacted
        case "PHONE", number:  # last 9 digits, so "+41 79" and "079" count as the same
            return digits(number)[-9:] in digits(redacted)
        case "AHV" | "IBAN", number:  # digits only, so reformatting does not hide a leak
            return digits(number) in digits(redacted)
        case _, other:
            return other in redacted


def report(docs: list[dict], redacted: list[str]) -> None:
    total, leaks = Counter(), Counter()
    kept = 0
    for doc, text in zip(docs, redacted, strict=True):
        for entity in doc["pii"]:
            total[entity["type"]] += 1
            leaks[entity["type"]] += leaked(entity, text)
        kept += sum(value in text for value in doc["keep"])

    print(f"{'entity':<10}{'count':>7}{'protected':>11}")
    for entity_type in dict.fromkeys(PII_SLOTS.values()):
        n = total[entity_type]
        print(f"{entity_type:<10}{n:>7}{1 - leaks[entity_type] / n:>11.1%}")
    n = total.total()
    print(f"{'all':<10}{n:>7}{1 - leaks.total() / n:>11.1%}")
    n_keep = sum(len(doc["keep"]) for doc in docs)
    print(f"\nnon-personal facts kept: {kept / n_keep:.1%} of {n_keep}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("method", choices=METHODS)
    args = parser.parse_args()
    docs = load_docs()
    report(docs, [METHODS[args.method](doc["text"]) for doc in docs])


if __name__ == "__main__":
    main()
