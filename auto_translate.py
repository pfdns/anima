"""
Auto Translate - با Qwen 2.5 7B
"""
import os
import sys
import json
import re
import time
import argparse
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-7b"
SUBTITLE_DIR = "subtitles"
OUTPUT_DIR = "output"


def translate(text, max_retries=2):
    """ترجمه با Qwen 2.5 - پرامپت ساده و مستقیم"""
    if not text or not text.strip():
        return ""

    # پرامپت chat-style برای Qwen
    prompt = f"""<|im_start|>system
You are a professional English-to-Persian subtitle translator. Translate naturally and conversationally. Only output the translation, nothing else.
<|im_end|>
<|im_start|>user
Translate this to Persian: {text}
<|im_end|>
<|im_start|>assistant
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.1,
            "num_predict": 512,
            "num_ctx": 2048,
            "stop": ["<|im_end|>", "<|im_start|>", "\n\n"],
        },
    }

    for attempt in range(max_retries):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            result = r.json().get("response", "").strip()

            # پاکسازی
            result = result.split("\n")[0].strip()
            result = re.sub(r"^(Persian|Farsi|Translation|ترجمه)[:\s]*", "", result, flags=re.IGNORECASE)
            result = result.strip()

            if len(result) > len(text) * 5:
                return text

            return result

        except Exception as e:
            print(f"    ⚠️ Error: {e}")
            time.sleep(2)

    return text


def check_ollama():
    for i in range(20):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if any(MODEL in m for m in models):
                print(f"✅ Model '{MODEL}' ready")
                return True
        except Exception:
            pass
        print(f"⏳ Waiting for Ollama... ({i+1}/20)")
        time.sleep(5)
    return False


def convert_vtt_to_srt(vtt_content):
    if not vtt_content.strip().startswith("WEBVTT"):
        return vtt_content

    lines = vtt_content.split("\n")
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip() == "":
            start_idx = i + 1
            break
    lines = lines[start_idx:]

    output = []
    counter = 1
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if "-->" in line:
            timing = line.replace(".", ",")
            output.append(str(counter))
            output.append(timing)
            counter += 1
            i += 1
            while i < len(lines) and lines[i].strip():
                output.append(lines[i].strip())
                i += 1
            output.append("")
        else:
            i += 1
    return "\n".join(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("anilist_id", type=int)
    parser.add_argument("--episode", type=int, default=6)
    args = parser.parse_args()

    anilist_id = args.anilist_id
    episode_num = args.episode

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)

    if not check_ollama():
        sys.exit(1)

    from hianime_mapper import HiAnimeMapper
    from hianime_client import HiAnimeClient

    print(f"\n🔗 Mapping to HiAnime...")
    mapper = HiAnimeMapper()
    mapped = mapper.map_anilist_to_hianime(anilist_id)
    hianime_id = mapped["hianimeId"]
    episodes = mapped["episodes"]

    ep = next((e for e in episodes if str(e["number"]) == str(episode_num)), None)
    if not ep:
        print(f"❌ Episode {episode_num} not found")
        sys.exit(1)
    print(f"✅ Episode {episode_num}: {ep['title']}")

    client = HiAnimeClient()
    sub_info = client.get_english_subtitle_url(hianime_id, str(episode_num))
    if not sub_info:
        print("❌ No English subtitle found")
        sys.exit(1)

    print(f"✅ Found: {sub_info['label']}")

    sub_path = os.path.join(SUBTITLE_DIR, f"episode_{episode_num}_en.srt")
    if not client.download_subtitle(sub_info["url"], sub_path, referer=sub_info["referer"]):
        print("❌ Download failed")
        sys.exit(1)

    with open(sub_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if content.strip().startswith("WEBVTT"):
        content = convert_vtt_to_srt(content)
        with open(sub_path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ Subtitle: {len(content)} chars")

    # ترجمه - فقط ۲۰ بلاک اول تست
    blocks = re.split(r"\n\s*\n", content.strip())
    translated_blocks = []
    TEST_LIMIT = 20

    print(f"\n🎬 Translating (test: {TEST_LIMIT} blocks)...")
    for i, block in enumerate(blocks, 1):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            translated_blocks.append(block)
            continue

        index = lines[0]
        timing = lines[1]
        text = "\n".join(lines[2:])

        if i <= TEST_LIMIT:
            translated = translate(text)
            print(f"[{i}] {text[:40]} → {translated[:40]}")
        else:
            translated = text

        translated_blocks.append(f"{index}\n{timing}\n{translated}")

        if i >= TEST_LIMIT:
            break

    out_path = os.path.join(OUTPUT_DIR, f"episode_{episode_num}_fa.srt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(translated_blocks))
    print(f"\n💾 Saved: {out_path}")


if __name__ == "__main__":
    main()
