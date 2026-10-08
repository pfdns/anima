"""
Auto Translate - ترجمه خودکار یه اپیزود با Qwen 2.5
Usage: python3 auto_translate.py <anilist_id> --episode <num>
"""
import os
import sys
import json
import re
import time
import argparse
import requests
from pathlib import Path

from anilist_client import AniListClient
from glossary_builder import build_and_save, load_glossary, build_glossary_text
from hianime_mapper import HiAnimeMapper
from hianime_client import HiAnimeClient


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-7b"
GLOSSARY_DIR = "glossaries"
SUBTITLE_DIR = "subtitles"
OUTPUT_DIR = "output"


def translate(text, context=None, max_retries=3, num_ctx=8192):
    """ترجمه یه متن با Qwen 2.5"""
    if not text.strip():
        return ""

    if context:
        prompt = f"""You are a professional subtitle translator. Translate the following English subtitle line to Persian (Farsi).

CONTEXT (use for consistent translation of names and terms):
{context}

RULES:
- Output ONLY the Persian translation
- Do NOT explain, do NOT add alternatives, do NOT chat
- Keep character names as they are
- For sound effects, translate naturally

English: {text}
Persian:"""
    else:
        prompt = f"""You are a professional subtitle translator. Translate the following English subtitle line to Persian (Farsi).

RULES:
- Output ONLY the Persian translation
- Do NOT explain, do NOT add alternatives, do NOT chat

English: {text}
Persian:"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.05,
            "num_predict": 512,
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
    """چک کن Ollama و مدل آماده‌ست"""
    for i in range(30):
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if any(MODEL in m for m in models):
                print(f"✅ Model '{MODEL}' is ready")
                return True
            print(f"⏳ Waiting for model... ({i+1}/30)")
            time.sleep(5)
        except Exception:
            print(f"⏳ Waiting for Ollama... ({i+1}/30)")
            time.sleep(5)
    print(f"❌ Model '{MODEL}' not found after waiting")
    return False


def build_translated_glossary(anilist_id):
    """Glossary رو ترجمه می‌کنه"""
    data = load_glossary(anilist_id)
    if not data:
        print(f"❌ Glossary not found for {anilist_id}")
        return None

    print(f"\n📚 Translating glossary for: {data['title'].get('romaji')}")

    translated = {
        "title": {},
        "genres": {},
        "characters": {},
        "tags": {},
        "studios": data.get("studios", []),
    }

    title_en = data["title"].get("english") or data["title"].get("romaji")
    translated["title"]["en"] = title_en
    translated["title"]["fa"] = translate(title_en) or title_en
    print(f"  Title: {title_en} → {translated['title']['fa']}")

    for g in data.get("genres", []):
        fa = translate(g) or g
        translated["genres"][g] = fa
        print(f"  Genre: {g} → {fa}")

    chars = data.get("characters", [])[:20]
    print(f"\n  Characters ({len(chars)}):")
    for c in chars:
        name = c.get("name_full")
        if not name:
            continue
        fa = translate(name) or name
        translated["characters"][name] = fa
        print(f"    {name} → {fa}")

    tags = data.get("tags", [])[:15]
    print(f"\n  Tags ({len(tags)}):")
    for t in tags:
        name = t.get("name")
        if not name:
            continue
        fa = translate(name) or name
        translated["tags"][name] = fa
        print(f"    {name} → {fa}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{anilist_id}_glossary_fa.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Saved translated glossary: {out_path}")

    return translated


def build_context(translated_glossary):
    """ساخت context از glossary ترجمه‌شده"""
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


def translate_srt(srt_content, context):
    """ترجمه SRT خط به خط"""
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
    parser.add_argument("--season", type=int, default=1)
    parser.add_argument("--episode", type=int, default=6)
    args = parser.parse_args()

    anilist_id = args.anilist_id
    episode_num = args.episode

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(SUBTITLE_DIR, exist_ok=True)

    if not check_ollama():
        sys.exit(1)

    print(f"\n📥 Building glossary for AniList ID {anilist_id}...")
    data = build_and_save(anilist_id)
    if not data:
        print("❌ Glossary build failed")
        sys.exit(1)

    print(f"\n🔗 Mapping to HiAnime...")
    mapper = HiAnimeMapper()
    try:
        mapped = mapper.map_anilist_to_hianime(anilist_id)
    except Exception as e:
        print(f"❌ Mapping failed: {e}")
        sys.exit(1)

    hianime_id = mapped["hianimeId"]
    episodes = mapped["episodes"]
    print(f"✅ HiAnime ID: {hianime_id}")
    print(f"✅ Episodes: {len(episodes)}")

    ep = next((e for e in episodes if str(e["number"]) == str(episode_num)), None)
    if not ep:
        print(f"❌ Episode {episode_num} not found")
        sys.exit(1)
    print(f"✅ Episode {episode_num}: {ep['title']}")

    client = HiAnimeClient()
    sub_url = client.get_english_subtitle_url(hianime_id, str(episode_num))
    if not sub_url:
        print("❌ No English subtitle found")
        sys.exit(1)

    sub_path = os.path.join(SUBTITLE_DIR, f"episode_{episode_num}_en.srt")
    print(f"\n⬇️  Downloading subtitle...")
    if not client.download_subtitle(sub_url, sub_path):
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

    glossary_fa = build_translated_glossary(anilist_id)
    if not glossary_fa:
        sys.exit(1)

    context = build_context(glossary_fa)
    ctx_path = os.path.join(OUTPUT_DIR, "context.txt")
    with open(ctx_path, "w", encoding="utf-8") as f:
        f.write(context)
    print(f"💾 Saved context: {ctx_path}")

    translated = translate_srt(content, context)

    out_path = os.path.join(OUTPUT_DIR, f"episode_{episode_num}_fa.srt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(translated)
    print(f"\n💾 Saved translated subtitle: {out_path}")

    print("\n" + "=" * 60)
    print("✅ DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
