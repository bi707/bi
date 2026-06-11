import os
from datetime import datetime, timezone as tz
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class InstagramClient:
    """Cliente para a Instagram Graph API (Business/Creator accounts)."""

    def __init__(self):
        self.access_token = os.environ["CAZETV_INSTAGRAM_ACCESS_TOKEN"]
        self.account_id = os.environ["CAZETV_INSTAGRAM_ACCOUNT_ID"]

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = f"{GRAPH_API_BASE}/{path}"
        p = {"access_token": self.access_token}
        if params:
            p.update(params)
        resp = requests.get(url, params=p, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise ValueError(f"API Error [{data['error'].get('code')}]: {data['error'].get('message')}")
        return data

    def _paginate(self, path: str, params: dict | None = None) -> list[dict[str, Any]]:
        """Coleta todos os itens seguindo a paginação por cursor do Graph API."""
        results: list[dict] = []
        data = self._get(path, params)
        results.extend(data.get("data", []))

        while True:
            next_url = data.get("paging", {}).get("next")
            if not next_url:
                break
            resp = requests.get(next_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("data", []))

        return results

    # ------------------------------------------------------------------
    # Perfil
    # ------------------------------------------------------------------

    def get_profile(self) -> dict[str, Any]:
        """Retorna informações básicas do perfil Instagram Business."""
        return self._get(self.account_id, {
            "fields": (
                "id,name,username,followers_count,follows_count,"
                "media_count,biography,website,profile_picture_url"
            )
        })

    # ------------------------------------------------------------------
    # Insights da conta (nível de perfil — dados diários)
    # ------------------------------------------------------------------

    def get_account_insights(self, since: str, until: str) -> dict[str, list[dict]]:
        """
        Retorna insights diários da conta no período.

        Retorna dict: métrica → lista de {"date": "YYYY-MM-DD", "value": int}
        """
        metrics = [
            "follower_count",
            "reach",
            "impressions",
            "profile_views",
            "accounts_engaged",
            "website_clicks",
        ]
        result: dict[str, list] = {}
        try:
            since_ts = int(datetime.fromisoformat(since).replace(tzinfo=tz.utc).timestamp())
            until_ts = int(datetime.fromisoformat(until).replace(tzinfo=tz.utc).timestamp()) + 86400

            data = self._get(f"{self.account_id}/insights", {
                "metric": ",".join(metrics),
                "period": "day",
                "since": since_ts,
                "until": until_ts,
            })
            for item in data.get("data", []):
                name = item["name"]
                result[name] = [
                    {"date": v["end_time"][:10], "value": v["value"]}
                    for v in item.get("values", [])
                ]
        except Exception as e:
            print(f"  Aviso: erro ao buscar account insights: {e}")

        return result

    # ------------------------------------------------------------------
    # Mídias (posts, reels, stories)
    # ------------------------------------------------------------------

    def get_media(self, since: str, until: str) -> list[dict[str, Any]]:
        """Retorna todas as mídias publicadas no período (posts, reels, stories)."""
        fields = (
            "id,caption,media_type,media_product_type,"
            "timestamp,permalink,like_count,comments_count,thumbnail_url"
        )
        since_ts = int(datetime.fromisoformat(since).replace(tzinfo=tz.utc).timestamp())
        until_ts = int(datetime.fromisoformat(until).replace(tzinfo=tz.utc).timestamp()) + 86400

        return self._paginate(f"{self.account_id}/media", {
            "fields": fields,
            "since": since_ts,
            "until": until_ts,
            "limit": 100,
        })

    def get_media_insights(self, media_id: str, media_product_type: str) -> dict[str, Any]:
        """Retorna métricas detalhadas de uma publicação específica."""
        mpt = (media_product_type or "FEED").upper()

        if mpt == "REELS":
            metrics = "plays,reach,likes,comments,shares,saved,total_interactions,ig_reels_avg_watch_time"
        elif mpt == "STORY":
            metrics = "impressions,reach,replies,taps_forward,taps_back,exits"
        else:
            # FEED: IMAGE, VIDEO, CAROUSEL_ALBUM
            metrics = "impressions,reach,likes,comments,shares,saved,total_interactions"

        try:
            data = self._get(f"{media_id}/insights", {"metric": metrics})
            return {
                item["name"]: item["values"][0]["value"]
                for item in data.get("data", [])
                if item.get("values")
            }
        except Exception as e:
            print(f"    Aviso: sem insights para mídia {media_id} ({mpt}): {e}")
            return {}
