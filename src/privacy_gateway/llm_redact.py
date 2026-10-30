"""Pseudonymize with the local LLM: the model finds the entities, plain code replaces them."""

import argparse
import json
from collections import Counter
from pathlib import Path

from privacy_gateway.data import PII_SLOTS, load_docs
from privacy_gateway.local_llm import chat

RUNS_DIR = Path("data/runs")
TYPES = list(dict.fromkeys(PII_SLOTS.values()))

SYSTEM = (
    "You find personal data in German text. List every mention of: PERSON (a person's "
    "name, also a surname on its own), AHV (Swiss social security number, 756.xxxx.xxxx.xx), "
    "IBAN, PHONE, EMAIL and ADDRESS (street, house number, postcode and town). Copy each "
    "mention exactly as it is written. Only list data that identifies a person, not amounts, "
    "dates or reference numbers. Answer with JSON that has one list per type: "
    '{"PERSON": ["..."], "AHV": [], "IBAN": [], "PHONE": [], "EMAIL": [], "ADDRESS": []}'
)
# One required list per type: the grammar walks the model through every type in turn.
# A single free-form list let it stop after the first name it found.
SCHEMA = {
    "type": "object",
    "properties": {t: {"type": "array", "items": {"type": "string"}} for t in TYPES},
    "required": TYPES,
}


def find_entities(text: str, grammar: bool = True) -> dict:
    """Ask the local LLM for the entities; an answer that isn't the expected JSON finds none."""
    result = chat(text, system=SYSTEM, max_tokens=400, schema=SCHEMA if grammar else None)
    try:
        answer = json.loads(result["text"])
        entities = [{"type": t, "text": str(s)} for t in TYPES for s in answer.get(t, [])]
        valid = True
    except (json.JSONDecodeError, AttributeError, TypeError):
        entities, valid = [], False
    return {"entities": entities, "valid_json": valid, "seconds": result["seconds"],
            "output_tokens": result["output_tokens"]}


def pseudonymize(text: str, entities: list[dict]) -> tuple[str, dict]:
    """Replace each found entity with a numbered placeholder; return the text and the map back."""
    mapping, counts = {}, Counter()
    for entity in entities:
        value = entity["text"].strip()
        if value and value in text and value not in mapping.values():  # ignore invented ones
            entity_type = entity["type"] if entity["type"] in TYPES else "PII"
            counts[entity_type] += 1
            mapping[f"<{entity_type}_{counts[entity_type]}>"] = value
    # Longest first, so "Anna Meier" becomes one placeholder before "Meier" is replaced alone.
    for placeholder, value in sorted(mapping.items(), key=lambda kv: -len(kv[1])):
        text = text.replace(value, placeholder)
    return text, mapping


def first_of_each_kind(docs: list[dict], n: int) -> list[dict]:
    seen, subset = Counter(), []
    for doc in docs:
        if seen[doc["kind"]] < n:
            subset.append(doc)
            seen[doc["kind"]] += 1
    return subset


def load_run(name: str) -> dict[int, dict]:
    with (RUNS_DIR / f"{name}.jsonl").open(encoding="utf-8") as f:
        return {row["id"]: row for row in map(json.loads, f)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="run name, e.g. qwen3-1.7b-q4 (the model the server runs)")
    parser.add_argument("--no-grammar", action="store_true", help="free generation, no schema")
    parser.add_argument("--limit", type=int, help="only the first N documents of each kind")
    args = parser.parse_args()

    docs = load_docs()
    if args.limit:
        docs = first_of_each_kind(docs, args.limit)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    with (RUNS_DIR / f"{args.name}.jsonl").open("w", encoding="utf-8") as f:
        for i, doc in enumerate(docs, 1):
            row = {"id": doc["id"], **find_entities(doc["text"], grammar=not args.no_grammar)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()  # a long CPU run keeps what it has if interrupted
            print(f"{i}/{len(docs)} {row['seconds']:.1f} s, {len(row['entities'])} entities")


if __name__ == "__main__":
    main()
