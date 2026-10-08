"""
HiAnime Client - پورت پایتون از ani-cli
"""
import base64
import json
import os
import re
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup


class HiAnimeClient:
    BASE_API = "https://hianime.at"
    SEARCH_API = BASE_API + "/search?keyword={}"
    EPISODES_API = BASE_API + "/api/theme/episode/list/{}"
    SERVERS_API = BASE_API + "/api/theme/episode/servers?episodeId={}"

    AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, proxy: Optional[str] = None, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.AGENT})
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

    def _get(self, url: str, referer: Optional[str] = None) -> str:
        headers = {}
        if referer:
            headers["Referer"] = referer
        r = self.session.get(url, headers=headers, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    def _short_id(self, anime_id: str) -> str:
        return anime_id.split("-")[-1]

    # ---------- SEARCH ----------
    def search(self, query: str) -> List[Dict[str, str]]:
        url = self.SEARCH_API.format(requests.utils.quote(query))
        html = self._get(url)

        if "Just a moment" in html:
            raise RuntimeError("Blocked by Cloudflare")

        html = html.split('id="main-sidebar"')[0]
        soup = BeautifulSoup(html, "lxml")

        results = []
        for item in soup.select("div.film-detail"):
            a = item.select_one("h3.film-name a")
            if not a:
                continue
            href = a.get("href", "")
            anime_id = href.rstrip("/").split("/")[-1]
            title = a.get("title") or a.get_text(strip=True)
            results.append({"id": anime_id, "title": title})

        return results

    # ---------- EPISODES ----------
    def get_episodes(self, anime_id: str) -> List[Dict[str, str]]:
        short = self._short_id(anime_id)
        url = self.EPISODES_API.format(short)
        html = self._get(url)

        if html.strip().startswith("{"):
            data = json.loads(html)
            html = data.get("html", "")

        soup = BeautifulSoup(html, "lxml")
        episodes = []
        for item in soup.select("a.ep-item"):
            ep_id = item.get("data-id")
            ep_num = item.get("data-number")
            ep_title = item.get("title", "")
            if ep_id and ep_num:
                episodes.append({
                    "id": ep_id,
                    "number": ep_num,
                    "title": ep_title,
                })

        return episodes

    # ---------- SERVERS ----------
    def get_servers(self, episode_id: str) -> List[Dict[str, str]]:
        url = self.SERVERS_API.format(episode_id)
        html = self._get(url)

        if html.strip().startswith("{"):
            data = json.loads(html)
            html = data.get("html", "")

        html = html.replace('\\"', '"')
        soup = BeautifulSoup(html, "lxml")

        servers = []
        for item in soup.select("div.server-item"):
            servers.append({
                "type": item.get("data-type", ""),
                "name": item.get("data-server-name", ""),
                "hash": item.get("data-hash", ""),
            })

        return servers

    # ---------- DEOBFUSCATE ----------
    @staticmethod
    def _deobfuscate_blob(b64_data: str) -> str:
        raw = base64.b64decode(b64_data)
        key = b"otaku-embed-v1"
        out = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return out.decode("utf-8", errors="ignore")

    # ---------- M3U8 ----------
    def get_m3u8(self, anime_id: str, episode_number: str, mode: str = "sub") -> Dict:
        episodes = self.get_episodes(anime_id)
        ep = next((e for e in episodes if e["number"] == episode_number), None)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        servers = self.get_servers(ep["id"])
        zoko = next(
            (s for s in servers if s["type"] == mode and s["name"] == "ZokoAnime"),
            None,
        )
        if not zoko:
            raise ValueError(f"No ZokoAnime server for mode={mode}")

        embed_url = base64.b64decode(zoko["hash"]).decode("utf-8")
        referer = re.match(r"^(https?://[^/]+)/", embed_url).group(1) + "/"

        embed_html = self._get(embed_url)
        m = re.search(r'window\.__P="([^"]*)"', embed_html)
        if not m:
            raise ValueError("Blob not found in embed page")

        json_str = self._deobfuscate_blob(m.group(1))

        m3u8_match = re.search(r'"src":"([^"]*\.m3u8[^"]*)"', json_str)
        if not m3u8_match:
            raise ValueError("m3u8 not found in blob")
        m3u8_url = m3u8_match.group(1)

        subtitles = []
        sub_match = re.search(r'"subtitles":\[(.*?)\]', json_str)
        if sub_match:
            for s in re.finditer(r'"src":"([^"]*)".*?"label":"([^"]*)"', sub_match.group(1)):
                subtitles.append({"url": s.group(1), "label": s.group(2)})

        return {
            "m3u8": m3u8_url,
            "subtitles": subtitles,
            "referer": referer,
        }

    # ---------- SUBTITLE ----------
    def get_english_subtitle_url(self, anime_id: str, episode_number: str) -> Optional[str]:
        """لینک زیرنویس انگلیسی رو برمی‌گردونه"""
        result = self.get_m3u8(anime_id, episode_number, mode="sub")
        subtitles = result.get("subtitles", [])
        for sub in subtitles:
            label = sub.get("label", "").lower()
            if "english" in label or label == "en":
                return sub["url"]
        return subtitles[0]["url"] if subtitles else None

    def download_subtitle(self, subtitle_url: str, output_path: str) -> bool:
        """دانلود فایل زیرنویس از یه URL"""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        try:
            r = self.session.get(subtitle_url, timeout=self.timeout)
            r.raise_for_status()
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        except Exception as e:
            print(f"  ⚠️  Subtitle download error: {e}")
            return False
