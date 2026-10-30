# privacy-gateway

**Can a small LLM running on a CPU strip personal data from text before it goes to a cloud
LLM, and what does that cost in privacy, answer quality and speed?**

Work in progress. The plan:

1. **Local server:** llama.cpp in Docker, capped at 4 CPUs and 4 GB RAM like a small
   on-prem box, serving a quantized Qwen3 model over an OpenAI-compatible API.
2. **Data:** synthetic Swiss documents (emails, invoices, notes) with planted names, AHV
   numbers, IBANs, addresses and phone numbers, so the labels come for free.
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

Another model or quantization: `MODEL=unsloth/Qwen3-4B-GGUF:Q4_K_M docker compose up -d`.

```
uv run python -m privacy_gateway.data             # writes data/docs.jsonl (240 documents)
uv run python -m privacy_gateway.evaluate regex   # privacy and utility of a redaction method

uv run python -m privacy_gateway.llm_redact qwen3-1.7b-q4 --limit 10   # 10 documents per kind
uv run python -m privacy_gateway.evaluate qwen3-1.7b-q4 --plus-regex
```

Add `--no-grammar` to `llm_redact` to let the model answer without a JSON schema.

## Results so far

An entity counts as **protected** if its identifying part is gone from the redacted text:
the surname for a person, street and number for an address, the digits for numbers (so a
reformatted IBAN still counts as leaked). **Facts kept** are non-personal values such as
amounts, dates and order numbers that the cloud LLM still needs.

80 documents, 10 of each kind, Qwen3 at Q4 on 4 CPUs. **Grammar** means llama.cpp gets a
JSON schema and masks every token that would break it; "+ regex" runs the regex after the LLM.

| entity | count | regex | 1.7B, no grammar | 1.7B | 1.7B + regex | 4B | 4B + regex |
|---|---|---|---|---|---|---|---|
| PERSON | 90 | 0.0% | 28.9% | 75.6% | 97.8% | 84.4% | 100.0% |
| AHV | 30 | 100.0% | 20.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| IBAN | 50 | 100.0% | 44.0% | 80.0% | 100.0% | 100.0% | 100.0% |
| PHONE | 50 | 100.0% | 22.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| EMAIL | 30 | 100.0% | 40.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| ADDRESS | 50 | 52.0% | 46.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| all | 300 | 62.0% | 33.3% | 89.3% | 99.3% | 95.3% | 100.0% |
| facts kept | 140 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| valid JSON | | | 32.5% | 100.0% | 100.0% | 100.0% | 100.0% |
| seconds per document (median) | | | 5.1 | 4.8 | 4.8 | 12.2 | 12.2 |

- **Regex** is perfect on numbers with a fixed format and fails on names and on streets
  without a typical suffix ("Im Gässli 4"). On all 240 documents it protects 62.2%.
- **Without the grammar** two answers in three are not valid JSON, so nothing is found and
  the whole document leaks. With it every answer parses, at no extra cost in speed.
- **LLM and regex complement each other.** The model finds full names ("Laura Graf") but
  misses later mentions such as "Frau Graf"; the regex catches exactly those. What still
  leaks are names without a title in an unexpected role ("Als Referenz wurde Beat Koch
  angegeben").
- **The 4B model** fixes those semantic misses (referees, every IBAN) but still skips
  "Herr Rossi" after the full name; with the regex it protects all 300 entities, at 2.5
  times the latency of the 1.7B model.
