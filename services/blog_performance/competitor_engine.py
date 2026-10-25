"""
competitor_engine.py
====================
네이버 블로그 경쟁 플레이어 벤치마크 엔진 (화상회의 / 로지텍 장비 시장용)

기능
  1) 키워드 10개 검색 → 순위 스냅샷을 SQLite 에 날짜별 저장 (일일 캐시)
  2) 노출 점수 기반 상위 N 경쟁 블로그 자동 발굴 (pin / exclude 수동 보정)
  3) Share of Voice(SoV) 계산 (핀포인트 / 제너럴 / 전체, 검색량 가중 가능)
  4) 추정 지수(0~1000): 노출력·활동성·주제집중도·콘텐츠 (경쟁군 내 상대 점수)
  5) 상위 글 리버스 엔지니어링 (제목/글자수/이미지수 중앙값과 내 글 비교)
  6) 백그라운드 스캔 잡 + Flask Blueprint (app.py 에서 register 한 줄로 연결)

주의
  * 순위는 "블로그 검색 API 결과 내 위치(추정)" 이며 실제 통합검색/VIEW 노출 순위와 다를 수 있음.
  * 지수는 공개 데이터(API/RSS/본문)만으로 계산한 "경쟁군 내 상대 점수" 임. 방문자 수는 사용하지 않음.
  * 본문 수집(3단계)의 CSS 셀렉터는 실제 페이지에서 한 번 확인 후 POST_BODY_SELECTORS 를 조정할 것.

의존성: requests (필수), beautifulsoup4 (본문 수집 시에만), flask (Blueprint 사용 시에만)
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import statistics
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse
try:
    from .competitor_calibration import normalize_weights,measurement_context
except ImportError:
    from competitor_calibration import normalize_weights,measurement_context

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from services import keyword_aliases as ka
    from services import relevance_filter as rf
except ImportError:
    import keyword_aliases as ka
    import relevance_filter as rf

# --------------------------------------------------------------------------- #
# 설정
# --------------------------------------------------------------------------- #

PINPOINT_KEYWORDS = [
    "로지텍 랠리바",
    "로지텍 랠리바 미니",
    "로지텍 밋업 2",
    "로지텍 랠리 마이크 팟",
    "로지텍 탭",
]
GENERAL_KEYWORDS = [
    "화상회의 구축",
    "화상회의 장비",
    "화상회의",
    "화상회의 솔루션",
    "회의실 화상카메라",
    "화상회의 장비 추천",
    "화상회의 시스템 구축",
]
# 주제 집중도 계산용 (영문/한글 주제어)
DEFAULT_TOPIC_TERMS = [
    "로지텍", "랠리바", "랠리", "밋업", "화상회의", "화상카메라", "회의실",
    "logitech", "rally bar", "meetup", "video conference"
]

USER_AGENT = "Mozilla/5.0 (compatible; blog-benchmark/1.0)"
POST_BODY_SELECTORS = [".se-main-container", "#postViewArea", ".post_ct", "#viewTypeSelector"]


@dataclass
class Config:
    my_blog_id: str = "oceantech01"
    pinpoint_keywords: list = field(default_factory=lambda: list(PINPOINT_KEYWORDS))
    general_keywords: list = field(default_factory=lambda: list(GENERAL_KEYWORDS))
    keyword_volumes: dict = field(default_factory=dict)  # {"화상회의": 12000, ...} 없으면 1
    pin: list = field(default_factory=list)  # 반드시 포함할 경쟁 blog_id
    exclude: list = field(default_factory=list)  # 제외할 blog_id (공식 브랜드, 체험단 등). pin 보다 우선
    longtail_keywords: list = field(default_factory=list)  # 전환 의도가 높은 롱테일 키워드 (검색량 낮음, 검증 후 채택)
    topic_terms: list = field(default_factory=lambda: list(DEFAULT_TOPIC_TERMS))
    top_n: int = 10
    pool_size: int = 25  # 연관성 필터링 후보 풀 크기
    min_focus: float = 0.3  # 최소 주제 집중도 하한선
    rank_depth: int = 100  # API 에서 가져올 결과 수 (최대 1000)
    sov_max_rank: int = 30  # SoV 가중치를 부여할 최대 순위
    index_weights: dict = field(
        default_factory=lambda: {"exposure": 0.40, "activity": 0.25, "focus": 0.20, "content": 0.15}
    )
    db_path: str = os.path.join(BASE_DIR, "data", "competitor_bench.db")
    api_min_interval: float = 0.15  # 초. 네이버 검색 API 초당 호출 제한 대비
    crawl_min_interval: float = 1.8  # 초. 본문 수집 간격
    post_cache_days: int = 7

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        default_comp = os.path.join(BASE_DIR, "config", "competitors_config.json")
        path = path or os.environ.get("COMPETITOR_CONFIG", default_comp)
        cfg = cls()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                if not key.startswith("_") and hasattr(cfg, key):
                    setattr(cfg, key, value)
        cfg.my_blog_id = cfg.my_blog_id.lower()
        cfg.pin = [b.lower() for b in cfg.pin]
        cfg.exclude = [b.lower() for b in cfg.exclude]
        cfg.index_weights = normalize_weights(cfg.index_weights)
        return cfg

    def all_keywords(self) -> list:
        """[(keyword, group)] — group 은 'pinpoint' | 'general' | 'longtail'"""
        return ([(k, "pinpoint") for k in self.pinpoint_keywords]
                + [(k, "general") for k in self.general_keywords]
                + [(k, "longtail") for k in self.longtail_keywords])

    def volume(self, keyword: str) -> float:
        return float(self.keyword_volumes.get(keyword, 1.0))


# --------------------------------------------------------------------------- #
# 유틸
# --------------------------------------------------------------------------- #

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {"&quot;": '"', "&amp;": "&", "&lt;": "<", "&gt;": ">", "&#39;": "'", "&apos;": "'"}


def strip_tags(text: str) -> str:
    text = _TAG_RE.sub("", text or "")
    for src, dst in _ENTITIES.items():
        text = text.replace(src, dst)
    return text.strip()


_NAVER_BLOG_HOSTS = {"blog.naver.com", "m.blog.naver.com"}
_NON_ID_PATHS = {"postview.naver", "postlist.naver", "blogmain.naver", "prologue"}


def extract_blog_id(url: Optional[str]) -> Optional[str]:
    """blog.naver.com 계열 URL 에서 blog_id 추출. 네이버 블로그가 아니면 None."""
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if (parsed.netloc or "").lower() not in _NAVER_BLOG_HOSTS:
        return None
    query = parse_qs(parsed.query)
    if query.get("blogId"):
        return query["blogId"][0].lower()
    parts = [p for p in parsed.path.split("/") if p]
    if parts and parts[0].lower() not in _NON_ID_PATHS:
        return parts[0].lower()
    return None


def extract_log_no(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if query.get("logNo"):
        return query["logNo"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():
        return parts[1]
    return None


class Throttle:
    """호출 간 최소 간격 보장."""

    def __init__(self, min_interval: float, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: Optional[float] = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            remaining = self.min_interval - (now - self._last)
            if remaining > 0:
                self._sleep(remaining)
        self._last = self._clock()


def summarize(values: list) -> dict:
    """중앙값과 사분위. 표본 1개면 모두 같은 값."""
    values = [v for v in values if v is not None]
    n = len(values)
    if n == 0:
        return {"n": 0, "median": None, "q1": None, "q3": None}
    if n == 1:
        v = float(values[0])
        return {"n": 1, "median": v, "q1": v, "q3": v}
    q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return {"n": n, "median": float(statistics.median(values)), "q1": float(q1), "q3": float(q3)}


# --------------------------------------------------------------------------- #
# 네이버 검색 API 클라이언트 (NAVER API HUB & 레거시 개발자센터 자동 호환)
# --------------------------------------------------------------------------- #


class NaverApiError(RuntimeError):
    pass


class NaverBlogClient:
    """네이버 검색 API(블로그). display 최대 100, start 최대 1000.
    NAVER API HUB(2026년 7월 이후 신규 apigw.ntruss.com) 및 기존 개발자센터 자동 지원."""

    HUB_URL = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
    LEGACY_URL = "https://openapi.naver.com/v1/search/blog.json"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 min_interval: float = 0.15, session=None):
        # 환경변수 우선, 없으면 config.json 에서 자동 로드
        self.client_id = client_id or os.environ.get("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("NAVER_CLIENT_SECRET")
        if not (self.client_id and self.client_secret):
            cfg_path = os.path.join(BASE_DIR, "config", "config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cdata = json.load(f)
                        self.client_id = self.client_id or cdata.get("naver_client_id")
                        self.client_secret = self.client_secret or cdata.get("naver_client_secret")
                except Exception:
                    pass

        if not (self.client_id and self.client_secret):
            raise NaverApiError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 이 설정되지 않았습니다.")
        self._throttle = Throttle(min_interval)
        self._session = session

    def _get(self, params: dict) -> dict:
        import requests

        sess = self._session or requests
        last_err: Optional[str] = None

        # 1-A: NAVER API HUB 헤더 시도
        hub_headers = {
            "X-NCP-APIGW-API-KEY-ID": self.client_id,
            "X-NCP-APIGW-API-KEY": self.client_secret,
            "User-Agent": USER_AGENT
        }
        # 1-B: 레거시 개발자센터 헤더
        legacy_headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "User-Agent": USER_AGENT
        }

        for attempt in range(3):
            self._throttle.wait()
            # First try NAVER API HUB
            try:
                resp = sess.get(self.HUB_URL, headers=hub_headers, params=params, timeout=10)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass

            # Fallback to Legacy Developers Center URL
            resp = sess.get(self.LEGACY_URL, headers=legacy_headers, params=params, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            break
        raise NaverApiError(last_err or "unknown error")

    def search_hits(self, query: str, depth: int = 100, sort: str = "sim") -> list:
        """상위 depth 개 결과를 [{rank, blog_id, blog_name, post_url, title, postdate}] 로 반환."""
        depth = max(1, min(depth, 1000))
        hits: list = []
        start = 1
        while len(hits) < depth and start <= 1000:
            display = min(100, depth - len(hits))
            data = self._get({"query": query, "display": display, "start": start, "sort": sort})
            items = data.get("items", [])
            if not items:
                break
            for item in items:
                hits.append({
                    "rank": len(hits) + 1,
                    "blog_id": extract_blog_id(item.get("bloggerlink")) or extract_blog_id(item.get("link")),
                    "blog_name": strip_tags(item.get("bloggername", "")),
                    "post_url": item.get("link", ""),
                    "title": strip_tags(item.get("title", "")),
                    "postdate": item.get("postdate", ""),
                })
            start += len(items)
            if len(items) < display:
                break
        return hits


# --------------------------------------------------------------------------- #
# 저장소 (SQLite)
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS blogs (
    blog_id TEXT PRIMARY KEY, name TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS keywords (
    keyword TEXT PRIMARY KEY, grp TEXT, volume REAL
);
CREATE TABLE IF NOT EXISTS rank_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snap_date TEXT NOT NULL, keyword TEXT NOT NULL, rank INTEGER NOT NULL,
    blog_id TEXT, post_url TEXT, title TEXT, postdate TEXT
);
CREATE INDEX IF NOT EXISTS ix_rank_date_kw ON rank_snapshots(snap_date, keyword);
CREATE TABLE IF NOT EXISTS competitor_sets (
    snap_date TEXT NOT NULL, blog_id TEXT NOT NULL, position INTEGER, exposure REAL,
    PRIMARY KEY (snap_date, blog_id)
);
CREATE TABLE IF NOT EXISTS posts (
    url TEXT PRIMARY KEY, blog_id TEXT, title TEXT, char_count INTEGER, image_count INTEGER, fetched_at TEXT
);
CREATE TABLE IF NOT EXISTS blog_activity (
    snap_date TEXT NOT NULL, blog_id TEXT NOT NULL,
    count_30d INTEGER, regularity REAL, focus_ratio REAL, avg_chars REAL, avg_images REAL,
    PRIMARY KEY (snap_date, blog_id)
);
CREATE TABLE IF NOT EXISTS index_snapshots (
    snap_date TEXT NOT NULL, blog_id TEXT NOT NULL,
    exposure REAL, activity REAL, focus REAL, content REAL, total REAL,
    PRIMARY KEY (snap_date, blog_id)
);
CREATE TABLE IF NOT EXISTS benchmark_run_context (
    snap_date TEXT PRIMARY KEY, context_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS verified_ranks (
    snap_date TEXT NOT NULL, keyword TEXT NOT NULL, blog_id TEXT NOT NULL, rank INTEGER,
    PRIMARY KEY (snap_date, keyword, blog_id)
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY, status TEXT, progress INTEGER, total INTEGER, message TEXT,
    created_at TEXT, finished_at TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    """파일 기반 SQLite."""

    def __init__(self, path: str):
        self.path = path
        # parent dir create
        parent_dir = os.path.dirname(self.path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30)
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # -- 키워드 / 블로그 ---------------------------------------------------
    def upsert_keyword(self, keyword: str, grp: str, volume: float) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT INTO keywords(keyword, grp, volume) VALUES(?,?,?) "
                "ON CONFLICT(keyword) DO UPDATE SET grp=excluded.grp, volume=excluded.volume",
                (keyword, grp, volume),
            )

    def upsert_blogs(self, pairs: dict) -> None:
        with self.conn() as c:
            for blog_id, name in pairs.items():
                c.execute(
                    "INSERT INTO blogs(blog_id, name, updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(blog_id) DO UPDATE SET name=COALESCE(NULLIF(excluded.name,''), blogs.name), "
                    "updated_at=excluded.updated_at",
                    (blog_id, name, _now_iso()),
                )

    def blog_names(self) -> dict:
        with self.conn() as c:
            return {r["blog_id"]: r["name"] for r in c.execute("SELECT blog_id, name FROM blogs")}

    # -- 순위 스냅샷 -------------------------------------------------------
    def has_snapshot(self, snap_date: str, keyword: str) -> bool:
        with self.conn() as c:
            row = c.execute(
                "SELECT 1 FROM rank_snapshots WHERE snap_date=? AND keyword=? LIMIT 1", (snap_date, keyword)
            ).fetchone()
        return row is not None

    def save_hits(self, snap_date: str, keyword: str, hits: list) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM rank_snapshots WHERE snap_date=? AND keyword=?", (snap_date, keyword))
            c.executemany(
                "INSERT INTO rank_snapshots(snap_date, keyword, rank, blog_id, post_url, title, postdate) "
                "VALUES(?,?,?,?,?,?,?)",
                [(snap_date, keyword, h["rank"], h["blog_id"], h["post_url"], h["title"], h["postdate"])
                 for h in hits],
            )
        self.upsert_blogs({h["blog_id"]: h["blog_name"] for h in hits if h["blog_id"]})

    def rank_rows(self, snap_date: Optional[str], keyword: Optional[str] = None) -> list:
        if not snap_date:
            return []
        sql = "SELECT keyword, rank, blog_id, post_url, title, postdate FROM rank_snapshots WHERE snap_date=?"
        args: list = [snap_date]
        if keyword:
            sql += " AND keyword=?"
            args.append(keyword)
        sql += " ORDER BY keyword, rank"
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, args)]

    def latest_date(self, before: Optional[str] = None) -> Optional[str]:
        sql, args = "SELECT MAX(snap_date) AS d FROM rank_snapshots", []
        if before:
            sql += " WHERE snap_date < ?"
            args.append(before)
        with self.conn() as c:
            row = c.execute(sql, args).fetchone()
            return row["d"] if row else None

    def trend(self, keyword: str, blog_ids: list, days: int = 60) -> dict:
        since = (date.today() - timedelta(days=days)).isoformat()
        out: dict = {b: [] for b in blog_ids}
        if not blog_ids:
            return out
        marks = ",".join("?" for _ in blog_ids)
        with self.conn() as c:
            rows = c.execute(
                f"SELECT snap_date, blog_id, MIN(rank) AS best FROM rank_snapshots "
                f"WHERE keyword=? AND snap_date>=? AND blog_id IN ({marks}) "
                f"GROUP BY snap_date, blog_id ORDER BY snap_date",
                [keyword, since, *blog_ids],
            ).fetchall()
        for r in rows:
            out[r["blog_id"]].append({"date": r["snap_date"], "rank": r["best"]})
        return out

    # -- 경쟁군 / 활동성 / 지수 --------------------------------------------
    def save_competitors(self, snap_date: str, rows: list) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM competitor_sets WHERE snap_date=?", (snap_date,))
            c.executemany(
                "INSERT INTO competitor_sets(snap_date, blog_id, position, exposure) VALUES(?,?,?,?)",
                [(snap_date, r["blog_id"], i + 1, r["exposure"]) for i, r in enumerate(rows)],
            )

    def get_competitors(self, snap_date: str) -> list:
        with self.conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT blog_id, position, exposure FROM competitor_sets WHERE snap_date=? ORDER BY position",
                (snap_date,))]

    def save_activity(self, snap_date: str, blog_id: str, m: dict) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO blog_activity(snap_date, blog_id, count_30d, regularity, focus_ratio, "
                "avg_chars, avg_images) VALUES(?,?,?,?,?,?,?)",
                (snap_date, blog_id, m["count_30d"], m["regularity"], m["focus_ratio"],
                 m.get("avg_chars"), m.get("avg_images")),
            )

    def get_activity(self, snap_date: str) -> dict:
        with self.conn() as c:
            return {r["blog_id"]: dict(r) for r in c.execute(
                "SELECT * FROM blog_activity WHERE snap_date=?", (snap_date,))}

    def save_index(self, snap_date: str, index: dict, context=None) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM index_snapshots WHERE snap_date=?", (snap_date,))
            c.executemany(
                "INSERT INTO index_snapshots(snap_date, blog_id, exposure, activity, focus, content, total) "
                "VALUES(?,?,?,?,?,?,?)",
                [(snap_date, b, v.get("exposure"), v.get("activity"), v.get("focus"), v.get("content"), v["total"])
                 for b, v in index.items()],
            )
            if context is not None:
                c.execute('INSERT OR REPLACE INTO benchmark_run_context(snap_date,context_json) VALUES(?,?)',
                          (snap_date,json.dumps(context,ensure_ascii=False)))

    def get_run_context(self,snap_date):
        with self.conn() as c:
            row=c.execute('SELECT context_json FROM benchmark_run_context WHERE snap_date=?',(snap_date,)).fetchone()
        return json.loads(row[0]) if row else None

    def get_index(self, snap_date: str) -> dict:
        with self.conn() as c:
            return {r["blog_id"]: dict(r) for r in c.execute(
                "SELECT * FROM index_snapshots WHERE snap_date=?", (snap_date,))}

    # -- 본문 메타 캐시 ----------------------------------------------------
    def get_post(self, url: str, max_age_days: int) -> Optional[dict]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM posts WHERE url=?", (url,)).fetchone()
        if not row:
            return None
        fetched = datetime.fromisoformat(row["fetched_at"])
        if datetime.now(timezone.utc) - fetched > timedelta(days=max_age_days):
            return None
        return dict(row)

    def save_post(self, url: str, blog_id: Optional[str], meta: dict) -> None:
        with self.conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO posts(url, blog_id, title, char_count, image_count, fetched_at) "
                "VALUES(?,?,?,?,?,?)",
                (url, blog_id, meta.get("title", ""), meta["char_count"], meta["image_count"], _now_iso()),
            )

    # -- 수동 검증 순위 ----------------------------------------------------
    def set_verified_rank(self, snap_date: str, keyword: str, blog_id: str, rank: Optional[int]) -> None:
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO verified_ranks(snap_date, keyword, blog_id, rank) VALUES(?,?,?,?)",
                      (snap_date, keyword, blog_id.lower(), rank))

    def get_verified(self, snap_date: str) -> dict:
        with self.conn() as c:
            return {(r["keyword"], r["blog_id"]): r["rank"] for r in c.execute(
                "SELECT keyword, blog_id, rank FROM verified_ranks WHERE snap_date=?", (snap_date,))}

    # -- 잡 ----------------------------------------------------------------
    def create_job(self, job_id: str) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO jobs(job_id, status, progress, total, message, created_at) VALUES(?,?,?,?,?,?)",
                      (job_id, "running", 0, 0, "시작", _now_iso()))

    def update_job(self, job_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.conn() as c:
            c.execute(f"UPDATE jobs SET {cols} WHERE job_id=?", [*fields.values(), job_id])

    def get_job(self, job_id: str) -> Optional[dict]:
        with self.conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def running_job(self, max_age_minutes: int = 30) -> Optional[dict]:
        since = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat(timespec="seconds")
        with self.conn() as c:
            row = c.execute(
                "SELECT * FROM jobs WHERE status='running' AND created_at>=? ORDER BY created_at DESC LIMIT 1",
                (since,)).fetchone()
        return dict(row) if row else None


# --------------------------------------------------------------------------- #
# 순수 계산: 점수 / SoV / 발굴 / 지수
# --------------------------------------------------------------------------- #


def rank_weight(rank: Optional[int], max_rank: int = 30) -> float:
    """w(r) = 1/r  (1 <= r <= max_rank), 그 밖은 0."""
    if rank is None or rank < 1 or rank > max_rank:
        return 0.0
    return 1.0 / rank


def keyword_scores(rows: list, max_rank: int = 30) -> dict:
    """rank 행 → {keyword: {blog_id: {"score", "best_rank", "posts"}}}. blog_id 없는 행(타 플랫폼)은 무시."""
    out: dict = {}
    for r in rows:
        blog_id = r.get("blog_id")
        if not blog_id:
            continue
        entry = out.setdefault(r["keyword"], {}).setdefault(blog_id, {"score": 0.0, "best_rank": None, "posts": 0})
        entry["score"] += rank_weight(r["rank"], max_rank)
        entry["posts"] += 1
        if entry["best_rank"] is None or r["rank"] < entry["best_rank"]:
            entry["best_rank"] = r["rank"]
    return out


def compute_sov(scores: dict, keywords: list, volumes: Optional[dict] = None) -> dict:
    """SoV(b) = Σk v_k·S(b,k) / Σb' Σk v_k·S(b',k). 결과에 등장한 모든 블로그의 합이 1."""
    volumes = volumes or {}
    per_blog: dict = {}
    total = 0.0
    for kw in keywords:
        v = float(volumes.get(kw, 1.0))
        for blog_id, e in scores.get(kw, {}).items():
            value = v * e["score"]
            per_blog[blog_id] = per_blog.get(blog_id, 0.0) + value
            total += value
    if total <= 0:
        return {}
    return {b: x / total for b, x in per_blog.items()}


def discover_competitors(scores: dict, keywords: list, my_id: str, pin: list, exclude: list, top_n: int) -> list:
    """노출 점수(Σ 1/순위, 검색량 미가중) 상위 블로그로 경쟁군 선정.
    pin 은 무조건 포함, exclude 는 pin 보다 우선, 내 블로그는 항상 제외."""
    exposure: dict = {}
    for kw in keywords:
        for blog_id, e in scores.get(kw, {}).items():
            exposure[blog_id] = exposure.get(blog_id, 0.0) + e["score"]
    banned = set(exclude) | {my_id}
    chosen: list = []
    for b in pin:
        if b not in banned and b not in [c["blog_id"] for c in chosen]:
            chosen.append({"blog_id": b, "exposure": exposure.get(b, 0.0)})
    for b, x in sorted(exposure.items(), key=lambda kv: (-kv[1], kv[0])):
        if len(chosen) >= top_n:
            break
        if b in banned or b in [c["blog_id"] for c in chosen]:
            continue
        chosen.append({"blog_id": b, "exposure": x})
    chosen.sort(key=lambda c: (-c["exposure"], c["blog_id"]))
    return chosen


def minmax(values: dict) -> dict:
    """None 은 None 유지. 모두 같은 값이면 0 이하는 0.0, 그 외 0.5."""
    present = [v for v in values.values() if v is not None]
    if not present:
        return {k: None for k in values}
    lo, hi = min(present), max(present)
    out: dict = {}
    for k, v in values.items():
        if v is None:
            out[k] = None
        elif hi == lo:
            out[k] = 0.0 if hi <= 0 else 0.5
        else:
            out[k] = (v - lo) / (hi - lo)
    return out


def compute_index(raw: dict, weights: dict) -> dict:
    """raw: {blog: {"exposure","activity","focus","content"(None 가능)}} → {blog: {..., "total"(0~1000)}}.
    모든 블로그가 None 인 영역은 제외하고 남은 가중치를 재정규화."""
    weights=normalize_weights(weights)
    areas = ["exposure", "activity", "focus", "content"]
    norm: dict = {}
    active: list = []
    for a in areas:
        vals = {b: r.get(a) for b, r in raw.items()}
        if all(v is None for v in vals.values()):
            continue
        active.append(a)
        norm[a] = minmax(vals)
    wsum = sum(weights.get(a, 0.0) for a in active) or 1.0
    out: dict = {}
    for b in raw:
        parts = {a: norm[a].get(b) for a in active}
        total = (1000.0 * sum(weights.get(a, 0.0) * parts[a] for a in active) / wsum
                 if active and all(v is not None for v in parts.values()) else None)
        out[b] = {a: (round(parts[a], 4) if parts.get(a) is not None else None) for a in areas}
        out[b]["total"] = round(total, 1) if total is not None else None
    return out


# --------------------------------------------------------------------------- #
# RSS 기반 활동성
# --------------------------------------------------------------------------- #


def fetch_rss_posts(blog_id: str, *, session=None, timeout: int = 10) -> list:
    """네이버 블로그 RSS → [{title, link, published(datetime, tz-aware)}]. 실패 시 빈 리스트."""
    import requests

    sess = session or requests
    try:
        resp = sess.get(f"https://rss.blog.naver.com/{blog_id}.xml", headers={"User-Agent": USER_AGENT},
                        timeout=timeout)
        if resp.status_code != 200:
            return []
        return parse_rss(resp.content)
    except Exception:
        return []


def parse_rss(xml_bytes) -> list:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    posts = []
    for item in root.findall("./channel/item"):
        try:
            published = parsedate_to_datetime((item.findtext("pubDate") or "").strip())
        except (TypeError, ValueError):
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        posts.append({"title": (item.findtext("title") or "").strip(),
                      "link": (item.findtext("link") or "").strip(), "published": published})
    posts.sort(key=lambda p: p["published"], reverse=True)
    return posts


def _regularity(published: list) -> float:
    ds = sorted(published)
    gaps = [(b - a).total_seconds() / 86400 for a, b in zip(ds, ds[1:])]
    if len(gaps) < 2:
        return 0.0
    mean = statistics.fmean(gaps)
    if mean <= 0:
        return 0.0
    return 1.0 / (1.0 + statistics.pstdev(gaps) / mean)


def activity_metrics(posts: list, now: datetime, topic_terms: list) -> dict:
    """count_30d: 최근 30일 발행 수 / regularity: 최근 90일 발행 간격 규칙성(0~1) /
    focus_ratio: 최근 20개 제목 중 주제어 포함 비율."""
    count_30d = sum(1 for p in posts if p["published"] >= now - timedelta(days=30))
    recent_90 = [p["published"] for p in posts if p["published"] >= now - timedelta(days=90)]
    latest = posts[:20]
    if latest:
        hit = sum(1 for p in latest if ka.title_hits_terms(p.get("title", ""), topic_terms))
        focus = hit / len(latest)
    else:
        focus = 0.0
    return {"count_30d": count_30d, "regularity": _regularity(recent_90), "focus_ratio": focus}


def activity_raw(m: dict) -> float:
    return m["count_30d"] * (0.5 + 0.5 * m["regularity"])


# --------------------------------------------------------------------------- #
# 본문 수집 (3단계) — 셀렉터는 실제 페이지에서 확인 후 조정
# --------------------------------------------------------------------------- #


def parse_post_html(html: str) -> Optional[dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    container = None
    for selector in POST_BODY_SELECTORS:
        container = soup.select_one(selector)
        if container is not None:
            break
    if container is None:
        return None
    text = container.get_text(" ", strip=True)
    imgs = [
        i for i in container.find_all("img")
        if not any(c in (i.get("class") or []) for c in ["se-sticker-image", "se-icon", "emoji"])
        and not (i.get("width") == "1" or i.get("height") == "1")
    ]
    og = soup.select_one('meta[property="og:title"]')
    return {
        "title": og.get("content", "") if og else "",
        "char_count": len(re.sub(r"\s+", "", text)),  # 공백 제외 글자 수
        "image_count": len(imgs),
    }


def fetch_post_meta(url: str, *, session=None, timeout: int = 10) -> Optional[dict]:
    """모바일 URL 로 글 본문을 받아 글자 수/이미지 수 추출. 실패 시 None."""
    import requests

    blog_id, log_no = extract_blog_id(url), extract_log_no(url)
    if not (blog_id and log_no):
        return None
    sess = session or requests
    try:
        resp = sess.get(f"https://m.blog.naver.com/{blog_id}/{log_no}", headers={"User-Agent": USER_AGENT},
                        timeout=timeout)
        if resp.status_code != 200:
            return None
        return parse_post_html(resp.text)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# 스캔 파이프라인
# --------------------------------------------------------------------------- #


def run_scan(cfg: Config, client, store: Store, *, force: bool = False, snap_date: Optional[str] = None,
             crawl_content: bool = False, rss_fetcher: Optional[Callable] = None,
             post_fetcher: Optional[Callable] = None, progress: Optional[Callable] = None,
             now: Optional[datetime] = None, sleep: Callable = time.sleep) -> dict:
    """순위 수집 → 경쟁군 발굴 → 활동성 → 지수. 같은 날짜에 다시 호출하면 API 는 재호출하지 않음(force 제외)."""
    rss_fetcher = rss_fetcher or fetch_rss_posts
    post_fetcher = post_fetcher or fetch_post_meta
    snap_date = snap_date or date.today().isoformat()
    now = now or datetime.now(timezone.utc)
    progress = progress or (lambda done, total, msg: None)
    keywords = cfg.all_keywords()
    errors: list = []
    successful_keywords=set()

    total_steps = len(keywords) + cfg.top_n + 1
    done = 0

    # 1) 순위 스냅샷
    for kw, grp in keywords:
        store.upsert_keyword(kw, grp, cfg.volume(kw))
        if force or not store.has_snapshot(snap_date, kw):
            try:
                store.save_hits(snap_date, kw, client.search_hits(kw, depth=cfg.rank_depth))
                successful_keywords.add(kw)
            except NaverApiError as e:
                errors.append(f"{kw}: {e}")
        else:
            successful_keywords.add(kw)
        done += 1
        progress(done, total_steps, f"순위 수집: {kw}")
    if len(errors) == len(keywords):
        raise NaverApiError("모든 키워드 수집에 실패했습니다: " + "; ".join(errors[:3]))

    # 2) 경쟁군 발굴
    rows = store.rank_rows(snap_date)
    scores = keyword_scores(rows, cfg.sov_max_rank)
    kw_names = [k for k, _ in keywords]
    pool_size = getattr(cfg, "pool_size", 25)
    candidates = discover_competitors(scores, kw_names, cfg.my_blog_id, cfg.pin, cfg.exclude, pool_size)

    rss_cache: dict = {}

    def cached_rss(blog_id: str) -> list:
        if blog_id not in rss_cache:
            try:
                rss_cache[blog_id] = rss_fetcher(blog_id)
            except Exception as e:
                errors.append(f"RSS {blog_id}: {e}")
                rss_cache[blog_id] = []
        return rss_cache[blog_id]

    min_focus = getattr(cfg, "min_focus", 0.3)
    filtered = rf.select_competitors(candidates, cached_rss, cfg.topic_terms, top_n=cfg.top_n,
                                     min_focus=min_focus, pin=cfg.pin)
    competitors = filtered["selected"]
    filtered_out = filtered["rejected"]
    store.save_competitors(snap_date, competitors)
    tracked = [cfg.my_blog_id] + [c["blog_id"] for c in competitors]
    total_steps = len(keywords) + len(tracked) + 1
    progress(done, total_steps, f"경쟁군 {len(competitors)}곳 선정 (제외 {len(filtered_out)}곳)")

    # 3) 활동성 (RSS) + 선택적 본문 수집
    existing = {} if force else store.get_activity(snap_date)
    crawl_throttle = Throttle(cfg.crawl_min_interval, sleep=sleep)
    for blog_id in tracked:
        if blog_id not in existing:
            posts = cached_rss(blog_id)
            metrics = activity_metrics(posts, now, cfg.topic_terms)
            metrics["avg_chars"] = metrics["avg_images"] = None
            if crawl_content:
                metas = []
                for p in posts[:3]:
                    meta = store.get_post(p["link"], cfg.post_cache_days)
                    if meta is None:
                        crawl_throttle.wait()
                        meta = post_fetcher(p["link"])
                        if meta:
                            store.save_post(p["link"], blog_id, meta)
                    if meta:
                        metas.append(meta)
                if metas:
                    metrics["avg_chars"] = statistics.fmean(m["char_count"] for m in metas)
                    metrics["avg_images"] = statistics.fmean(m["image_count"] for m in metas)
            store.save_activity(snap_date, blog_id, metrics)
        done += 1
        progress(done, total_steps, f"활동성 분석: {blog_id}")

    # 4) 지수
    activity = store.get_activity(snap_date)
    sov_all = compute_sov(scores, kw_names, {k: cfg.volume(k) for k in kw_names})
    chars = minmax({b: activity[b]["avg_chars"] for b in tracked if b in activity})
    imgs = minmax({b: activity[b]["avg_images"] for b in tracked if b in activity})
    raw: dict = {}
    for b in tracked:
        a = activity.get(b)
        if a is None:
            continue
        content = None
        if chars.get(b) is not None or imgs.get(b) is not None:
            content = 0.7 * (chars.get(b) or 0.0) + 0.3 * (imgs.get(b) or 0.0)
        raw[b] = {"exposure": sov_all.get(b, 0.0), "activity": activity_raw(a) if cached_rss(b) else None,
                  "focus": a["focus_ratio"] if cached_rss(b) else None, "content": content}
    context=measurement_context(cfg,tracked,successful_keywords,
        rss_complete=all(bool(cached_rss(b)) for b in tracked),
        content_complete=all(activity.get(b,{}).get('avg_chars') is not None and activity.get(b,{}).get('avg_images') is not None for b in tracked))
    previous=store.get_run_context(snap_date)
    if existing and not (previous and previous.get('complete') and all(previous.get(k)==context.get(k) for k in ['measurement_key','cohort_key'])):
        context['complete']=False  # Do not assign new provenance to old cached metrics.
    context["samples"] = {b: {
        "rss_posts": len(cached_rss(b)), "focus_title_sample": min(20, len(cached_rss(b))),
        "rss_oldest": min((p["published"].isoformat() for p in cached_rss(b)), default=None),
        "rss_newest": max((p["published"].isoformat() for p in cached_rss(b)), default=None),
        "publication_count_basis": "observed_rss_last_30_days",
        "content_sample_limit": 3, "content_requested": crawl_content
    } for b in tracked}
    context["collection_status"] = "complete" if context["complete"] else "partial"
    computed = compute_index(raw, cfg.index_weights)
    if not context["complete"]:
        for value in computed.values():
            value["total"] = None
    store.save_index(snap_date, computed, context=context)
    progress(total_steps, total_steps, "완료")
    return {"snap_date": snap_date, "tracked": tracked, "filtered_out": filtered_out, "errors": errors}


# --------------------------------------------------------------------------- #
# 매트릭스 / CSV
# --------------------------------------------------------------------------- #


def build_matrix(store: Store, cfg: Config, snap_date: Optional[str] = None) -> dict:
    """대시보드용 매트릭스. status 는 '추적 중인 경쟁군' 기준(내 순위 vs 경쟁군 최고 순위)."""
    snap_date = snap_date or store.latest_date()
    if not snap_date:
        return {"snap_date": None, "error": "저장된 스캔이 없습니다. 먼저 스캔을 실행하세요."}
    context = store.get_run_context(snap_date)
    comparable = bool(context and context.get("complete"))
    if not comparable:
        return {"snap_date": snap_date, "comparison_available": False,
                "measurement_context": context,
                "error": "수집 자료 또는 측정 조건이 불완전하여 상대 비교를 제공하지 않습니다. 원자료는 보존됩니다."}
    prev_date = store.latest_date(before=snap_date)
    scores = keyword_scores(store.rank_rows(snap_date), cfg.sov_max_rank)
    prev_context = store.get_run_context(prev_date) if prev_date else None
    current_context = store.get_run_context(snap_date)
    same_basis = bool(prev_context and current_context and prev_context.get("complete") and current_context.get("complete") and all(prev_context.get(k) == current_context.get(k) for k in ["measurement_key", "cohort_key", "feature_version"]))
    prev_scores = keyword_scores(store.rank_rows(prev_date), cfg.sov_max_rank) if same_basis else {}
    competitors = store.get_competitors(snap_date)
    tracked = [cfg.my_blog_id] + [c["blog_id"] for c in competitors]
    names = store.blog_names()
    verified = store.get_verified(snap_date)
    index = store.get_index(snap_date)
    groups = {"pinpoint": cfg.pinpoint_keywords, "general": cfg.general_keywords,
              "longtail": cfg.longtail_keywords,
              "total": cfg.pinpoint_keywords + cfg.general_keywords + cfg.longtail_keywords}
    volumes = {k: cfg.volume(k) for k in groups["total"]}
    sov = {g: compute_sov(scores, kws, volumes) for g, kws in groups.items()}

    def best(kw: str, blog: str, table: dict) -> Optional[int]:
        return table.get(kw, {}).get(blog, {}).get("best_rank")

    blogs_out = []
    for b in tracked:
        cells = {}
        for kw, _grp in cfg.all_keywords():
            rank, prev = best(kw, b, scores), best(kw, b, prev_scores)
            cell = {
                "best_rank": rank,
                "score": round(scores.get(kw, {}).get(b, {}).get("score", 0.0), 4),
                "delta": (prev - rank) if (rank is not None and prev is not None) else None,  # +면 상승
                "verified_rank": verified.get((kw, b)),
            }
            if b == cfg.my_blog_id:
                rivals = [best(kw, r, scores) for r in tracked if r != b]
                rival_best = min([r for r in rivals if r is not None], default=None)
                if rank is None and rival_best is None:
                    cell["status"] = "none"
                elif rank is None:
                    cell["status"] = "lose"
                elif rival_best is None or rank < rival_best:
                    cell["status"] = "win"
                else:
                    cell["status"] = "lose"
                cell["rival_best"] = rival_best
            cells[kw] = cell
        blogs_out.append({
            "blog_id": b, "name": names.get(b, ""), "is_me": b == cfg.my_blog_id, "cells": cells,
            "sov": {g: round(sov[g].get(b, 0.0), 4) for g in groups},
            "index": index.get(b),
        })
    other = {g: round(max(0.0, 1.0 - sum(sov[g].get(b, 0.0) for b in tracked)), 4) for g in groups}
    leaderboard = sorted((x for x in blogs_out if x.get("index") and x["index"].get("total") is not None), key=lambda x: -x["index"]["total"])
    lost = [kw for kw, c in blogs_out[0]["cells"].items() if c.get("status") == "lose"] if blogs_out else []
    return {
        "snap_date": snap_date, "prev_date": prev_date, "measurement_context": context, "comparison_available": comparable,
        "rank_basis": "블로그 검색 API 결과 내 위치(추정)",
        "keywords": [{"keyword": k, "group": g, "volume": cfg.volume(k)} for k, g in cfg.all_keywords()],
        "blogs": blogs_out, "other_share": other,
        "leaderboard": [{"blog_id": x["blog_id"], "name": x["name"], "total": x["index"]["total"], "exposure": x["index"].get("exposure"), "activity": x["index"].get("activity"), "focus": x["index"].get("focus"), "content": x["index"].get("content")} for x in leaderboard],
        "lost_keywords": lost,
    }


def matrix_to_csv(matrix: dict) -> str:
    """Excel 한글 호환을 위해 호출 측에서 utf-8-sig 로 인코딩할 것."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    kws = [k["keyword"] for k in matrix.get("keywords", [])]
    sov_groups = list(matrix["blogs"][0]["sov"].keys()) if matrix.get("blogs") else ["pinpoint", "general", "longtail", "total"]
    sov_labels = {"pinpoint": "SoV 핀포인트", "general": "SoV 제너럴", "longtail": "SoV 롱테일", "total": "SoV 전체"}
    writer.writerow(["blog_id", "name", *kws, *[sov_labels.get(g, f"SoV {g}") for g in sov_groups], "추정 지수"])
    for b in matrix.get("blogs", []):
        writer.writerow([
            b["blog_id"], b["name"],
            *[(b["cells"][k]["best_rank"] if b["cells"][k]["best_rank"] is not None else "-") for k in kws],
            *[f"{b['sov'].get(g, 0.0):.4f}" for g in sov_groups],
            b["index"]["total"] if b.get("index") else "",
        ])
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# 리버스 엔지니어링
# --------------------------------------------------------------------------- #


def analyze_title(title: str, keyword: str) -> dict:
    t = strip_tags(title)
    m = ka.find_keyword_pos(t, keyword)
    if m is None:
        return {"length": len(t), "kw_in_title": False, "kw_exact": False, "kw_pos": None,
                "kw_at_front": False, "alias": None}
    return {
        "length": len(t),
        "kw_in_title": True,
        "kw_exact": m.exact,
        "kw_pos": m.pos,
        "kw_at_front": 0 <= m.pos <= 10,
        "alias": m.alias,
    }


def _guidance(mine: dict, stats: dict, keyword: str) -> list:
    tips: list = []
    n = stats["n"]
    tl = stats["title_length"]
    if mine.get("title_length") is not None and tl["n"]:
        if mine["title_length"] > tl["q3"] + 5 or mine["title_length"] < tl["q1"] - 5:
            tips.append(f"제목 길이를 {round(tl['q1'])}~{round(tl['q3'])}자 범위로 조정하세요. "
                        f"(내 제목 {mine['title_length']}자 / 상위 {n}개 중앙값 {round(tl['median'])}자)")
    if stats.get("kw_in_title_ratio", 0) >= 0.7 and not mine.get("kw_in_title"):
        tips.append(f"상위 글의 {round(stats['kw_in_title_ratio'] * 100)}%가 제목에 '{keyword}'(또는 관련 표기)를 넣었습니다. "
                    f"제목에 키워드를 포함하세요.")
    elif stats.get("kw_at_front_ratio", 0) >= 0.6 and mine.get("kw_in_title") and not mine.get("kw_at_front"):
        tips.append(f"상위 글의 {round(stats['kw_at_front_ratio'] * 100)}%가 키워드를 제목 앞 10자 안에 배치했습니다. "
                    f"키워드를 제목 앞쪽으로 옮기세요.")
    cc = stats["char_count"]
    if mine.get("char_count") is not None and cc["n"] and mine["char_count"] < cc["q1"]:
        tips.append(f"본문이 상위 글보다 짧습니다. (내 글 {mine['char_count']:,}자 / 중앙값 {round(cc['median']):,}자) "
                    f"상위 글 수준으로 보강하세요.")
    ic = stats["image_count"]
    if mine.get("image_count") is not None and ic["n"] and mine["image_count"] < ic["q1"]:
        tips.append(f"이미지가 부족합니다. (내 글 {mine['image_count']}장 / 중앙값 {round(ic['median'])}장)")
    return tips


def reverse_engineer(store: Store, cfg: Config, keyword: str, *, top_n: int = 10,
                     snap_date: Optional[str] = None, my_post_url: Optional[str] = None,
                     post_fetcher: Optional[Callable] = None, sleep: Callable = time.sleep) -> dict:
    """키워드 상위 글(내 글 제외)의 제목/본문 패턴 중앙값과 내 글을 비교. 표본이 작으면 참고용."""
    post_fetcher = post_fetcher or fetch_post_meta
    snap_date = snap_date or store.latest_date()
    rows = store.rank_rows(snap_date, keyword) if snap_date else []
    if not rows:
        return {"error": f"'{keyword}' 스캔 결과가 없습니다. 먼저 스캔을 실행하세요."}

    throttle = Throttle(cfg.crawl_min_interval, sleep=sleep)

    def meta_for(url: str, blog_id: Optional[str]) -> Optional[dict]:
        meta = store.get_post(url, cfg.post_cache_days)
        if meta is None:
            throttle.wait()
            meta = post_fetcher(url)
            if meta:
                store.save_post(url, blog_id, meta)
        return meta

    samples, failed = [], 0
    candidate_rows = [r for r in rows if r.get("blog_id") and r.get("blog_id") != cfg.my_blog_id]
    for r in candidate_rows[:top_n]:
        meta = meta_for(r["post_url"], r["blog_id"])
        if not meta:
            failed += 1
            continue
        t = analyze_title(r["title"], keyword)
        samples.append({
            "rank": r["rank"], "blog_id": r["blog_id"], "url": r["post_url"], "title": r["title"],
            "title_length": t["length"], "kw_in_title": t["kw_in_title"], "kw_exact": t.get("kw_exact", False),
            "kw_at_front": t["kw_at_front"], "alias": t.get("alias"),
            "char_count": meta["char_count"], "image_count": meta["image_count"]
        })
    if not samples:
        return {"error": "상위 글 본문을 수집하지 못했습니다. POST_BODY_SELECTORS 와 접근 가능 여부를 확인하세요.",
                "failed": failed}

    n = len(samples)
    stats = {
        "n": n,
        "title_length": summarize([s["title_length"] for s in samples]),
        "char_count": summarize([s["char_count"] for s in samples]),
        "image_count": summarize([s["image_count"] for s in samples]),
        "kw_in_title_ratio": sum(1 for s in samples if s["kw_in_title"]) / n,
        "kw_at_front_ratio": sum(1 for s in samples if s["kw_at_front"]) / n,
    }

    mine_row = None
    if my_post_url:
        mine_row = {"post_url": my_post_url, "title": "", "rank": None}
    else:
        mine_rows = [r for r in rows if r["blog_id"] == cfg.my_blog_id]
        mine_row = mine_rows[0] if mine_rows else None
    mine: dict = {}
    if mine_row:
        meta = meta_for(mine_row["post_url"], cfg.my_blog_id)
        title = mine_row["title"] or (meta or {}).get("title", "")
        t = analyze_title(title, keyword)
        mine = {"url": mine_row["post_url"], "rank": mine_row["rank"], "title": title, "title_length": t["length"],
                "kw_in_title": t["kw_in_title"], "kw_exact": t.get("kw_exact", False),
                "kw_at_front": t["kw_at_front"], "alias": t.get("alias"),
                "char_count": (meta or {}).get("char_count"), "image_count": (meta or {}).get("image_count")}

    guidance = _guidance(mine, stats, keyword) if mine else []
    note = None if mine else ("이 키워드의 API 상위 결과에 내 글이 없습니다. my_post_url 로 비교할 글을 지정하세요.")
    return {"keyword": keyword, "snap_date": snap_date, "label": "참고 패턴 (표본 크기 확인)", "sample_size": n,
            "failed": failed, "stats": stats, "top_posts": samples, "my_post": mine or None,
            "guidance": guidance, "note": note}


# --------------------------------------------------------------------------- #
# 백그라운드 잡 + Flask Blueprint
# --------------------------------------------------------------------------- #


def default_client_factory(cfg: Config) -> NaverBlogClient:
    return NaverBlogClient(min_interval=cfg.api_min_interval)


def start_scan_job(cfg: Config, *, client_factory: Callable = default_client_factory, force: bool = False,
                   crawl_content: bool = False) -> str:
    """스캔을 백그라운드 스레드로 시작하고 job_id 반환. 이미 실행 중이면 그 job_id 를 돌려줌."""
    store = Store(cfg.db_path)
    running = store.running_job()
    if running:
        return running["job_id"]
    job_id = uuid.uuid4().hex[:12]
    store.create_job(job_id)

    def work() -> None:
        try:
            def on_progress(done: int, total: int, msg: str) -> None:
                store.update_job(job_id, progress=done, total=total, message=msg)

            summary = run_scan(cfg, client_factory(cfg), store, force=force, crawl_content=crawl_content,
                               progress=on_progress)
            msg = "완료" + (f" (경고 {len(summary['errors'])}건)" if summary["errors"] else "")
            store.update_job(job_id, status="done", message=msg, finished_at=_now_iso())
        except Exception as e:
            store.update_job(job_id, status="error", message=str(e)[:300], finished_at=_now_iso())

    threading.Thread(target=work, name=f"scan-{job_id}", daemon=True).start()
    return job_id


def create_blueprint(config_loader: Callable = Config.load, client_factory: Callable = default_client_factory):
    """app.py:  from competitor_engine import create_blueprint;  app.register_blueprint(create_blueprint())"""
    from flask import Blueprint, Response, jsonify, request

    bp = Blueprint("competitors", __name__, url_prefix="/api/competitors")

    @bp.get("/product-scores")
    def product_scores():
        from pathlib import Path
        files = sorted((Path(BASE_DIR)/"data/blog_performance/product-search").glob("*/competitiveness-*/results.json"))
        if not files:
            return jsonify({"status": "unavailable", "error": "제품별 검색 경쟁력 자료가 없습니다."}), 404
        result = json.loads(files[-1].read_text(encoding="utf-8"))
        if result.get("valid_for_brand_inference") is False:
            return jsonify({"status": "unavailable", "error": "제품 관련성 미검증 결과는 사용 중지됐습니다. 본문 검토 결과를 기다려 주세요."}), 409
        blog_id = request.args.get("blog_id", "").strip().lower()
        if blog_id:
            result["blogs"] = [r for r in result["blogs"] if r["blog_id"] == blog_id]
            result["product_scores"] = [r for r in result["product_scores"] if r["blog_id"] == blog_id]
            result["query_rankings"] = [r for r in result.get("query_rankings", []) if r["blog_id"] == blog_id]
            result["brand_exposure"] = [r for r in result.get("brand_exposure", []) if r["blog_id"] == blog_id]
        else:
            result.pop("product_scores", None)
            result.pop("query_rankings", None)
        query_id = request.args.get("query_id", "")
        if query_id:
            result["query_rankings"] = [r for r in json.loads(files[-1].read_text(encoding="utf-8")).get("query_rankings", []) if r["query_id"] == query_id and (not blog_id or r["blog_id"] == blog_id)]
        return jsonify(result)

    @bp.post("/scan")
    def scan():
        body = request.get_json(silent=True) or {}
        cfg = config_loader()
        job_id = start_scan_job(cfg, client_factory=client_factory, force=bool(body.get("force")),
                                crawl_content=bool(body.get("crawl_content")))
        return jsonify({"job_id": job_id})

    @bp.get("/status/<job_id>")
    def status(job_id):
        job = Store(config_loader().db_path).get_job(job_id)
        return (jsonify(job), 200) if job else (jsonify({"error": "job not found"}), 404)

    @bp.get("/matrix")
    def matrix():
        cfg = config_loader()
        return jsonify(build_matrix(Store(cfg.db_path), cfg, request.args.get("date")))

    @bp.get("/trend")
    def trend():
        cfg = config_loader()
        store = Store(cfg.db_path)
        keyword = request.args.get("keyword", "")
        snap = store.latest_date()
        ids = [cfg.my_blog_id] + [c["blog_id"] for c in (store.get_competitors(snap) if snap else [])]
        return jsonify(store.trend(keyword, ids, int(request.args.get("days", 60))))

    @bp.post("/reverse-engineer")
    def reverse():
        body = request.get_json(silent=True) or {}
        cfg = config_loader()
        if not body.get("keyword"):
            return jsonify({"error": "keyword is required"}), 400
        result = reverse_engineer(Store(cfg.db_path), cfg, body["keyword"], top_n=int(body.get("top_n", 10)),
                                  my_post_url=body.get("my_post_url"))
        return jsonify(result), (400 if "error" in result else 200)

    @bp.post("/verified-rank")
    def verified():
        body = request.get_json(silent=True) or {}
        cfg = config_loader()
        store = Store(cfg.db_path)
        snap = body.get("date") or store.latest_date()
        if not (snap and body.get("keyword") and body.get("blog_id")):
            return jsonify({"error": "keyword, blog_id required (and a scan must exist)"}), 400
        store.set_verified_rank(snap, body["keyword"], body["blog_id"], body.get("rank"))
        return jsonify({"ok": True})

    @bp.get("/export.csv")
    def export_csv():
        cfg = config_loader()
        text = matrix_to_csv(build_matrix(Store(cfg.db_path), cfg, request.args.get("date")))
        return Response(text.encode("utf-8-sig"), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=competitor_matrix.csv"})

    return bp


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _main(argv: Optional[list] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="네이버 블로그 경쟁 플레이어 벤치마크")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="스캔 실행 (순위/경쟁군/활동성/지수)")
    p_scan.add_argument("--force", action="store_true", help="오늘 캐시 무시하고 재수집")
    p_scan.add_argument("--crawl", action="store_true", help="본문 수집(콘텐츠 지수) 포함")
    sub.add_parser("matrix", help="최신 매트릭스를 JSON 으로 출력")
    args = ap.parse_args(argv)

    cfg = Config.load()
    store = Store(cfg.db_path)
    if args.cmd == "scan":
        t0 = time.time()
        summary = run_scan(cfg, default_client_factory(cfg), store, force=args.force, crawl_content=args.crawl,
                           progress=lambda d, t, m: print(f"[{d}/{t}] {m}"))
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"소요 {time.time() - t0:.1f}s")
    else:
        print(json.dumps(build_matrix(store, cfg), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
