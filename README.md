# privacy-gateway

**Can a small LLM running on a CPU strip personal data from text before it goes to a cloud
LLM, and what does that cost in privacy, answer quality and speed?**

**Short answer: yes, on these documents.** Qwen3-1.7B (Q4) followed by a regex protects
99.3% of 300 planted entities at under 5 s per document on 4 CPUs. On the text the 1.7B
model pseudonymized, a cloud LLM keeps every fact once the placeholders are mapped back; the
one cost is that a reply can no longer say "Frau Graf", because `<PERSON_1>` hides the
gender. The documents come from only 8 templates, so this shows the approach works, not how
well it generalizes.

## Example

A real document from the data (id 210), followed through each step of the 1.7B Q4 run.

**1. The original stays on your machine:**

```
Bitte Lukas Keller zurückrufen, es geht um die Bestellung 3712808082 über CHF 7'418.50.
Rückruf an 041 240 51 65. Die Rückzahlung soll auf CH7885816662419202001 gehen.
```

**2. The local model only lists what it finds:**

```json
{"PERSON": ["Lukas Keller"], "AHV": [], "IBAN": ["CH7885816662419202001"],
 "PHONE": ["041 240 51 65"], "EMAIL": [], "ADDRESS": []}
```

**3. Plain code swaps the values, and only this text goes to the cloud.** Personal data is
gone, while the order number and amount that the task needs remain:

```
Bitte <PERSON_1> zurückrufen, es geht um die Bestellung 3712808082 über CHF 7'418.50.
Rückruf an <PHONE_1>. Die Rückzahlung soll auf <IBAN_1> gehen.
```

**4. Claude drafts a reply using the placeholders, and the local mapping restores the real
values:**

```
Guten Tag Lukas Keller

Vielen Dank für Ihre Nachricht. Wir haben Ihr Anliegen zur Bestellung 3712808082 über
CHF 7'418.50 erhalten. Gerne rufen wir Sie in Kürze unter der Nummer 041 240 51 65 zurück,
[...]. Die Rückzahlung erfolgt wie gewünscht auf das Konto mit der IBAN CH7885816662419202001.
```

Not every document goes this smoothly. These failures, also from the data, are why the LLM
and the regex are combined:

| failure | what stays in the text | who catches it |
|---|---|---|
| Regex can't recognize a bare name | `Bitte Lukas Keller zurückrufen` | LLM: `Bitte <PERSON_1> zurückrufen` |
| LLM misses a later mention | `Frau Graf stellte sich [...] vor` | regex: `<PERSON> stellte sich [...] vor` |
| LLM miscopies a value, adding a digit (`...4856 48`), so it is ignored | `CH39 1160 9051 8690 4856 4` | regex: `<IBAN>` |

**Two limits.** The regex's plain `<PERSON>` can't be mapped back, so the round trip below
uses the LLM alone, which protects 89.3% of entities rather than 99.3%. And only direct
identifiers are measured: in the medical note the name is hidden, but "Rückenschmerzen" still
goes to the cloud.

## How it works


1. **Local server:** llama.cpp in Docker, capped at 4 CPUs and 4 GB RAM like a small
   on-prem box, serving a quantized Qwen3 model over an OpenAI-compatible API.
2. **Data:** synthetic Swiss documents (emails, invoices, notes) with planted names, AHV
   (social security) numbers, IBANs, addresses and phone numbers, so the labels come for free.
3. **Pseudonymize:** the local model replaces each entity with a placeholder such as
   `<PERSON_1>`, compared with a regex baseline.
4. **Round trip:** the cloud LLM works on the redacted text and the placeholders are mapped
   back. Its answers on original and redacted text are compared.
5. **Measured:** recall per entity type (privacy), answer quality (utility), and latency
   per model size and quantization.

## Run it

Needs Docker and [uv](https://docs.astral.sh/uv/).

```
docker compose up -d                      # first start downloads the model (~1.1 GB)
uv run python -m privacy_gateway.local_llm "Name three Swiss cantons."
```

A run is named after the model the server runs. For another model or quantization, restart
the server with `MODEL=unsloth/Qwen3-4B-GGUF:Q4_K_M docker compose up -d` and pass a new
name, e.g. `llm_redact qwen3-4b-q4 --limit 10`.

```
uv run python -m privacy_gateway.data             # writes data/docs.jsonl (240 documents)
uv run python -m privacy_gateway.evaluate regex   # privacy and utility of a redaction method

uv run python -m privacy_gateway.llm_redact qwen3-1.7b-q4 --limit 10   # 10 documents per kind
uv run python -m privacy_gateway.evaluate qwen3-1.7b-q4 --plus-regex
```

Add `--no-grammar` to `llm_redact` to let the model answer without a JSON schema.

The round trip needs an Anthropic API key in `ANTHROPIC_API_KEY` (160 requests, about $1):

```
uv run python -m privacy_gateway.cloud record qwen3-1.7b-q4   # or: reply
```

## Results

An entity counts as **protected** if its identifying part is gone from the redacted text:
the surname for a person, street and number for an address, the digits for numbers (so a
reformatted IBAN still counts as leaked). **Facts kept** are non-personal values such as
amounts, dates and order numbers that the cloud LLM still needs.

80 documents, 10 of each kind, all models on 4 CPUs and 4 GB RAM. **Grammar** means
llama.cpp gets a JSON schema and masks every token that would break it; **+ regex** runs the
regex after the LLM. Every method kept all 140 non-personal facts.

**Caveat:** each of the 8 document kinds comes from one template, so the 80 documents are 8
sentence patterns with different values. The table compares methods on these patterns; real
documents with free wording would be harder, especially for names.

| method | PERSON (90) | AHV (30) | IBAN (50) | PHONE (50) | EMAIL (30) | ADDRESS (50) | all (300) | + regex | valid JSON | s per doc |
|---|---|---|---|---|---|---|---|---|---|---|
| regex only | 0.0% | 100% | 100% | 100% | 100% | 52.0% | 62.0% | | | |
| 1.7B Q4, no grammar | 28.9% | 20.0% | 44.0% | 22.0% | 40.0% | 46.0% | 33.3% | 75.3% | 32.5% | 5.1 |
| 0.6B Q4 | 72.2% | 83.3% | 8.0% | 60.0% | 80.0% | 92.0% | 64.7% | 98.0% | 100% | 2.2 |
| 1.7B Q4 | 75.6% | 100% | 80.0% | 100% | 100% | 100% | 89.3% | 99.3% | 100% | 4.8 |
| 1.7B Q8 | 77.8% | 100% | 98.0% | 100% | 100% | 100% | 93.0% | 100% | 100% | 9.0 |
| 4B Q4 | 84.4% | 100% | 100% | 100% | 100% | 100% | 95.3% | 100% | 100% | 12.2 |

Seconds are the median per document. Models are the Qwen3 GGUFs from
[unsloth](https://huggingface.co/unsloth); Q4 is Q4_K_M.

- **Regex** is perfect on numbers with a fixed format and fails on names and on streets
  without a typical suffix ("Im Gässli 4"). On all 240 documents it protects 62.2%.
- **Without the grammar** two answers in three are not valid JSON, so nothing is found and
  the whole document leaks. With it every answer parses, at no extra cost in speed.
- **LLM and regex complement each other.** The models find full names ("Laura Graf") but
  miss later mentions such as "Frau Graf"; the regex catches exactly those. The 1.7B Q4
  model also misses names without a title in an unexpected role ("Als Referenz wurde Beat
  Koch angegeben"); the larger runs find them.
- **Model size matters more than quantization.** 0.6B never lists an IBAN and is barely
  better than the regex alone. Q8 instead of Q4 adds 3.7 points to the 1.7B model for twice
  the latency; 4B adds 6 points for 2.5 times.
- **Best trade-off: 1.7B Q4 + regex,** 99.3% at under 5 s per document. 1.7B Q8 + regex
  and 4B + regex reach 100%.

### Round trip

Claude Opus 5.5 works on each of the 80 documents twice, once on the original and once on
the text the 1.7B model pseudonymized. Placeholders in the second answer are mapped back to
the real values and the two answers are compared.

**Task 1, case record:** extract name, amount, date, IBAN, phone, email and address.

| field | filled | hidden from the cloud | same answer |
|---|---|---|---|
| name | 80 | 80 | 100% |
| amount | 40 | 0 | 100% |
| date | 70 | 0 | 100% |
| IBAN | 50 | 40 | 100% |
| phone | 40 | 40 | 100% |
| email | 30 | 30 | 100% |
| address | 50 | 50 | 100% |

In 240 fields the cloud LLM never saw the real value: it copied `<PERSON_1>` into its
answer and the mapping restored "Laura Graf".

**Task 2, reply:** draft a short German letter to the person. Free text can't be compared
exactly, so three checks target what pseudonymization could break:

| check | original | pseudonymized |
|---|---|---|
| placeholders the cloud changed, so they can't be mapped back | | 0 of 80 |
| facts and full name of the original reply also in the restored one | | 140 of 140 |
| reply addresses the person as "Frau/Herr <surname>" | 91.2% | 15.0% |

The content survives, the courtesy doesn't. "Guten Tag Herr Müller" becomes "Guten Tag Urs
Müller", "Sehr geehrte/r Laura Graf" or "Liebe/r …", because `<PERSON_1>` hides the gender.
The 15% that keep "Frau/Herr" are all documents where the local model left "Frau Graf" in
the text: the salutation only survives where privacy failed. Gendered placeholders
(`<FRAU_1>`) would fix this at the price of revealing one bit about the person.

## Key ideas

- **Synthetic data gives labels for free** (`data.py`): the planted names and numbers (with
  valid check digits) are the ground truth, so no manual annotation is needed.
- **Constrained decoding** (`local_llm.py`): a JSON schema becomes a grammar that masks
  invalid tokens. It lifts valid JSON from 32.5% to 100% at no cost in speed.
- **The LLM finds, plain code replaces** (`llm_redact.py`): the model only lists entities;
  the replacement is deterministic, longest first, and ignores entities the model invented.
- **Reversible pseudonymization** (`cloud.py`): numbered placeholders and a mapping keep the
  cloud answer usable. Plain `<PERSON>` redaction could not be mapped back.
- **Measure leaks, not matches** (`evaluate.py`): an entity is protected only if its
  identifying part is gone, so a reformatted IBAN still counts as leaked.
- **Hybrid beats either alone:** the regex handles fixed formats, the LLM handles context.
