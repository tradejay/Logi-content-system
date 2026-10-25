"""
naver_search_client.py
======================
4개 소스(blog, cafearticle, kin, webkr) 네이버 검색 API 클라이언트.
NAVER API HUB 및 기존 OpenAPI(개발자센터) 자동 지원.
Customer Language DB의 문서량(total) 수집 및 일반인지수 계산을 위한 원재료 수집 특화.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable, Optional

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class NaverSearchError(RuntimeError):
    pass


class Throttle:
    def __init__(self, min_interval: float = 0.15, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep):
        self._min = min_interval
        self._last = 0.0
        self._clock = clock
        self._sleep = sleep

    def wait(self) -> None:
        now = self._clock()
        gap = now - self._last
        if gap < self._min:
            self._sleep(self._min - gap)
        self._last = self._clock()


class NaverSearchClient:
    """4소스(blog/cafearticle/kin/webkr) 검색. total 필드 수집 특화."""

    HUB_HOST = "https://naverapihub.apigw.ntruss.com"
    LEGACY_HOST = "https://openapi.naver.com"

    SOURCES = {
        "blog": {
            "hub": "/search/v1/blog",
            "legacy": "/v1/search/blog.json"
        },
        "cafearticle": {
            "hub": "/search/v1/cafearticle",
            "legacy": "/v1/search/cafearticle.json"
        },
        "kin": {
            "hub": "/search/v1/kin",
            "legacy": "/v1/search/kin.json"
        },
        "webkr": {
            "hub": "/search/v1/webkr",
            "legacy": "/v1/search/webkr.json"
        },
    }

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 min_interval: float = 0.12, session=None):
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET")
        if not (self.client_id and self.client_secret):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            cfg_path = os.path.join(base_dir, "config", "config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cdata = json.load(f)
                        self.client_id = self.client_id or cdata.get("naver_client_id")
                        self.client_secret = self.client_secret or cdata.get("naver_client_secret")
                except Exception:
                    pass

        if not (self.client_id and self.client_secret):
            raise NaverSearchError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 설정되지 않았습니다.")
        self._throttle = Throttle(min_interval)
        self._session = session

    def _get(self, endpoint_hub: str, endpoint_legacy: str, params: dict) -> dict:
        import requests

        sess = self._session or requests
        last_err: Optional[str] = None

        hub_headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
            "User-Agent": USER_AGENT,
        }
        legacy_headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "User-Agent": USER_AGENT,
        }

        hub_url = self.HUB_HOST + endpoint_hub
        legacy_url = self.LEGACY_HOST + endpoint_legacy

        for attempt in range(3):
            self._throttle.wait()
            try:
                resp = sess.get(hub_url, headers=hub_headers, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass

            try:
                resp = sess.get(legacy_url, headers=legacy_headers, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
                last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(1.0 * (attempt + 1))
                    continue
            except Exception as e:
                last_err = str(e)
                time.sleep(1.0 * (attempt + 1))
                continue
            break
        raise NaverSearchError(last_err or "unknown search api error")

    def totals(self, query: str) -> dict[str, int]:
        """4대 소스에 대해 display=1 로 호출하여 total 문서량 수집."""
        res: dict[str, int] = {"blog": 0, "cafearticle": 0, "kin": 0, "webkr": 0}
        params = {"query": query, "display": 1}
        for src, paths in self.SOURCES.items():
            try:
                data = self._get(paths["hub"], paths["legacy"], params)
                res[src] = int(data.get("total", 0))
            except Exception as e:
                res[src] = 0
        return res
