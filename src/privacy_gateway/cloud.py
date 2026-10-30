"""Round trip: the cloud LLM works on pseudonymized text and the placeholders are mapped back.

Each document goes to the cloud twice, once original and once pseudonymized by a local LLM
run, and the restored answer is compared with the answer on the original. Two tasks:
"record" extracts the facts a back office needs, "reply" drafts a letter to the person.
"""

import argparse
import json
import re

import anthropic

from privacy_gateway.data import load_docs
from privacy_gateway.llm_redact import RUNS_DIR, load_run, pseudonymize

MODEL = "claude-opus-5-5"
FIELDS = ["name", "amount", "date", "iban", "phone", "email", "address"]
PLACEHOLDERS = "Platzhalter wie <PERSON_1> stehen für echte Werte: übernimm sie unverändert."

SYSTEM = {
    "record": (
        "Du erfasst Dokumente für ein Schweizer Backoffice. Gib für die Person, um die es "
        "geht, Name, Betrag, Datum, IBAN, Telefon, E-Mail und Adresse an, jeweils genau so "
        f'geschrieben wie im Text. {PLACEHOLDERS} Fehlt ein Wert, gib "" an.'
    ),
    "reply": (
        "Du arbeitest im Backoffice eines Schweizer Unternehmens. Schreibe der Person, um die "
        "es im Dokument geht, eine kurze, höfliche Antwort mit Anrede (höchstens 120 Wörter). "
        f"Nenne die wichtigen Angaben aus dem Dokument. {PLACEHOLDERS}"
    ),
}
# Structured outputs: the API constrains the answer to this schema, like the grammar locally.
SCHEMA = {
    "type": "object",
    "properties": {field: {"type": "string"} for field in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def ask(client: anthropic.Anthropic, text: str, task: str) -> str:
    output_config = {"effort": "low"}
    if task == "record":
        output_config["format"] = {"type": "json_schema", "schema": SCHEMA}
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM[task],
        messages=[{"role": "user", "content": text}],
        output_config=output_config,
        # If a safety classifier declines, the API reruns the request on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return "{}" if task == "record" else ""
    return next(b.text for b in response.content if b.type == "text")


def restore(text: str, mapping: dict) -> str:
    """Put the real values back where the cloud LLM copied a placeholder."""
    for placeholder, original in mapping.items():
        text = text.replace(placeholder, original)
    return text


def score_record(rows: list[dict]) -> None:
    print(f"{'field':<10}{'same answer':>12}")
    for field in FIELDS:
        same = sum(row["restored"].get(field) == row["original"].get(field) for row in rows)
        print(f"{field:<10}{same / len(rows):>12.1%}")
    same = sum(row["restored"] == row["original"] for row in rows)
    print(f"{'all':<10}{same / len(rows):>12.1%}  (documents with every field the same)")


def score_reply(rows: list[dict], docs: dict[int, dict]) -> None:
    """Free text can't be compared exactly, so check what pseudonymization could break."""
    left = kept = total = salutation_original = salutation_restored = 0
    for row in rows:
        doc = docs[row["id"]]
        # A placeholder the cloud LLM changed ("PERSON_1", "<Person 1>") can't be mapped back.
        left += bool(re.search(r"<[^<>]*\d>|\b[A-Z]+_\d+\b", row["restored"]))
        # Facts and the full name the original reply used must survive the round trip.
        person = next(e["value"] for e in doc["pii"] if e["type"] == "PERSON")
        for value in [*doc["keep"], person]:
            if value in row["original"]:
                total += 1
                kept += value in row["restored"]
        # From <PERSON_1> alone the cloud LLM can't tell "Frau" from "Herr".
        salutation = re.compile(rf"\b(?:Frau|Herr)n? {re.escape(person.split()[-1])}\b")
        salutation_original += bool(salutation.search(row["original"]))
        salutation_restored += bool(salutation.search(row["restored"]))
    n = len(rows)
    print(f"placeholders left over:        {left / n:.1%} of replies")
    print(f"facts and name kept:           {kept / total:.1%} of {total}")
    print(f"'Frau/Herr <surname>' used:    original {salutation_original / n:.1%}, "
          f"pseudonymized {salutation_restored / n:.1%}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=SYSTEM)
    parser.add_argument("run", help="local LLM run in data/runs, e.g. qwen3-1.7b-q4")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    run = load_run(args.run)
    docs = {doc["id"]: doc for doc in load_docs() if doc["id"] in run}
    rows = []
    with (RUNS_DIR / f"cloud-{args.task}-{args.run}.jsonl").open("w", encoding="utf-8") as f:
        for i, doc in enumerate(docs.values(), 1):
            redacted, mapping = pseudonymize(doc["text"], run[doc["id"]]["entities"])
            original = ask(client, doc["text"], args.task)
            restored = restore(ask(client, redacted, args.task), mapping)
            if args.task == "record":
                original, restored = json.loads(original), json.loads(restored)
            row = {"id": doc["id"], "redacted": redacted, "original": original,
                   "restored": restored}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"{i}/{len(docs)}")

    print()
    if args.task == "record":
        score_record(rows)
    else:
        score_reply(rows, docs)


if __name__ == "__main__":
    main()
