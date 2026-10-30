"""Round trip: the cloud LLM works on pseudonymized text and the placeholders are mapped back.

Each document goes to the cloud twice, once original and once pseudonymized by a local LLM
run. The task is a case record with the facts a back office needs. Utility is how often the
restored answer from the redacted text equals the answer from the original text.
"""

import argparse
import json

import anthropic

from privacy_gateway.data import load_docs
from privacy_gateway.llm_redact import RUNS_DIR, load_run, pseudonymize

MODEL = "claude-opus-5-5"
FIELDS = ["name", "amount", "date", "iban", "phone", "email", "address"]

SYSTEM = (
    "Du erfasst Dokumente für ein Schweizer Backoffice. Gib für die Person, um die es geht, "
    "Name, Betrag, Datum, IBAN, Telefon, E-Mail und Adresse an, jeweils genau so geschrieben "
    "wie im Text. Platzhalter wie <PERSON_1> stehen für echte Werte: übernimm sie unverändert. "
    'Fehlt ein Wert, gib "" an.'
)
# Structured outputs: the API constrains the answer to this schema, like the grammar locally.
SCHEMA = {
    "type": "object",
    "properties": {field: {"type": "string"} for field in FIELDS},
    "required": FIELDS,
    "additionalProperties": False,
}


def ask(client: anthropic.Anthropic, text: str) -> dict:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": text}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        # If a safety classifier declines, the API reruns the request on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        return dict.fromkeys(FIELDS, "")
    return json.loads(next(b.text for b in response.content if b.type == "text"))


def restore(answer: dict, mapping: dict) -> dict:
    """Put the real values back where the cloud LLM copied a placeholder."""
    restored = {}
    for field, value in answer.items():
        for placeholder, original in mapping.items():
            value = value.replace(placeholder, original)
        restored[field] = value
    return restored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="local LLM run in data/runs, e.g. qwen3-1.7b-q4")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    run = load_run(args.run)
    docs = [doc for doc in load_docs() if doc["id"] in run]
    rows = []
    with (RUNS_DIR / f"cloud-{args.run}.jsonl").open("w", encoding="utf-8") as f:
        for i, doc in enumerate(docs, 1):
            redacted, mapping = pseudonymize(doc["text"], run[doc["id"]]["entities"])
            row = {"id": doc["id"], "redacted": redacted, "original": ask(client, doc["text"])}
            row["restored"] = restore(ask(client, redacted), mapping)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            rows.append(row)
            print(f"{i}/{len(docs)}")

    print(f"\n{'field':<10}{'same answer':>12}")
    for field in FIELDS:
        same = sum(row["restored"][field] == row["original"][field] for row in rows)
        print(f"{field:<10}{same / len(rows):>12.1%}")
    same = sum(row["restored"] == row["original"] for row in rows)
    print(f"{'all':<10}{same / len(rows):>12.1%}  (documents with every field the same)")


if __name__ == "__main__":
    main()
