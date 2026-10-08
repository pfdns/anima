"""
Anima - AniList + HiAnime CLI
"""
import sys

from anilist_client import AniListClient
from formatter import format_anime, print_anime
from hianime_mapper import HiAnimeMapper
from hianime_client import HiAnimeClient


PROXY = "http://127.0.0.1:2080"


def pick_anime(anilist: AniListClient, query: str):
    """جستجو تو AniList و انتخاب از بین نتایج"""
    print(f"\n{'='*60}")
    print(f"  📺 AniList Search: {query}")
    print(f"{'='*60}\n")

    results = anilist.search_anime_list(query, limit=15)
    if not results:
        print("  ❌ Not found on AniList.")
        return None

    for i, r in enumerate(results, 1):
        title = r["title"].get("english") or r["title"].get("romaji")
        fmt = r.get("format", "?")
        year = r.get("seasonYear", "?")
        eps = r.get("episodes", "?")
        status = r.get("status", "?")
        print(f"  [{i:>2}] {title}")
        print(f"       {fmt} | {year} | {eps} eps | {status} | AniList ID: {r['id']}")

    print()
    try:
        choice = input("  Select anime number (or q to quit): ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if choice.lower() in ("q", "quit", ""):
        return None

    if not choice.isdigit() or not (1 <= int(choice) <= len(results)):
        print("  ❌ Invalid choice.")
        return None

    return results[int(choice) - 1]["id"]


def pick_episode(episodes: list):
    """نمایش اپیزودها و انتخاب"""
    print(f"\n{'='*60}")
    print(f"  📋 Episodes")
    print(f"{'='*60}\n")

    for ep in episodes[:30]:
        print(f"    [{ep['number']:>3}] {ep['title']}")
    if len(episodes) > 30:
        print(f"    ... and {len(episodes) - 30} more")

    print()
    try:
        ep_choice = input("  Select episode number (or q to quit): ").strip()
    except (KeyboardInterrupt, EOFError):
        return None

    if ep_choice.lower() in ("q", "quit", ""):
        return None

    return next((e for e in episodes if str(e["number"]) == ep_choice), None)


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 main.py "anime name"')
        print('Example: python3 main.py "jujutsu kaisen"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    anilist = AniListClient()

    # ===== ۱. انتخاب انیمه از AniList =====
    anilist_id = pick_anime(anilist, query)
    if not anilist_id:
        return

    # ===== ۲. اطلاعات کامل =====
    print(f"\n{'='*60}")
    print(f"  📺 AniList Info (ID: {anilist_id})")
    print(f"{'='*60}\n")

    media = anilist.get_anime_by_id(anilist_id)
    if not media:
        print("  ❌ Could not fetch anime info.")
        return

    info = format_anime(media)
    print_anime(info)

    # ===== ۳. Mapping به HiAnime =====
    print(f"\n{'='*60}")
    print(f"  🔗 Mapping to HiAnime...")
    print(f"{'='*60}\n")

    mapper = HiAnimeMapper(proxy=PROXY)
    try:
        mapped = mapper.map_anilist_to_hianime(anilist_id)
    except Exception as e:
        print(f"  ❌ Mapping failed: {e}")
        return

    hianime_id = mapped["hianimeId"]
    episodes = mapped["episodes"]

    print(f"  ✅ HiAnime ID: {hianime_id}")
    print(f"  ✅ Episodes: {len(episodes)}")

    # ===== ۴. انتخاب اپیزود =====
    ep = pick_episode(episodes)
    if not ep:
        return

    # ===== ۵. گرفتن m3u8 =====
    print(f"\n{'='*60}")
    print(f"  🎥 Getting stream for Episode {ep['number']}...")
    print(f"{'='*60}\n")

    client = HiAnimeClient(proxy=PROXY)
    try:
        result = client.get_m3u8(hianime_id, str(ep["number"]))
        print(f"  ✅ m3u8: {result['m3u8']}")
        print(f"  📝 Referer: {result['referer']}")
        if result["subtitles"]:
            print(f"\n  💬 Subtitles ({len(result['subtitles'])}):")
            for sub in result["subtitles"]:
                print(f"     - {sub['label']}")
    except Exception as e:
        print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    main()
