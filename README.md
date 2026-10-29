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
```

## Results so far

An entity counts as **protected** if its identifying part is gone from the redacted text:
the surname for a person, street and number for an address, the digits for numbers (so a
reformatted IBAN still counts as leaked). **Facts kept** are non-personal values such as
amounts, dates and order numbers that the cloud LLM still needs.

| entity | count | regex |
|---|---|---|
| PERSON | 270 | 0.0% |
| AHV | 90 | 100.0% |
| IBAN | 150 | 100.0% |
| PHONE | 150 | 100.0% |
| EMAIL | 90 | 100.0% |
| ADDRESS | 150 | 53.3% |
| all | 900 | 62.2% |
| facts kept | 420 | 100.0% |

Regular expressions are perfect on numbers with a fixed format and fail on names and on
streets without a typical suffix ("Im Gässli 4"): those need context, which is the local
LLM's job.
