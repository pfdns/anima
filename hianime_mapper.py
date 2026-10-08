"""
HiAnime Mapper - پورت پایتون از anime-mapper
AniList ID → HiAnime slug + لیست اپیزودها
"""
import re
import requests
from typing import Optional, Dict, List, Set
from difflib import SequenceMatcher

from bs4 import BeautifulSoup


# ===== CONSTANTS =====
ANILIST_URL = "https://graphql.anilist.co"
HIANIME_URL = "https://hianime.at"
ANIZIP_URL = "https://api.ani.zip/mappings"

ANILIST_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    id
    title {
      romaji
      english
      native
      userPreferred
    }
    episodes
    synonyms
  }
}
"""

AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Word replacements for title variations
TITLE_REPLACEMENTS = {
    "season": ["s", "sz"],
    "s": ["season", "sz"],
    "sz": ["season", "s"],
    "two": ["2", "ii"],
    "three": ["3", "iii"],
    "four": ["4", "iv"],
    "part": ["pt", "p"],
    "episode": ["ep"],
    "chapters": ["ch"],
    "chapter": ["ch"],
    "first": ["1", "i"],
    "second": ["2", "ii"],
    "third": ["3", "iii"],
    "fourth": ["4", "iv"],
}


def normalize_text(text: str) -> str:
    """نرمال‌سازی متن برای مقایسه"""
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def get_word_variations(word: str) -> Set[str]:
    """گرفتن واریانت‌های یه کلمه"""
    variations = {word}
    normalized = normalize_text(word)
    variations.add(normalized)

    without_numbers = re.sub(r"\d+", "", word).strip()
    if without_numbers != word:
        variations.add(without_numbers)

    for key, values in TITLE_REPLACEMENTS.items():
        if normalized == key:
            variations.update(values)
        elif normalized in values:
            variations.add(key)
            variations.update(values)

    return variations


def calculate_title_score(search_title: str, hianime_title: str) -> float:
    """محاسبه امتیاز شباهت بین دو عنوان"""
    normalized_search = normalize_text(search_title)
    normalized_title = normalize_text(hianime_title)

    if normalized_search == normalized_title:
        return 1.0

    search_words = normalized_search.split()
    title_words = normalized_title.split()

    search_variations = [get_word_variations(w) for w in search_words]
    title_variations = [get_word_variations(w) for w in title_words]

    matches = 0
    partial_matches = 0.0

    for i, s_vars in enumerate(search_variations):
        best_word_match = 0.0

        for j, t_vars in enumerate(title_variations):
            for s_var in s_vars:
                for t_var in t_vars:
                    if s_var == t_var:
                        best_word_match = 1.0
                        break
                    if s_var in t_var or t_var in s_var:
                        match_length = min(len(s_var), len(t_var))
                        max_length = max(len(s_var), len(t_var))
                        best_word_match = max(best_word_match, match_length / max_length)
                if best_word_match == 1.0:
                    break
            if best_word_match == 1.0:
                break

        if best_word_match == 1.0:
            matches += 1
        elif best_word_match > 0:
            partial_matches += best_word_match

    word_match_score = (matches + partial_matches * 0.5) / len(search_words) if search_words else 0

    # similarity با SequenceMatcher (جایگزین string-similarity-js)
    similarity = SequenceMatcher(None, normalized_search, normalized_title).ratio()

    return (word_match_score * 0.7) + (similarity * 0.3)


class HiAnimeMapper:
    def __init__(self, proxy: Optional[str] = None, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": AGENT})
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    # ===== ANILIST =====
    def get_anime_info(self, anilist_id: int) -> Optional[Dict]:
        """گرفتن اطلاعات انیمه از AniList"""
        try:
            r = self.session.post(
                ANILIST_URL,
                json={"query": ANILIST_QUERY, "variables": {"id": anilist_id}},
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json().get("data", {}).get("Media")
            if not data:
                return None

            # حذف عنوان‌های چینی
            all_titles = set()
            for t in [
                *(data.get("synonyms") or []),
                data.get("title", {}).get("english"),
                data.get("title", {}).get("romaji"),
            ]:
                if t and not re.search(r"[\u4E00-\u9FFF]", t):
                    all_titles.add(t)

            return {
                "id": data["id"],
                "title": data["title"],
                "episodes": data.get("episodes"),
                "synonyms": list(all_titles),
            }
        except Exception as e:
            print(f"  ⚠️  AniList error: {e}")
            return None

    # ===== SEARCH HIANIME =====
    def search_anime(self, title: str, anime_info: Dict) -> Optional[str]:
        """جستجو تو HiAnime و انتخاب بهترین تطابق"""
        try:
            best_match = {"score": 0.0, "id": None}
            series_matches = []
            year = None

            # استخراج سال از عنوان
            year_match = re.search(r"\((\d{4})\)", title)
            if year_match:
                year = year_match.group(1)

            # عنوان‌های اولویت‌دار
            titles_to_try = []
            for t in [
                anime_info["title"].get("english"),
                anime_info["title"].get("romaji"),
                *anime_info.get("synonyms", []),
            ]:
                if t and t not in titles_to_try:
                    titles_to_try.append(t)

            for search_title in titles_to_try:
                url = f"{HIANIME_URL}/search?keyword={requests.utils.quote(search_title)}"
                try:
                    r = self.session.get(url, timeout=self.timeout)
                    r.raise_for_status()
                except Exception:
                    continue

                soup = BeautifulSoup(r.text, "lxml")
                for item in soup.select(".film_list-wrap > .flw-item"):
                    a = item.select_one(".film-detail .film-name a")
                    if not a:
                        continue

                    hianime_title = a.get_text(strip=True)
                    href = a.get("href", "")
                    hianime_id = href.split("/")[-1].split("?")[0]

                    jname = a.get("data-jname", "").strip()

                    # چک TV یا Movie
                    info_items = item.select(".fd-infor .fdi-item")
                    is_tv = bool(info_items and info_items[0].get_text(strip=True) == "TV")
                    is_movie = bool(info_items and info_items[0].get_text(strip=True) == "Movie")

                    # تعداد اپیزود
                    eps_el = item.select_one(".tick-item.tick-eps")
                    episodes_count = int(eps_el.get_text(strip=True)) if eps_el else 0

                    if not hianime_id:
                        continue

                    score = calculate_title_score(search_title, hianime_title)

                    # امتیازهای اضافی
                    if is_tv and anime_info.get("episodes", 0) > 12:
                        score += 0.1
                    if anime_info.get("episodes") and episodes_count == anime_info["episodes"]:
                        score += 0.2
                    if year and jname and year in jname:
                        score += 0.3
                    if is_movie and anime_info.get("episodes", 0) > 1:
                        score -= 0.3

                    if score > 0.5:
                        series_matches.append({
                            "title": hianime_title,
                            "id": hianime_id,
                            "score": score,
                            "is_movie": is_movie,
                            "is_tv": is_tv,
                            "episodes": episodes_count,
                            "jname": jname,
                        })

                    if score > best_match["score"]:
                        best_match = {"score": score, "id": hianime_id}

                if best_match["score"] > 0.85:
                    return best_match["id"]

            # فیلتر نهایی
            if series_matches:
                exact_ep = [m for m in series_matches if m["is_tv"] and anime_info.get("episodes") and m["episodes"] == anime_info["episodes"]]
                if exact_ep:
                    return sorted(exact_ep, key=lambda x: -x["score"])[0]["id"]

                series_matches.sort(key=lambda x: -x["score"])
                best_tv = next((m for m in series_matches if m["is_tv"]), None)
                best_overall = series_matches[0]

                if best_tv and (best_overall["score"] - best_tv["score"]) < 0.2:
                    return best_tv["id"]
                return best_overall["id"]

            return best_match["id"] if best_match["score"] > 0.4 else None

        except Exception as e:
            print(f"  ⚠️  Search error: {e}")
            return None

    # ===== EPISODES =====
    def get_episode_ids(self, anime_id: str, anilist_id: int) -> Dict:
        """گرفتن لیست اپیزودها"""
        try:
            short_id = anime_id.split("-")[-1]
            episode_url = f"{HIANIME_URL}/api/theme/episode/list/{short_id}"
            anizip_url = f"{ANIZIP_URL}?anilist_id={anilist_id}"

            # همزمان درخواست بفرست
            ep_r = self.session.get(
                episode_url,
                headers={
                    "Referer": f"{HIANIME_URL}/watch/{anime_id}",
                    "X-Requested-With": "XMLHttpRequest",
                },
                timeout=self.timeout,
            )
            anizip_r = self.session.get(anizip_url, timeout=self.timeout)

            ep_r.raise_for_status()
            ep_data = ep_r.json()
            html = ep_data.get("html", "")
            if not html:
                return {"totalEpisodes": 0, "episodes": []}

            anizip_data = anizip_r.json() if anizip_r.ok else {}

            soup = BeautifulSoup(html, "lxml")
            episodes = []

            for i, el in enumerate(soup.select("#detail-ss-list div.ss-list a")):
                href = el.get("href")
                if not href:
                    continue

                full_path = href.split("/")[-1]
                episode_number = i + 1
                anizip_ep = anizip_data.get("episodes", {}).get(str(episode_number), {})

                if full_path:
                    ep_id = full_path.split("?ep=")[-1] if "?ep=" in full_path else ""
                    episodes.append({
                        "episodeId": f"{anime_id}?ep={ep_id}",
                        "title": anizip_ep.get("title", {}).get("en") or el.get("title", ""),
                        "number": episode_number,
                        "image": anizip_ep.get("image"),
                        "overview": anizip_ep.get("overview"),
                        "airDate": anizip_ep.get("airDate"),
                        "runtime": anizip_ep.get("runtime"),
                    })

            return {
                "totalEpisodes": len(episodes),
                "episodes": episodes,
                "titles": anizip_data.get("titles"),
                "images": anizip_data.get("images"),
                "mappings": anizip_data.get("mappings"),
            }

        except Exception as e:
            print(f"  ⚠️  Episodes error: {e}")
            return {"totalEpisodes": 0, "episodes": []}

    # ===== MAIN =====
    def map_anilist_to_hianime(self, anilist_id: int) -> Optional[Dict]:
        """AniList ID → HiAnime slug + لیست اپیزودها"""
        anime_info = self.get_anime_info(anilist_id)
        if not anime_info:
            raise ValueError("Could not fetch anime info from AniList")

        title = anime_info["title"].get("english") or anime_info["title"].get("romaji")
        if not title:
            raise ValueError("No English or romaji title found")

        hianime_id = self.search_anime(title, anime_info)
        if not hianime_id:
            raise ValueError("Could not find anime on HiAnime")

        episodes = self.get_episode_ids(hianime_id, anilist_id)
        if not episodes.get("episodes"):
            raise ValueError("Could not fetch episodes")

        return {
            "anilistId": anilist_id,
            "hianimeId": hianime_id,
            "title": title,
            **episodes,
        }


if __name__ == "__main__":
    mapper = HiAnimeMapper(proxy="http://127.0.0.1:2080")
    result = mapper.map_anilist_to_hianime(113415)
    if result:
        print(f"✅ HiAnime ID: {result['hianimeId']}")
        print(f"✅ Title: {result['title']}")
        print(f"✅ Episodes: {result['totalEpisodes']}")
        print(f"\nFirst 3 episodes:")
        for ep in result["episodes"][:3]:
            print(f"  [{ep['number']}] {ep['title']}")
