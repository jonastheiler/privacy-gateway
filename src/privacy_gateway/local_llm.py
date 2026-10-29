"""Client for the local LLM server: plain HTTP against llama.cpp's OpenAI-compatible API."""

import sys
import time

import requests

URL = "http://localhost:8080/v1/chat/completions"


def chat(prompt: str, system: str = "", max_tokens: int = 512) -> dict:
    """Send one prompt and return the answer with its latency numbers."""
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    body = {
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        # Qwen3 "thinks" before answering by default; that costs many tokens on a CPU.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    start = time.perf_counter()
    response = requests.post(URL, json=body, timeout=600)
    response.raise_for_status()
    data = response.json()
    timings = data["timings"]  # llama.cpp extension, not part of the OpenAI format
    return {
        "text": data["choices"][0]["message"]["content"],
        "seconds": time.perf_counter() - start,
        "prompt_tokens": timings["prompt_n"],
        "output_tokens": timings["predicted_n"],
        "prompt_tokens_per_s": timings["prompt_per_second"],
        "output_tokens_per_s": timings["predicted_per_second"],
    }


if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "Name three Swiss cantons."
    result = chat(prompt)
    print(result["text"])
    print(
        f"\n{result['seconds']:.1f} s | prompt {result['prompt_tokens']} tokens "
        f"at {result['prompt_tokens_per_s']:.0f}/s | output {result['output_tokens']} "
        f"tokens at {result['output_tokens_per_s']:.1f}/s"
    )
