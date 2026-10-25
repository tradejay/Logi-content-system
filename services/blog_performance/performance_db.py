"""
performance_db.py
=================
블로그 성과 이력 데이터베이스 (SQLite)
- 글별 키워드 순위 일일 기록
- 블로그 전체 지수 일일 기록
- 방문자 수 일일 기록
- 시계열 조회 및 추세 분석
"""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "data", "performance_history.db")


@contextmanager
def get_db():
    """Thread-safe SQLite connection context manager."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """데이터베이스 테이블 초기화."""
    with get_db() as conn:
        conn.executescript("""
        -- 1. 글별 키워드 순위 일일 기록
        CREATE TABLE IF NOT EXISTS keyword_rank_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,           -- YYYY-MM-DD
            content_id TEXT NOT NULL,             -- e.g. CNT-2026W39-001
            keyword TEXT NOT NULL,                -- 추적 키워드
            keyword_type TEXT DEFAULT 'primary',  -- primary / supporting / layman
            rank INTEGER,                         -- 1~100 (NULL = 미노출)
            total_searched INTEGER DEFAULT 0,     -- 스크래핑된 전체 결과 수
            source TEXT DEFAULT 'scraping',       -- naver_api_hub / legacy / scraping
            post_title TEXT,                      -- 발견된 글 제목
            post_link TEXT,                       -- 발견된 글 링크
            UNIQUE(recorded_at, content_id, keyword)
        );

        -- 2. 블로그 전체 지수 일일 기록
        CREATE TABLE IF NOT EXISTS blog_index_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,            -- YYYY-MM-DD
            blog_id TEXT NOT NULL,
            total_score INTEGER NOT NULL,         -- 0~1000
            grade TEXT NOT NULL,                  -- 최적화 등급
            traffic_score INTEGER DEFAULT 0,
            activity_score INTEGER DEFAULT 0,
            content_score INTEGER DEFAULT 0,
            exposure_score INTEGER DEFAULT 0,
            avg_daily_visitors REAL DEFAULT 0,
            weekly_posts INTEGER DEFAULT 0,
            UNIQUE(recorded_at, blog_id)
        );

        -- 3. 키워드 검색량 주기적 스냅샷
        CREATE TABLE IF NOT EXISTS keyword_volume_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            keyword TEXT NOT NULL,
            monthly_pc INTEGER DEFAULT 0,
            monthly_mobile INTEGER DEFAULT 0,
            monthly_total INTEGER DEFAULT 0,
            comp_idx TEXT DEFAULT '',
            source TEXT DEFAULT '',
            UNIQUE(recorded_at, keyword)
        );

        -- 4. 추적 대상 콘텐츠 등록부
        CREATE TABLE IF NOT EXISTS tracked_contents (
            content_id TEXT PRIMARY KEY,
            blog_id TEXT,                         -- 게시된 블로그 ID
            title TEXT,
            primary_keyword TEXT,
            supporting_keywords TEXT,              -- JSON array
            layman_terms TEXT,                     -- JSON array
            canonical_topic TEXT,
            published_date TEXT,
            published_url TEXT,
            is_active INTEGER DEFAULT 1            -- 추적 활성화 여부
        );

        -- 5. 피드백 루프 기록
        CREATE TABLE IF NOT EXISTS feedback_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            content_id TEXT NOT NULL,
            feedback_type TEXT NOT NULL,           -- LOW_RANK / LOW_CTR / HIGH_PERFORM / RISING
            current_rank INTEGER,
            rank_change INTEGER,                   -- 음수=상승, 양수=하락
            recommendation TEXT,
            applied INTEGER DEFAULT 0,             -- 다음 Brief에 반영 여부
            applied_to TEXT                        -- 반영된 다음 content_id
        );

        CREATE INDEX IF NOT EXISTS idx_rank_content_date
            ON keyword_rank_history(content_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_rank_keyword_date
            ON keyword_rank_history(keyword, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_blog_index_date
            ON blog_index_history(blog_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_feedback_content
            ON feedback_actions(content_id);
        """)
    return True


# ─────────────────────────────────────────────
# WRITE OPERATIONS
# ─────────────────────────────────────────────

def register_content(content_id, blog_id, title, primary_keyword,
                     supporting_keywords=None, layman_terms=None,
                     canonical_topic="", published_date=None, published_url=None):
    """추적 대상 콘텐츠 등록 (upsert)."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO tracked_contents
                (content_id, blog_id, title, primary_keyword, supporting_keywords,
                 layman_terms, canonical_topic, published_date, published_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(content_id) DO UPDATE SET
                blog_id = excluded.blog_id,
                title = excluded.title,
                primary_keyword = excluded.primary_keyword,
                supporting_keywords = excluded.supporting_keywords,
                layman_terms = excluded.layman_terms,
                canonical_topic = excluded.canonical_topic,
                published_date = excluded.published_date,
                published_url = excluded.published_url
        """, (
            content_id, blog_id, title, primary_keyword,
            json.dumps(supporting_keywords or [], ensure_ascii=False),
            json.dumps(layman_terms or [], ensure_ascii=False),
            canonical_topic,
            published_date,
            published_url or ""
        ))
    return True


def record_rank(content_id, keyword, rank, keyword_type="primary",
                total_searched=0, source="scraping", post_title=None,
                post_link=None, recorded_at=None):
    """키워드 순위 일일 기록."""
    date_str = recorded_at or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO keyword_rank_history
                (recorded_at, content_id, keyword, keyword_type, rank,
                 total_searched, source, post_title, post_link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorded_at, content_id, keyword) DO UPDATE SET
                rank = excluded.rank,
                total_searched = excluded.total_searched,
                source = excluded.source,
                post_title = excluded.post_title,
                post_link = excluded.post_link
        """, (date_str, content_id, keyword, keyword_type, rank,
              total_searched, source, post_title, post_link))
    return True


def record_blog_index(blog_id, index_data, recorded_at=None):
    """블로그 지수 일일 기록."""
    date_str = recorded_at or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO blog_index_history
                (recorded_at, blog_id, total_score, grade, traffic_score,
                 activity_score, content_score, exposure_score,
                 avg_daily_visitors, weekly_posts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorded_at, blog_id) DO UPDATE SET
                total_score = excluded.total_score,
                grade = excluded.grade,
                traffic_score = excluded.traffic_score,
                activity_score = excluded.activity_score,
                content_score = excluded.content_score,
                exposure_score = excluded.exposure_score,
                avg_daily_visitors = excluded.avg_daily_visitors,
                weekly_posts = excluded.weekly_posts
        """, (
            date_str, blog_id,
            index_data.get("total_score", 0),
            index_data.get("grade", ""),
            index_data.get("traffic_score", 0),
            index_data.get("activity_score", 0),
            index_data.get("content_score", 0),
            index_data.get("exposure_score", 0),
            index_data.get("avg_daily_visitors", 0),
            index_data.get("weekly_posts", 0)
        ))
    return True


def record_keyword_volume(keyword, volume_data, recorded_at=None):
    """키워드 검색량 스냅샷 기록."""
    date_str = recorded_at or datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        conn.execute("""
            INSERT INTO keyword_volume_snapshot
                (recorded_at, keyword, monthly_pc, monthly_mobile,
                 monthly_total, comp_idx, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(recorded_at, keyword) DO UPDATE SET
                monthly_pc = excluded.monthly_pc,
                monthly_mobile = excluded.monthly_mobile,
                monthly_total = excluded.monthly_total,
                comp_idx = excluded.comp_idx,
                source = excluded.source
        """, (
            date_str, keyword,
            volume_data.get("monthly_pc", 0),
            volume_data.get("monthly_mobile", 0),
            volume_data.get("monthly_total", 0),
            volume_data.get("comp_idx", ""),
            volume_data.get("source", "")
        ))
    return True


def record_feedback(content_id, feedback_type, current_rank=None,
                    rank_change=None, recommendation=""):
    """피드백 루프 분석 결과 기록."""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO feedback_actions
                (created_at, content_id, feedback_type, current_rank,
                 rank_change, recommendation)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            content_id, feedback_type, current_rank,
            rank_change, recommendation
        ))
    return True


# ─────────────────────────────────────────────
# READ OPERATIONS
# ─────────────────────────────────────────────

def get_tracked_contents(active_only=True):
    """추적 대상 콘텐츠 목록 조회."""
    with get_db() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM tracked_contents WHERE is_active = 1"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM tracked_contents").fetchall()
    result = []
    for r in rows:
        item = dict(r)
        item["supporting_keywords"] = json.loads(item.get("supporting_keywords") or "[]")
        item["layman_terms"] = json.loads(item.get("layman_terms") or "[]")
        result.append(item)
    return result


def get_rank_history(content_id, keyword=None, days=30):
    """특정 콘텐츠의 키워드 순위 이력 조회."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as conn:
        if keyword:
            rows = conn.execute("""
                SELECT * FROM keyword_rank_history
                WHERE content_id = ? AND keyword = ? AND recorded_at >= ?
                ORDER BY recorded_at ASC
            """, (content_id, keyword, since)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM keyword_rank_history
                WHERE content_id = ? AND recorded_at >= ?
                ORDER BY recorded_at ASC, keyword
            """, (content_id, since)).fetchall()
    return [dict(r) for r in rows]


def get_blog_index_history(blog_id, days=30):
    """블로그 지수 이력 조회."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM blog_index_history
            WHERE blog_id = ? AND recorded_at >= ?
            ORDER BY recorded_at ASC
        """, (blog_id, since)).fetchall()
    return [dict(r) for r in rows]


def get_latest_ranks(content_id=None):
    """최신 순위 데이터 조회 (전체 또는 특정 콘텐츠)."""
    with get_db() as conn:
        if content_id:
            rows = conn.execute("""
                SELECT h.* FROM keyword_rank_history h
                INNER JOIN (
                    SELECT content_id, keyword, MAX(recorded_at) as max_date
                    FROM keyword_rank_history
                    WHERE content_id = ?
                    GROUP BY content_id, keyword
                ) latest ON h.content_id = latest.content_id
                    AND h.keyword = latest.keyword
                    AND h.recorded_at = latest.max_date
            """, (content_id,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT h.* FROM keyword_rank_history h
                INNER JOIN (
                    SELECT content_id, keyword, MAX(recorded_at) as max_date
                    FROM keyword_rank_history
                    GROUP BY content_id, keyword
                ) latest ON h.content_id = latest.content_id
                    AND h.keyword = latest.keyword
                    AND h.recorded_at = latest.max_date
            """).fetchall()
    return [dict(r) for r in rows]


def get_rank_trend(content_id, keyword, days=14):
    """특정 키워드의 순위 추세 (상승/하락 판단)."""
    history = get_rank_history(content_id, keyword, days)
    if len(history) < 2:
        return {"trend": "insufficient_data", "data_points": len(history)}

    ranks = [h["rank"] for h in history if h["rank"] is not None]
    if not ranks:
        return {"trend": "not_indexed", "data_points": 0}

    first_half = ranks[:len(ranks)//2]
    second_half = ranks[len(ranks)//2:]

    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    change = avg_second - avg_first  # 음수 = 순위 상승 (좋음)

    if change <= -5:
        trend = "rising_fast"
    elif change <= -1:
        trend = "rising"
    elif change >= 5:
        trend = "falling_fast"
    elif change >= 1:
        trend = "falling"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "avg_first_half": round(avg_first, 1),
        "avg_second_half": round(avg_second, 1),
        "change": round(change, 1),
        "best_rank": min(ranks),
        "worst_rank": max(ranks),
        "latest_rank": ranks[-1],
        "data_points": len(ranks)
    }


def get_content_performance_summary(content_id):
    """콘텐츠별 종합 성과 요약."""
    latest = get_latest_ranks(content_id)
    result = {
        "content_id": content_id,
        "keywords_tracked": len(latest),
        "keywords_in_top10": 0,
        "keywords_in_top20": 0,
        "keywords_not_indexed": 0,
        "best_keyword": None,
        "best_rank": None,
        "details": []
    }

    for r in latest:
        rank = r.get("rank")
        kw = r.get("keyword", "")
        if rank is None:
            result["keywords_not_indexed"] += 1
        else:
            if rank <= 10:
                result["keywords_in_top10"] += 1
            if rank <= 20:
                result["keywords_in_top20"] += 1
            if result["best_rank"] is None or rank < result["best_rank"]:
                result["best_rank"] = rank
                result["best_keyword"] = kw
        result["details"].append({
            "keyword": kw,
            "keyword_type": r.get("keyword_type", ""),
            "rank": rank,
            "recorded_at": r.get("recorded_at", "")
        })

    return result


def get_db_stats():
    """데이터베이스 통계."""
    with get_db() as conn:
        stats = {}
        stats["tracked_contents"] = conn.execute(
            "SELECT COUNT(*) FROM tracked_contents WHERE is_active = 1"
        ).fetchone()[0]
        stats["total_rank_records"] = conn.execute(
            "SELECT COUNT(*) FROM keyword_rank_history"
        ).fetchone()[0]
        stats["total_index_records"] = conn.execute(
            "SELECT COUNT(*) FROM blog_index_history"
        ).fetchone()[0]
        stats["total_feedback_actions"] = conn.execute(
            "SELECT COUNT(*) FROM feedback_actions"
        ).fetchone()[0]

        first_record = conn.execute(
            "SELECT MIN(recorded_at) FROM keyword_rank_history"
        ).fetchone()[0]
        last_record = conn.execute(
            "SELECT MAX(recorded_at) FROM keyword_rank_history"
        ).fetchone()[0]
        stats["first_record_date"] = first_record
        stats["last_record_date"] = last_record

        if first_record and last_record:
            d1 = datetime.strptime(first_record, "%Y-%m-%d")
            d2 = datetime.strptime(last_record, "%Y-%m-%d")
            stats["tracking_days"] = (d2 - d1).days + 1
        else:
            stats["tracking_days"] = 0

    return stats


# ─────────────────────────────────────────────
# INITIALIZATION: Auto-register from CONTENT_REGISTRY.csv
# ─────────────────────────────────────────────

def auto_register_from_registry(blog_id=""):
    """실제 발행 URL·발행일이 있는 PUBLISHED 콘텐츠만 추적 등록."""
    import csv
    import yaml

    registry_path = os.path.join(
        BASE_DIR, "content-system", "registry", "CONTENT_REGISTRY.csv"
    )
    briefs_dir = os.path.join(
        BASE_DIR, "content-system", "01_keyword_ai", "briefs"
    )

    if not os.path.exists(registry_path):
        print(f"[WARN] Registry not found: {registry_path}")
        return []

    registered = []
    with open(registry_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get("status", "").strip()
            cid = row.get("content_id", "").strip()
            if not cid or status != "PUBLISHED" or not row.get('published_url') or not row.get('published_date'):
                continue

            # Brief에서 상세 키워드 정보 가져오기
            brief_path = os.path.join(briefs_dir, f"{cid}.brief.yaml")
            supporting = []
            layman = []
            primary_kw = row.get("primary_keyword", "").strip()

            if os.path.exists(brief_path):
                try:
                    with open(brief_path, "r", encoding="utf-8") as bf:
                        brief = yaml.safe_load(bf)
                    search = brief.get("search", {})
                    if not primary_kw:
                        primary_kw = search.get("primary_keyword", "")
                    supporting = search.get("supporting_keywords", [])
                    layman = search.get("layman_terms", [])
                except Exception as e:
                    print(f"[WARN] Brief parse error for {cid}: {e}")

            register_content(
                content_id=cid,
                blog_id=blog_id,
                title=row.get("title", ""),
                primary_keyword=primary_kw,
                supporting_keywords=supporting,
                layman_terms=layman,
                canonical_topic=row.get("canonical_topic", ""),
                published_date=row.get("published_date"),
                published_url=row.get("published_url", "")
            )
            registered.append(cid)
            print(f"  ✓ Registered: {cid} ({primary_kw})")

    return registered


# Auto-initialize on first import
init_db()
