"""
AniList Client - جستجو و اطلاعات انیمه
"""
import requests
from typing import Optional, Dict, Any, List


class AniListClient:
    API_URL = "https://graphql.anilist.co"

    # کوئری کامل برای یه انیمه خاص (شامل tags, characters, relations)
    QUERY_SINGLE = """
    query ($id: Int) {
      Media(id: $id, type: ANIME) {
        id
        idMal
        title { romaji english native }
        description(asHtml: false)
        episodes
        duration
        status
        season
        seasonYear
        startDate { year month day }
        endDate { year month day }
        averageScore
        meanScore
        popularity
        favourites
        genres
        source
        format
        countryOfOrigin
        isAdult
        studios(isMain: true) { nodes { name } }
        coverImage { large medium }
        bannerImage

        tags {
          name
          description
          rank
          category
          isGeneralSpoiler
          isMediaSpoiler
        }

        characters(sort: [ROLE, RELEVANCE, ID], perPage: 25) {
          edges {
            role
            node {
              id
              name { full native }
              description(asHtml: false)
            }
          }
        }

        relations {
          edges {
            relationType
            node {
              id
              title { romaji english native }
              format
              seasonYear
              type
            }
          }
        }
      }
    }
    """

    # کوئری جستجو (چندتایی)
    QUERY_SEARCH = """
    query ($search: String, $perPage: Int) {
      Page(perPage: $perPage) {
        media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
          id
          title { romaji english native }
          format
          seasonYear
          episodes
          status
        }
      }
    }
    """

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _post(self, query: str, variables: Dict) -> Optional[Dict]:
        try:
            r = self.session.post(
                self.API_URL,
                json={"query": query, "variables": variables},
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                print(f"  ⚠️  AniList API error: {data['errors']}")
                return None
            return data.get("data")
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Network error: {e}")
            return None

    def search_anime_list(self, name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """جستجوی چندتایی - برای انتخاب فصل/فیلم"""
        data = self._post(self.QUERY_SEARCH, {"search": name, "perPage": limit})
        if not data:
            return []
        return data.get("Page", {}).get("media", [])

    def get_anime_by_id(self, anilist_id: int) -> Optional[Dict[str, Any]]:
        """اطلاعات کامل یه انیمه با ID"""
        data = self._post(self.QUERY_SINGLE, {"id": anilist_id})
        if not data:
            return None
        return data.get("Media")

    def search_anime(self, name: str) -> Optional[Dict[str, Any]]:
        """جستجو - اولین نتیجه رو برمی‌گردونه (سازگاری با کد قدیمی)"""
        results = self.search_anime_list(name, limit=1)
        if not results:
            return None
        return self.get_anime_by_id(results[0]["id"])
