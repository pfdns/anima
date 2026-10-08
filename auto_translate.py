"""
Auto Translate - ترجمه خودکار یه اپیزود با Hy-MT2
Usage: python3 auto_translate.py <anilist_id> [--episode N]
"""
import os
import sys
import json
import re
import time
import argparse
import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "hy-mt2"
SUBTITLE_DIR = "subtitles"
OUTPUT_DIR = "output"


def translate(text, max_retries=2):
    """ترجمه ساده با Hy-MT2"""
    if not text or not text.strip():
        return ""

    prompt = f"Translate to Persian:\n{text}"

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1,
            "top_k": 1,
            "repeat_penalty": 1.3,
            "num_predict": 512,
            "num_ctx": 512,
        },
    }

    for attempt in range(max_retries):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=180)
            r.raise_for_status()
            result = r.json().get("response", "").strip()

            # پاکسازی: حذف متن‌های اضافی
            result = re.sub(r"\n\n.*", "", result, flags=re.DOTALL)
            result = re.sub(r"^(Persian|Farsi|Translation|ترجمه)[:\s]*", "", result, flags=re.IGNORECASE)
            result = result.strip()

            # اگه خروجی خیلی طولانی بود، رد کن
            if len(result) > len(text) * 5:
                return text

            return result

        except Exception as e:
            print(f"    ⚠️ Error: {e}")
            time.sleep(2)

    return text


def check_ollama():
    """چک کن Ollama آماده‌ست"""
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
    """تبدیل VTT به SRT"""
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

    # ===== چک Ollama =====
    if not check_ollama():
        sys.exit(1)

    # ===== مپ کردن =====
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

    # ===== دانلود زیرنویس =====
    client = HiAnimeClient()
    sub_info = client.get_english_subtitle_url(hianime_id, str(episode_num))
    if not sub_info:
        print("❌ No English subtitle found")
        sys.exit(1)

    print(f"✅ Found English subtitle: {sub_info['label']}")

    sub_path = os.path.join(SUBTITLE_DIR, f"episode_{episode_num}_en.srt")
    print(f"\n⬇️  Downloading subtitle...")

    # ✅ اینجا درست شد: URL و referer جدا پاس داده می‌شن
    if not client.download_subtitle(sub_info["url"], sub_path, referer=sub_info["referer"]):
        print("❌ Subtitle download failed")
        sys.exit(1)

    with open(sub_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    if content.strip().startswith("WEBVTT"):
        print("🔄 Converting VTT to SRT...")
        content = convert_vtt_to_srt(content)
        with open(sub_path, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"✅ Subtitle saved: {sub_path} ({len(content)} chars)")

    # ===== ترجمه زیرنویس =====
    print(f"\n" + "=" * 60)
    print(f"🎬 Translating subtitle")
    print(f"=" * 60)

    blocks = re.split(r"\n\s*\n", content.strip())
    translated_blocks = []

    # فقط ۳۰ بلاک اول رو ترجمه کن (تست)
    TEST_LIMIT = 30

    for i, block in enumerate(blocks, 1):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            translated_blocks.append(block)
            continue

        index = lines[0]
        timing = lines[1]
        text = "\n".join(lines[2:])

        print(f"[{i}/{len(blocks)}] {text[:50]}")

        if i <= TEST_LIMIT:
            translated = translate(text)
            print(f"   → {translated[:50]}")
        else:
            translated = text

        translated_blocks.append(f"{index}\n{timing}\n{translated}")

        if i >= TEST_LIMIT:
            print(f"\n⏸️  Stopped after {TEST_LIMIT} blocks (test mode)")
            break

    out_path = os.path.join(OUTPUT_DIR, f"episode_{episode_num}_fa.srt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(translated_blocks))
    print(f"\n💾 Saved: {out_path}")

    print("\n" + "=" * 60)
    print("✅ DONE (test mode)")
    print("=" * 60)


if __name__ == "__main__":
    main()
