"""
Translate Episode - ترجمه زیرنویس با Hy-MT2 و context از glossary
"""
import os
import sys
import json
import re
import time
import argparse
import requests
from pathlib import Path


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "hy-mt2"
GLOSSARY_DIR = "glossaries"
SUBTITLE_DIR = "subtitles"
OUTPUT_DIR = "output"


def translate(text, context=None, max_retries=3, num_ctx=8192):
    """ترجمه یه متن با Hy-MT2"""
    if not text.strip():
        return ""

    if context:
        prompt = f"""Context (use this for consistency of names and terms):
{context}

Translate the following English text to Persian. Only output the translation, nothing else.

Text:
{text}"""
    else:
        prompt = f"""Translate the following English text to Persian. Only output the translation, nothing else.

Text:
{text}"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "top_p": 0.6,
            "top_k": 20,
            "repeat_penalty": 1.05,
            "num_predict": 4096,
            "num_ctx": num_ctx,
        },
    }

    for attempt in range(max_retries):
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=600)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except requests.exceptions.Timeout:
            print(f"    ⚠️ Timeout (attempt {attempt+1})")
            time.sleep(3)
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️ Error: {e}")
            time.sleep(3)
    return None


def check_ollama():
    """چک کن Ollama و مدل در دسترسن"""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if not any(MODEL in m for m in models):
            print(f"❌ Model '{MODEL}' not found. Available: {models}")
            return False
        print(f"✅ Model '{MODEL}' is available")
        return True
    except Exception as e:
        print(f"❌ Ollama not reachable: {e}")
        return False


def build_translated_glossary(anilist_id):
    """Glossary رو می‌خونه و بخش‌های مهمش رو به فارسی ترجمه می‌کنه"""
    path = os.path.join(GLOSSARY_DIR, f"{anilist_id}_en.json")
    if not os.path.exists(path):
        print(f"❌ Glossary not found: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n📚 Building translated glossary for: {data['title'].get('romaji')}")

    translated = {
        "title": {},
        "genres": {},
        "characters": {},
        "tags": {},
        "studios": [],
        "description": "",
    }

    # عنوان
    title_en = data["title"].get("english") or data["title"].get("romaji")
    print(f"\n📌 Title: {title_en}")
    translated["title"]["en"] = title_en
    translated["title"]["fa"] = translate(title_en) or title_en
    print(f"   → {translated['title']['fa']}")

    # ژانرها
    for g in data.get("genres", []):
        fa = translate(g) or g
        translated["genres"][g] = fa
        print(f"   Genre: {g} → {fa}")

    # کاراکترها (فقط MAIN و SUPPORTING، حداکثر ۲۰ تا)
    chars = data.get("characters", [])[:20]
    print(f"\n📌 Characters ({len(chars)}):")
    for c in chars:
        name = c.get("name_full")
        if not name:
            continue
        fa = translate(name) or name
        translated["characters"][name] = fa
        print(f"   {name} → {fa}")

    # تگ‌ها (فقط ۱۵ تای اول)
    tags = data.get("tags", [])[:15]
    print(f"\n📌 Tags ({len(tags)}):")
    for t in tags:
        name = t.get("name")
        if not name:
            continue
        fa = translate(name) or name
        translated["tags"][name] = fa
        print(f"   {name} → {fa}")

    # استودیوها
    for s in data.get("studios", []):
        translated["studios"].append(s)

    # ذخیره
    out_path = os.path.join(OUTPUT_DIR, f"{anilist_id}_glossary_fa.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved translated glossary: {out_path}")

    return translated


def build_context(translated_glossary):
    """از glossary ترجمه‌شده یه متن context می‌سازه"""
    lines = []

    if translated_glossary.get("title", {}).get("fa"):
        lines.append(f"Anime: {translated_glossary['title']['en']} → {translated_glossary['title']['fa']}")

    if translated_glossary.get("characters"):
        lines.append("\nCharacters:")
        for en, fa in translated_glossary["characters"].items():
            lines.append(f"  {en} → {fa}")

    if translated_glossary.get("genres"):
        lines.append("\nGenres:")
        for en, fa in translated_glossary["genres"].items():
            lines.append(f"  {en} → {fa}")

    if translated_glossary.get("tags"):
        lines.append("\nKey terms:")
        for en, fa in translated_glossary["tags"].items():
            lines.append(f"  {en} → {fa}")

    return "\n".join(lines)


def translate_srt(srt_content, context):
    """زیرنویس SRT رو خط به خط ترجمه می‌کنه"""
    print("\n" + "=" * 60)
    print("🎬 Translating subtitle")
    print("=" * 60)

    blocks = re.split(r"\n\s*\n", srt_content.strip())
    translated_blocks = []

    for i, block in enumerate(blocks, 1):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            translated_blocks.append(block)
            continue

        index = lines[0]
        timing = lines[1]
        text = "\n".join(lines[2:])

        print(f"\n[{i}/{len(blocks)}] {text[:60]}...")
        translated = translate(text, context=context)
        if translated:
            print(f"   → {translated[:60]}...")
        else:
            translated = text
            print("   ⚠️ Translation failed, keeping original")

        translated_blocks.append(f"{index}\n{timing}\n{translated}")

    return "\n\n".join(translated_blocks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("anilist_id", type=int)
    parser.add_argument("--subtitle", required=True, help="Path to English SRT")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    if not check_ollama():
        sys.exit(1)

    # مرحله ۱: Glossary ترجمه‌شده
    glossary_fa = build_translated_glossary(args.anilist_id)
    if not glossary_fa:
        sys.exit(1)

    # مرحله ۲: Context
    context = build_context(glossary_fa)
    ctx_path = os.path.join(OUTPUT_DIR, "context.txt")
    with open(ctx_path, "w", encoding="utf-8") as f:
        f.write(context)
    print(f"\n💾 Saved context: {ctx_path}")

    # مرحله ۳: خوندن زیرنویس
    if not os.path.exists(args.subtitle):
        print(f"❌ Subtitle not found: {args.subtitle}")
        sys.exit(1)
    with open(args.subtitle, "r", encoding="utf-8") as f:
        srt = f.read()
    print(f"📄 Loaded subtitle: {args.subtitle} ({len(srt)} chars)")

    # مرحله ۴: ترجمه
    translated = translate_srt(srt, context)

    # مرحله ۵: ذخیره
    out = args.output or os.path.join(OUTPUT_DIR, "episode_fa.srt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(translated)
    print(f"\n💾 Saved translated subtitle: {out}")

    print("\n" + "=" * 60)
    print("✅ DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
