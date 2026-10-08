import re
from typing import Dict, Any


def format_anime(media: Dict[str, Any]) -> Dict[str, Any]:
    if not media:
        return {}
    title = media.get("title", {})
    start = media.get("startDate", {}) or {}
    end = media.get("endDate", {}) or {}
    studios = media.get("studios", {}).get("nodes", []) or []
    return {
        "anilist_id": media.get("id"),
        "mal_id": media.get("idMal"),
        "title_romaji": title.get("romaji"),
        "title_english": title.get("english"),
        "title_native": title.get("native"),
        "description": media.get("description"),
        "episodes": media.get("episodes"),
        "duration": media.get("duration"),
        "status": media.get("status"),
        "season": media.get("season"),
        "season_year": media.get("seasonYear"),
        "start_date": f"{start.get('year', '?')}-{start.get('month', '?')}-{start.get('day', '?')}",
        "end_date": f"{end.get('year', '?')}-{end.get('month', '?')}-{end.get('day', '?')}",
        "average_score": media.get("averageScore"),
        "mean_score": media.get("meanScore"),
        "popularity": media.get("popularity"),
        "favourites": media.get("favourites"),
        "genres": media.get("genres", []),
        "source": media.get("source"),
        "format": media.get("format"),
        "country": media.get("countryOfOrigin"),
        "is_adult": media.get("isAdult"),
        "studios": [s.get("name") for s in studios],
        "cover_image": media.get("coverImage", {}).get("large"),
        "banner_image": media.get("bannerImage"),
    }


def print_anime(info: Dict[str, Any]) -> None:
    if not info:
        print("No data found.")
        return
    print("=" * 60)
    print(f"  {info.get('title_english') or info.get('title_romaji')}")
    print("=" * 60)
    if info.get("title_native"):
        print(f"  Native:   {info['title_native']}")
    if info.get("title_romaji"):
        print(f"  Romaji:   {info['title_romaji']}")
    print()
    print(f"  Format:   {info.get('format')}")
    print(f"  Status:   {info.get('status')}")
    print(f"  Season:   {info.get('season')} {info.get('season_year')}")
    print(f"  Aired:    {info.get('start_date')} -> {info.get('end_date')}")
    print(f"  Episodes: {info.get('episodes')}")
    print(f"  Duration: {info.get('duration')} min")
    print(f"  Source:   {info.get('source')}")
    print(f"  Studios:  {', '.join(info.get('studios', [])) or 'N/A'}")
    print(f"  Genres:   {', '.join(info.get('genres', [])) or 'N/A'}")
    print()
    print(f"  AniList Score: {info.get('average_score')}")
    print(f"  Popularity:    {info.get('popularity')}")
    print(f"  Favourites:    {info.get('favourites')}")
    print()
    print(f"  AniList ID: {info.get('anilist_id')}")
    print(f"  MAL ID:     {info.get('mal_id')}")
    print(f"  Cover:      {info.get('cover_image')}")
    print("=" * 60)
    if info.get("description"):
        desc = re.sub(r"<[^>]+>", "", info["description"])
        print("\nSynopsis:")
        print(desc[:500] + "..." if len(desc) > 500 else desc)
    print()
