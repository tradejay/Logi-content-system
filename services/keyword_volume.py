"""
keyword_volume.py
=================
네이버 검색광고 API(키워드도구)로 키워드별 월간 검색량(PC + 모바일)을 조회해
competitors_config.json 의 keyword_volumes 를 채우는 도구.

준비물: 네이버 검색광고(searchad.naver.com) 계정의 API 사용 정보 3가지
  NAVER_SEARCHAD_CUSTOMER_ID   고객 ID (CUSTOMER_ID)
  NAVER_SEARCHAD_API_KEY       액세스 라이선스
  NAVER_SEARCHAD_SECRET_KEY    비밀키
  (도구 > API 사용 관리에서 발급. 네이버 개발자센터의 검색 API 키와는 다른 키입니다.)

사용
  python keyword_volume.py                # 조회만 하고 표로 출력
  python keyword_volume.py --write        # 12개 전부 조회된 경우에만 config 에 기록

주의
  * 일부 키워드만 채우면 빈 키워드의 가중치가 1이 되어 SoV 가 왜곡되므로, 하나라도 못 찾으면 기록하지 않는다.
  * 월간 검색량이 10 미만이면 API 가 '< 10' 문자열을 주므로 구간 표기를 보존하고 정확한 합계를 만들지 않는다.
  * 이 코드는 오프라인 테스트만 거쳤다. 실제 API 응답 필드가 다르면 keyword_stats() 의 파싱부를 조정할 것.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Callable, Optional


class SearchAdError(RuntimeError):
    pass


def make_signature(secret_key: str, timestamp: str, method: str, uri: str) -> str:
    """X-Signature = base64(HMAC-SHA256(secret, '{timestamp}.{method}.{uri}')). uri 는 쿼리스트링 제외 경로."""
    message = f"{timestamp}.{method}.{uri}".encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _to_int(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("<"):
            return text
        digits = text.replace(",", "")
        return int(digits) if digits.isdigit() else 0
    return 0


def _key(keyword: str) -> str:
    return keyword.replace(" ", "").lower()


class SearchAdClient:
    BASE = "https://api.searchad.naver.com"
    URI = "/keywordstool"

    def __init__(self, customer_id: Optional[str] = None, api_key: Optional[str] = None,
                 secret_key: Optional[str] = None, session=None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep, min_interval: float = 0.4):
        self.customer_id = customer_id or os.environ.get("NAVER_SEARCHAD_CUSTOMER_ID")
        self.api_key = api_key or os.environ.get("NAVER_SEARCHAD_API_KEY")
        self.secret_key = secret_key or os.environ.get("NAVER_SEARCHAD_SECRET_KEY")
        if not (self.customer_id and self.api_key and self.secret_key):
            raise SearchAdError("NAVER_SEARCHAD_CUSTOMER_ID / API_KEY / SECRET_KEY 가 설정되지 않았습니다.")
        self._session = session
        self._clock = clock
        self._sleep = sleep
        self._min_interval = min_interval

    def _headers(self) -> dict:
        ts = str(int(self._clock() * 1000))
        return {
            "X-Timestamp": ts,
            "X-API-KEY": self.api_key,
            "X-Customer": str(self.customer_id),
            "X-Signature": make_signature(self.secret_key, ts, "GET", self.URI),
        }

    def _request(self, hints: list) -> dict:
        import requests

        sess = self._session or requests
        params = {"hintKeywords": ",".join(h.replace(" ", "") for h in hints), "showDetail": "1"}
        resp = sess.get(self.BASE + self.URI, headers=self._headers(), params=params, timeout=10)
        if resp.status_code != 200:
            raise SearchAdError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    def keyword_relatives(self, hints: list) -> list[dict]:
        """hintKeywords 에 대한 relKeyword 전체 목록을 반환 (버리지 않고 전부)."""
        all_rows: list[dict] = []
        for i in range(0, len(hints), 5):
            chunk = hints[i:i + 5]
            if i:
                self._sleep(self._min_interval)
            data = self._request(chunk)
            all_rows.extend(data.get("keywordList", []))
        return all_rows

    def keyword_stats(self, keywords: list) -> dict:
        """{keyword: {'pc', 'mobile', 'total'}} — 응답에서 못 찾은 키워드는 None."""
        out: dict = {}
        for i in range(0, len(hints := keywords), 5):  # hintKeywords 는 호출당 최대 5개
            chunk = hints[i:i + 5]
            if i:
                self._sleep(self._min_interval)
            rows = {_key(r.get("relKeyword", "")): r for r in self._request(chunk).get("keywordList", [])}
            for kw in chunk:
                row = rows.get(_key(kw))
                if row is None:
                    out[kw] = None
                    continue
                pc = _to_int(row.get("monthlyPcQcCnt") if row.get("monthlyPcQcCnt") is not None else row.get("monthlyPcQryCnt"))
                mobile = _to_int(row.get("monthlyMobileQcCnt") if row.get("monthlyMobileQcCnt") is not None else row.get("monthlyMobileQryCnt"))
                out[kw] = {"pc": pc, "mobile": mobile, "total": pc + mobile if isinstance(pc, int) and isinstance(mobile, int) else None}
        return out


def write_volumes(config_path: str, volumes: dict) -> None:
    """config JSON 의 keyword_volumes 만 교체하고 나머지 키는 그대로 보존."""
    data: dict = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    data["keyword_volumes"] = volumes
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _main(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="검색광고 API 로 키워드 월간 검색량 조회")
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_comp_config = os.path.join(base_dir, "config", "competitors_config.json")
    ap.add_argument("--config", default=os.environ.get("COMPETITOR_CONFIG", default_comp_config))
    ap.add_argument("--write", action="store_true", help="전부 조회된 경우에만 config 의 keyword_volumes 에 기록")
    args = ap.parse_args(argv)

    cfg_file = os.path.join(base_dir, "config", "config.json")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, encoding="utf-8") as f:
                cdata = json.load(f)
                if cdata.get("ad_customer_id") or cdata.get("naver_searchad_customer_id"):
                    os.environ.setdefault("NAVER_SEARCHAD_CUSTOMER_ID", str(cdata.get("ad_customer_id") or cdata.get("naver_searchad_customer_id")))
                if cdata.get("ad_api_key") or cdata.get("naver_searchad_api_key"):
                    os.environ.setdefault("NAVER_SEARCHAD_API_KEY", str(cdata.get("ad_api_key") or cdata.get("naver_searchad_api_key")))
                if cdata.get("ad_secret_key") or cdata.get("naver_searchad_secret_key"):
                    os.environ.setdefault("NAVER_SEARCHAD_SECRET_KEY", str(cdata.get("ad_secret_key") or cdata.get("naver_searchad_secret_key")))
        except Exception:
            pass

    try:
        from .competitor_engine import Config
    except ImportError:
        from services.competitor_engine import Config

    cfg = Config.load(args.config)
    keywords = [k for k, _ in cfg.all_keywords()]
    stats = SearchAdClient().keyword_stats(keywords)

    print(f"{'키워드':<24}{'PC':>10}{'모바일':>10}{'합계':>10}")
    for kw in keywords:
        s = stats.get(kw)
        print(f"{kw:<24}" + (f"{str(s['pc']):>10}{str(s['mobile']):>10}{str(s['total']) if s['total'] is not None else '구간값':>10}" if s else "   (조회 실패)"))

    missing = [k for k in keywords if stats.get(k) is None or stats[k]["total"] is None]
    if missing:
        print(f"\n조회하지 못한 키워드 {len(missing)}개: {', '.join(missing)}", file=sys.stderr)
        print("일부만 기록하면 SoV 가중치가 왜곡되므로 config 는 수정하지 않았습니다.", file=sys.stderr)
        return 2
    if args.write:
        write_volumes(args.config, {k: stats[k]["total"] for k in keywords})
        print(f"\n{args.config} 의 keyword_volumes 를 갱신했습니다.")
    else:
        print("\n(--write 를 붙이면 config 에 기록합니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
