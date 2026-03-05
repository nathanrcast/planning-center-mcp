import os
import httpx


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = "llama3.2:3b"
EMBED_MODEL = "nomic-embed-text"
TIMEOUT = 30.0


def embed(text: str) -> list[float] | None:
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("embedding")
    except Exception:
        return None


def summarize(report_markdown: str, report_type: str) -> str | None:
    prompt = (
        f"You are a church worship team assistant. Given this {report_type} report data, "
        "write 1-2 sentences highlighting the most notable insights. Be specific and concise.\n\n"
        f"{report_markdown}"
    )
    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 256},
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip() or None
    except Exception:
        return None
