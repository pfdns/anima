"""
Anima - AniList + HiAnime CLI
"""
import os
import sys

from anilist_client import AniListClient
from formatter import format_anime, print_anime
from hianime_mapper import HiAnimeMapper
from hianime_client import HiAnimeClient


PROXY = None
SUBTITLE_DIR = "subtitles"


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


def show_episode_menu(ep, result, client, hianime_id):
    """منوی اقدامات برای اپیزود انتخاب‌شده"""
    while True:
        print(f"\n{'='*60}")
        print(f"  📺 Episode {ep['number']}: {ep['title']}")
        print(f"{'='*60}\n")
        print("  What do you want to do?")
        print()
        print("    [1] Download subtitle (English)")
        print("    [2] Download video (m3u8)")
        print("    [3] Translate subtitle to Persian")
        print("    [4] Show subtitle list")
        print("    [5] Show m3u8 URL")
        print("    [0] Back to episode list")
        print()

        try:
            choice = input("  Choose an option: ").strip()
        except (KeyboardInterrupt, EOFError):
            return

        if choice == "0":
            return

        elif choice == "1":
            download_subtitle(ep, result, client)

        elif choice == "2":
            print(f"\n  🎥 m3u8 URL:")
            print(f"     {result['m3u8']}")
            print(f"  📝 Referer: {result['referer']}")
            print(f"\n  💡 Use ffmpeg or yt-dlp to download:")
            print(f"     ffmpeg -headers 'Referer: {result['referer']}' -i '{result['m3u8']}' -c copy output.mp4")

        elif choice == "3":
            translate_subtitle(ep)

        elif choice == "4":
            print(f"\n  💬 Subtitles ({len(result['subtitles'])}):")
            for i, sub in enumerate(result["subtitles"], 1):
                print(f"     [{i}] {sub['label']}")

        elif choice == "5":
            print(f"\n  🎥 m3u8: {result['m3u8']}")
            print(f"  📝 Referer: {result['referer']}")

        else:
            print("  ❌ Invalid option.")


def download_subtitle(ep, result, client):
    """دانلود زیرنویس انگلیسی"""
    subtitles = result.get("subtitles", [])
    if not subtitles:
        print("\n  ⚠️  No subtitles found.")
        return

    # اگه فقط یه زیرنویس انگلیسی هست، مستقیم دانلود کن
    english_subs = [s for s in subtitles if "english" in s["label"].lower()]

    if not english_subs:
        print("\n  ⚠️  No English subtitle found.")
        print("  Available:")
        for i, sub in enumerate(subtitles, 1):
            print(f"     [{i}] {sub['label']}")
        try:
            choice = input("  Choose subtitle number (or 0 to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not choice.isdigit() or int(choice) == 0:
            return
        idx = int(choice) - 1
        if not (0 <= idx < len(subtitles)):
            print("  ❌ Invalid.")
            return
        chosen = subtitles[idx]
    elif len(english_subs) == 1:
        chosen = english_subs[0]
    else:
        print(f"\n  💬 Multiple English subtitles found:")
        for i, sub in enumerate(english_subs, 1):
            print(f"     [{i}] {sub['label']}")
        try:
            choice = input("  Choose (or 0 to cancel): ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not choice.isdigit() or int(choice) == 0:
            return
        idx = int(choice) - 1
        if not (0 <= idx < len(english_subs)):
            print("  ❌ Invalid.")
            return
        chosen = english_subs[idx]

    # تعیین پسوند فایل از URL
    url = chosen["url"]
    ext = ".srt"
    if url.endswith(".vtt") or ".vtt" in url:
        ext = ".vtt"
    elif url.endswith(".ass") or ".ass" in url:
        ext = ".ass"

    os.makedirs(SUBTITLE_DIR, exist_ok=True)
    sub_path = os.path.join(SUBTITLE_DIR, f"episode_{ep['number']}_en{ext}")

    print(f"\n  ⬇️  Downloading: {chosen['label']}")
    print(f"     URL: {url}")
    ok = client.download_subtitle(url, sub_path)
    if ok:
        size = os.path.getsize(sub_path)
        print(f"  ✅ Saved: {sub_path} ({size} bytes)")

        # نمایش پیش‌نمایش
        print(f"\n  📄 Preview:")
        print("  " + "-" * 56)
        with open(sub_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f.readlines()[:10]:
                print(f"  {line.rstrip()}")
        print("  " + "-" * 56)
    else:
        print(f"  ❌ Failed to download subtitle")


def translate_subtitle(ep):
    """ترجمه زیرنویس با Hy-MT2 (فعلاً placeholder)"""
    print("\n  🚧 Translation not implemented yet.")
    print("  (This will use Hy-MT2 via Ollama with glossary context)")


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 main.py "anime name"')
        print('Example: python3 main.py "jujutsu kaisen"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    anilist = AniListClient()

    # ===== ۱. انتخاب انیمه =====
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

    # ===== ۳. Mapping =====
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

    # ===== ۴. حلقه‌ی انتخاب اپیزود =====
    while True:
        ep = pick_episode(episodes)
        if not ep:
            return

        # ===== ۵. گرفتن m3u8 + زیرنویس‌ها =====
        print(f"\n{'='*60}")
        print(f"  🎥 Getting stream for Episode {ep['number']}...")
        print(f"{'='*60}\n")

        client = HiAnimeClient(proxy=PROXY)
        try:
            result = client.get_m3u8(hianime_id, str(ep["number"]))
            print(f"  ✅ m3u8: {result['m3u8']}")
            print(f"  📝 Referer: {result['referer']}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

        # ===== ۶. منوی اقدامات =====
        show_episode_menu(ep, result, client, hianime_id)


if __name__ == "__main__":
    main()
