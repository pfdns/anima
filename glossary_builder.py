"""
Glossary Builder - ساخت Glossary خودکار از AniList
"""
import json
import os
import re
from typing import Optional, Dict, Any

from anilist_client import AniListClient


GLOSSARY_DIR = os.path.join(os.path.dirname(__file__), "glossaries")


def ensure_dir():
    os.makedirs(GLOSSARY_DIR, exist_ok=True)


def clean_text(text: Optional[str]) -> str:
    """پاکسازی متن"""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_glossary_data(anilist_id: int) -> Optional[Dict[str, Any]]:
    """استخراج داده خام Glossary از AniList"""
    client = AniListClient()
    media = client.get_anime_by_id(anilist_id)
    if not media:
        return None

    # --- Tags (فقط rank >= 60) ---
    tags = []
    for t in media.get("tags", []) or []:
        if t.get("rank", 0) >= 60:
            tags.append({
                "name": t.get("name"),
                "description": clean_text(t.get("description")),
                "rank": t.get("rank"),
                "category": t.get("category"),
            })
    tags.sort(key=lambda x: -x["rank"])

    # --- Characters (فقط MAIN و SUPPORTING) ---
    characters = []
    for edge in (media.get("characters") or {}).get("edges", []) or []:
        role = edge.get("role", "")
        if role not in ("MAIN", "SUPPORTING"):
            continue
        node = edge.get("node") or {}
        name = node.get("name") or {}
        desc = clean_text(node.get("description"))
        characters.append({
            "name_full": name.get("full"),
            "name_native": name.get("native"),
            "role": role,
            "description": desc,
        })

    # --- Relations ---
    relations = []
    for edge in (media.get("relations") or {}).get("edges", []) or []:
        rel_type = edge.get("relationType", "")
        node = edge.get("node") or {}
        title = node.get("title") or {}
        relations.append({
            "relation_type": rel_type,
            "title": title.get("english") or title.get("romaji"),
            "format": node.get("format"),
            "year": node.get("seasonYear"),
        })

    # --- Studios ---
    studios = [
        s.get("name")
        for s in (media.get("studios") or {}).get("nodes", []) or []
    ]

    return {
        "anilist_id": anilist_id,
        "id_mal": media.get("idMal"),
        "title": {
            "romaji": (media.get("title") or {}).get("romaji"),
            "english": (media.get("title") or {}).get("english"),
            "native": (media.get("title") or {}).get("native"),
        },
        "description": clean_text(media.get("description")),
        "genres": media.get("genres", []) or [],
        "format": media.get("format"),
        "season_year": media.get("seasonYear"),
        "episodes": media.get("episodes"),
        "studios": studios,
        "tags": tags,
        "characters": characters,
        "relations": relations,
    }


def build_glossary_text(data: Dict[str, Any]) -> str:
    """ساخت متن Glossary انگلیسی"""
    lines = []
    lines.append(f"=== GLOSSARY: {data['title'].get('romaji')} ===")
    lines.append("")

    if data.get("description"):
        lines.append("CONTEXT:")
        lines.append(data["description"])
        lines.append("")

    if data.get("genres"):
        lines.append(f"GENRES: {', '.join(data['genres'])}")
    if data.get("format"):
        lines.append(f"FORMAT: {data['format']} ({data.get('season_year', '?')})")
    if data.get("studios"):
        lines.append(f"STUDIOS: {', '.join(data['studios'])}")
    lines.append("")

    if data.get("tags"):
        lines.append("KEY TERMS:")
        for t in data["tags"]:
            lines.append(f"- {t['name']} (rank {t['rank']}):")
            lines.append(f"  {t['description']}")
        lines.append("")

    if data.get("characters"):
        lines.append("CHARACTERS:")
        for c in data["characters"]:
            native = f" ({c['name_native']})" if c.get("name_native") else ""
            lines.append(f"- {c['name_full']}{native} [{c['role']}]:")
            lines.append(f"  {c['description'][:300]}")
        lines.append("")

    if data.get("relations"):
        lines.append("RELATIONS:")
        for r in data["relations"]:
            lines.append(
                f"- {r['relation_type']}: {r['title']} "
                f"({r.get('format', '?')}, {r.get('year', '?')})"
            )
        lines.append("")

    return "\n".join(lines)


def save_raw_glossary(anilist_id: int, data: Dict[str, Any]) -> str:
    ensure_dir()
    path = os.path.join(GLOSSARY_DIR, f"{anilist_id}_en.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_glossary(anilist_id: int) -> Optional[Dict[str, Any]]:
    path = os.path.join(GLOSSARY_DIR, f"{anilist_id}_en.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_and_save(anilist_id: int) -> Optional[Dict[str, Any]]:
    print(f"  📥 Fetching AniList data for ID: {anilist_id}")
    data = extract_glossary_data(anilist_id)
    if not data:
        print("  ❌ Could not fetch data")
        return None

    json_path = save_raw_glossary(anilist_id, data)
    print(f"  ✅ Saved: {json_path}")

    print(f"  📊 Tags: {len(data.get('tags', []))}")
    print(f"  📊 Characters: {len(data.get('characters', []))}")
    print(f"  📊 Relations: {len(data.get('relations', []))}")

    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 glossary_builder.py <anilist_id>")
        sys.exit(1)

    anilist_id = int(sys.argv[1])
    data = build_and_save(anilist_id)
    if data:
        print()
        print(build_glossary_text(data)[:2000])
