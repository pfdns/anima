"""
Hy-MT2 Client - ترجمه با Hy-MT2 1.8B از طریق Ollama
"""
import time
from typing import Optional

import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "hy-mt2:1.8b"


class HyMT2Client:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ollama_url: str = OLLAMA_URL,
        timeout: int = 300,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.timeout = timeout

    def is_available(self) -> bool:
        """چک کن Ollama و مدل در دسترس هستن"""
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            return any(self.model in m for m in models)
        except Exception:
            return False

    def translate(
        self,
        text: str,
        target_language: str = "Persian",
        context: Optional[str] = None,
        max_retries: int = 3,
    ) -> Optional[str]:
        """ترجمه یه متن با Hy-MT2"""
        if context:
            prompt = f"""Context: {context}

Translate the following text into {target_language}.
Only output the translation, no explanations.

Text:
{text}"""
        else:
            prompt = f"""Translate the following text into {target_language}.
Only output the translation, no explanations.

Text:
{text}"""

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.6,
                "top_k": 20,
                "repetition_penalty": 1.05,
                "num_predict": 4096,
            },
        }

        for attempt in range(max_retries):
            try:
                r = requests.post(
                    self.ollama_url,
                    json=payload,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                data = r.json()
                return data.get("response", "").strip()

            except requests.exceptions.Timeout:
                print(f"    ⚠️  Timeout (attempt {attempt+1})")
                time.sleep(3)
            except requests.exceptions.RequestException as e:
                print(f"    ⚠️  Error: {e}")
                time.sleep(3)

        return None


if __name__ == "__main__":
    client = HyMT2Client()

    if not client.is_available():
        print("❌ Ollama or model not available")
        print(f"   Expected model: {client.model}")
        print()
        print("To install Ollama:")
        print("  curl -fsSL https://ollama.com/install.sh | sh")
        print()
        print("To download Hy-MT2:")
        print("  ollama pull hy-mt2:1.8b")
        exit(1)

    print("✅ Ollama and model are available")
    print()

    test_text = "Don't look inside me without permission. I hate it..."
    print(f"Test: {test_text}")
    print()

    result = client.translate(test_text, context="Jujutsu Kaisen anime subtitle")
    print(f"Result: {result}")
