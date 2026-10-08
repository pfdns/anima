"""
HiAnime Client - استخراج لینک m3u8 + زیرنویس
"""
import base64
import json
import re
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup


class HiAnimeClient:
    BASE_API = "https://hianime.at"
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

    @staticmethod
    def _parse_subtitles_from_json(json_str: str) -> List[Dict[str, str]]:
        """پارس دقیق زیرنویس‌ها از JSON"""
        subtitles = []
        sub_match = re.search(r'"subtitles"\s*:\s*\[(.*?)\](?=\s*[},])', json_str, re.DOTALL)
        if not sub_match:
            return subtitles

        sub_section = sub_match.group(1)
        item_pattern = re.compile(r'\{(.*?)\}', re.DOTALL)

        for item_match in item_pattern.finditer(sub_section):
            item = item_match.group(1)
            lang_m = re.search(r'"lang"\s*:\s*"([^"]*)"', item)
            label_m = re.search(r'"label"\s*:\s*"([^"]*)"', item)
            src_m = re.search(r'"src"\s*:\s*"([^"]*)"', item)

            if src_m:
                subtitles.append({
                    "lang": lang_m.group(1) if lang_m else "",
                    "label": label_m.group(1) if label_m else "",
                    "url": src_m.group(1),
                })

        return subtitles

    # ---------- DOWNLOAD SUBTITLE (NEW) ----------
    def download_subtitle(
        self,
        url: str,
        output_path: str,
        referer: Optional[str] = None,
    ) -> bool:
        """
        دانلود فایل زیرنویس با Referer مناسب
        Referer برای سرورهای زیرنویس حیاتیه (بدونش 403 می‌ده)
        """
        # Referer پیش‌فرض برای zokoanime
        if not referer:
            referer = "https://zokoanime.video/"

        headers = {
            "User-Agent": self.AGENT,
            "Referer": referer,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

        try:
            r = self.session.get(url, headers=headers, timeout=30)
            r.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(r.content)

            return True

        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Download error: {e}")
            return False

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

        m3u8_match = re.search(r'"src"\s*:\s*"([^"]*\.m3u8[^"]*)"', json_str)
        if not m3u8_match:
            raise ValueError("m3u8 not found in blob")
        m3u8_url = m3u8_match.group(1)

        subtitles = self._parse_subtitles_from_json(json_str)

        return {
            "m3u8": m3u8_url,
            "subtitles": subtitles,
            "referer": referer,
        }


if __name__ == "__main__":
    client = HiAnimeClient(proxy="http://127.0.0.1:2080")
    result = client.get_m3u8("jujutsu-kaisen-237", "6")
    print(f"Referer: {result['referer']}")
    print(f"m3u8: {result['m3u8'][:80]}...")
    print()
    print(f"Subtitles ({len(result['subtitles'])}):")
    for sub in result["subtitles"]:
        print(f"  [{sub['label']}]")
        print(f"  {sub['url'][:80]}...")
