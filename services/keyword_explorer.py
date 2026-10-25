"""
keyword_explorer.py
===================
Customer Language DB 핵심 탐색 및 그래프 분석 엔진.
네이버 SearchAd API의 relKeyword 수확 + 4소스 문서량(total) 기반 일반인지수(layman_score) 계산
+ 의미 클러스터(Jaccard relKeyword overlap) + 2-hop 자동 확장.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime
import io
import json
import os
import sqlite3
import sys
import time
from typing import Any, Callable, Iterator, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from .keyword_volume import SearchAdClient, _key, _to_int
    from .naver_search_client import NaverSearchClient
except ImportError:
    from services.keyword_volume import SearchAdClient, _key, _to_int
    from services.naver_search_client import NaverSearchClient

DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "keyword_graph.db")


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()


def layman_score(node: dict) -> float:
    """0.0(전문가/업계용어) ~ 1.0(완전 일반인/고객언어) 계산."""
    blog = node.get("blog_total") or 0
    cafe = node.get("cafe_total") or 0
    kin = node.get("kin_total") or 0
    web = node.get("web_total") or 0
    total = blog + cafe + kin + web

    query = node.get("query", "")
    is_question = any(query.endswith(s) for s in ("요", "까", "법", "방법")) or "?" in query
    has_expert_term = any(t in query for t in ("솔루션", "시스템", "구축", "인프라", "SIP", "코덱", "MCU"))
    has_colloquial = any(t in query for t in ("안들려", "안들림", "안됨", "소리", "울림", "하울링", "따라가는", "잡아주는"))

    if total == 0:
        score = 0.5
        if is_question or has_colloquial:
            score += 0.25
        if has_expert_term:
            score -= 0.25
        return round(max(0.0, min(1.0, score)), 3)

    kin_ratio = kin / total
    cafe_ratio = cafe / total

    score = (kin_ratio * 0.45) + (cafe_ratio * 0.35)
    if is_question or has_colloquial:
        score += 0.2
    if has_expert_term:
        score -= 0.2

    return round(max(0.0, min(1.0, score)), 3)


DEFAULT_TAXONOMY_PATH = os.path.join(BASE_DIR, "data", "product_taxonomy.json")


class ProductAffinityScorer:
    """화상회의 장비(랠리바, 밋업2, 마이크팟, 탭 등) 및 솔루션과의 의미적 제품 연관도(0.0~1.0) 계산."""

    def __init__(self, taxonomy_path: str = DEFAULT_TAXONOMY_PATH):
        self.taxonomy_path = taxonomy_path
        self.taxonomy = self._load_taxonomy()

    def _load_taxonomy(self) -> dict:
        if os.path.exists(self.taxonomy_path):
            try:
                with open(self.taxonomy_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"products": {}, "global_context": {}}

    @staticmethod
    def _normalize(text: str) -> str:
        import re
        return re.sub(r"[\s\-_·\(\)]+", "", text).lower()

    def score(self, query: str) -> dict[str, Any]:
        q_norm = self._normalize(query)
        products_def = self.taxonomy.get("products", {})
        global_ctx = self.taxonomy.get("global_context", {})

        matched_products: list[str] = []
        product_names: list[str] = []
        best_product_score = 0.0
        details: list[str] = []

        # 1. 개별 제품별 매칭 (명칭, 기능, 문제해결, 전용맥락)
        for prod_key, prod_info in products_def.items():
            prod_score = 0.0
            prod_matched_reasons = []

            for syn in prod_info.get("synonyms", []):
                syn_norm = self._normalize(syn)
                if syn_norm and syn_norm in q_norm:
                    prod_score = max(prod_score, 0.90)
                    prod_matched_reasons.append(f"제품명 '{syn}'")
                    break

            for feat in prod_info.get("features", []):
                feat_norm = self._normalize(feat)
                if feat_norm and feat_norm in q_norm:
                    prod_score = max(prod_score, 0.75)
                    prod_matched_reasons.append(f"기능 '{feat}'")
                    break

            for prob in prod_info.get("problems_solved", []):
                prob_norm = self._normalize(prob)
                if prob_norm and prob_norm in q_norm:
                    prod_score = max(prod_score, 0.65)
                    prod_matched_reasons.append(f"문제해결 '{prob}'")
                    break

            for uctx in prod_info.get("use_contexts", []):
                uctx_norm = self._normalize(uctx)
                if uctx_norm and uctx_norm in q_norm:
                    prod_score = max(prod_score, prod_score + 0.10)
                    prod_matched_reasons.append(f"공간 '{uctx}'")
                    break

            weight = prod_info.get("weight", 1.0)
            weighted_score = min(1.0, prod_score * weight)

            if weighted_score >= 0.40:
                matched_products.append(prod_key)
                name = prod_info.get("name_ko", prod_key).split("/")[0].strip()
                if name not in product_names:
                    product_names.append(name)
                if weighted_score > best_product_score:
                    best_product_score = weighted_score
                details.extend([f"{prod_key}: {r}" for r in prod_matched_reasons])

        # 2. 글로벌 긍정 맥락 검사
        context_score = 0.0
        for ctx in global_ctx.get("positive_contexts", []):
            term_norm = self._normalize(ctx["term"])
            if term_norm and term_norm in q_norm:
                context_score += ctx["score"]
                details.append(f"맥락 '{ctx['term']}' (+{ctx['score']})")
        context_score = min(0.6, context_score)

        # 3. 의도 시그널 검사 (설치, 세팅, 비교, 추천 등)
        intent_score = 0.0
        for it in global_ctx.get("intent_signals", []):
            term_norm = self._normalize(it["term"])
            if term_norm and term_norm in q_norm:
                intent_score += it["score"]
                details.append(f"의도 '{it['term']}' (+{it['score']})")
        intent_score = min(0.5, intent_score)

        # 4. 부정 시그널 (무관 카테고리 감점)
        penalty = 0.0
        for neg in global_ctx.get("negative_signals", []):
            term_norm = self._normalize(neg["term"])
            if term_norm and term_norm in q_norm:
                penalty += neg["penalty"]
                details.append(f"무관패널티 '{neg['term']}' (-{neg['penalty']})")

        # 5. 최종 종합 Affinity 계산
        has_hw = any(hw in q_norm for hw in ("카메라", "마이크", "스피커", "웹캠", "장비", "화면", "디스플레이", "tv", "ptz"))

        if best_product_score > 0:
            raw_affinity = (best_product_score * 0.65) + (context_score * 0.20) + (intent_score * 0.15)
            if has_hw:
                raw_affinity += 0.05
        elif context_score > 0.20:
            if has_hw:
                raw_affinity = 0.55 + (context_score * 0.25) + (intent_score * 0.20)
                matched_products.append("video_conference_general")
                product_names.append("화상회의 장비")
            else:
                raw_affinity = (context_score * 0.35) + (intent_score * 0.25)
        else:
            if has_hw:
                raw_affinity = 0.15 + (intent_score * 0.15)
            else:
                raw_affinity = 0.02

        final_affinity = max(0.0, min(1.0, raw_affinity - penalty))
        return {
            "query": query,
            "product_affinity": round(final_affinity, 3),
            "target_products": matched_products,
            "target_product_names": product_names,
            "best_product_score": round(best_product_score, 3),
            "context_score": round(context_score, 3),
            "intent_score": round(intent_score, 3),
            "penalty": round(penalty, 3),
            "reasons": details,
        }


def content_opportunity_score(layman: float, affinity: float, volume: int = 0) -> float:
    """일반인 지수와 제품 연관도, 검색량을 결합한 최종 콘텐츠 발행 기회 점수(0.0 ~ 1.0)."""
    if affinity < 0.25:
        return 0.0
    import math
    base = (layman * 0.40) + (affinity * 0.60)
    vol_factor = min(1.0, max(0.3, math.log10(max(10, volume)) / 4.0))
    return round(base * vol_factor, 3)



class ExplorerStore:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.init_db()

    @contextlib.contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def init_db(self) -> None:
        with self.conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS query_nodes (
                query             TEXT PRIMARY KEY,
                query_norm        TEXT NOT NULL,
                source_type       TEXT,
                source_query      TEXT,
                depth             INTEGER DEFAULT 0,
                monthly_pc        INTEGER,
                monthly_mobile    INTEGER,
                monthly_total     INTEGER,
                competition       TEXT,
                avg_pc_ctr        REAL,
                avg_mobile_ctr    REAL,
                intent            TEXT,
                language_level    TEXT,
                context           TEXT,
                device_category   TEXT,
                platform          TEXT,
                blog_total        INTEGER,
                cafe_total        INTEGER,
                kin_total         INTEGER,
                web_total         INTEGER,
                layman_score      REAL,
                product_affinity  REAL DEFAULT 0.0,
                target_products   TEXT,
                opportunity_score REAL DEFAULT 0.0,
                explored_at       TEXT,
                updated_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS query_edges (
                source_query    TEXT NOT NULL,
                target_query    TEXT NOT NULL,
                edge_type       TEXT DEFAULT 'searchad_rel',
                weight          REAL DEFAULT 1.0,
                discovered_at   TEXT,
                PRIMARY KEY (source_query, target_query, edge_type)
            );

            CREATE TABLE IF NOT EXISTS concept_map (
                concept_id      TEXT NOT NULL,
                query           TEXT NOT NULL,
                tier            TEXT,
                PRIMARY KEY (concept_id, query)
            );

            CREATE TABLE IF NOT EXISTS seed_config (
                query           TEXT PRIMARY KEY,
                seed_group      TEXT,
                intent          TEXT,
                language_level  TEXT,
                active          INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS ix_edges_target ON query_edges(target_query);
            CREATE INDEX IF NOT EXISTS ix_edges_source ON query_edges(source_query);
            CREATE INDEX IF NOT EXISTS ix_nodes_source ON query_nodes(source_query);
            CREATE INDEX IF NOT EXISTS ix_nodes_depth ON query_nodes(depth);
            CREATE INDEX IF NOT EXISTS ix_nodes_monthly_total ON query_nodes(monthly_total);
            CREATE INDEX IF NOT EXISTS ix_nodes_layman ON query_nodes(layman_score);
            """)

            # 기존 DB 스키마 마이그레이션 (컬럼이 없을 경우 추가)
            cursor = conn.execute("PRAGMA table_info(query_nodes)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "product_affinity" not in existing_cols:
                conn.execute("ALTER TABLE query_nodes ADD COLUMN product_affinity REAL DEFAULT 0.0")
            if "target_products" not in existing_cols:
                conn.execute("ALTER TABLE query_nodes ADD COLUMN target_products TEXT")
            if "opportunity_score" not in existing_cols:
                conn.execute("ALTER TABLE query_nodes ADD COLUMN opportunity_score REAL DEFAULT 0.0")

            conn.execute("CREATE INDEX IF NOT EXISTS ix_nodes_affinity ON query_nodes(product_affinity)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_nodes_opportunity ON query_nodes(opportunity_score)")

    def upsert_node(self, node: dict) -> None:
        now = _now_iso()
        q = node["query"].strip()
        q_norm = _key(q)

        # Affinity 및 기회 점수 계산 (만약 제공되지 않았다면)
        affinity = node.get("product_affinity")
        target_prods = node.get("target_products")
        if affinity is None:
            scorer = ProductAffinityScorer()
            s_res = scorer.score(q)
            affinity = s_res["product_affinity"]
            target_prods = json.dumps(s_res["target_product_names"], ensure_ascii=False)
        elif isinstance(target_prods, list):
            target_prods = json.dumps(target_prods, ensure_ascii=False)

        layman = node.get("layman_score")
        if layman is None:
            layman = layman_score({"query": q})

        vol = node.get("monthly_total") or 0
        opp_score = node.get("opportunity_score")
        if opp_score is None:
            opp_score = content_opportunity_score(layman, affinity, vol)

        with self.conn() as conn:
            conn.execute("""
            INSERT INTO query_nodes (
                query, query_norm, source_type, source_query, depth,
                monthly_pc, monthly_mobile, monthly_total, competition,
                avg_pc_ctr, avg_mobile_ctr, intent, language_level,
                context, device_category, platform,
                blog_total, cafe_total, kin_total, web_total, layman_score,
                product_affinity, target_products, opportunity_score,
                explored_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?
            )
            ON CONFLICT(query) DO UPDATE SET
                source_type = COALESCE(query_nodes.source_type, excluded.source_type),
                source_query = COALESCE(query_nodes.source_query, excluded.source_query),
                depth = MIN(query_nodes.depth, excluded.depth),
                monthly_pc = COALESCE(excluded.monthly_pc, query_nodes.monthly_pc),
                monthly_mobile = COALESCE(excluded.monthly_mobile, query_nodes.monthly_mobile),
                monthly_total = COALESCE(excluded.monthly_total, query_nodes.monthly_total),
                competition = COALESCE(excluded.competition, query_nodes.competition),
                avg_pc_ctr = COALESCE(excluded.avg_pc_ctr, query_nodes.avg_pc_ctr),
                avg_mobile_ctr = COALESCE(excluded.avg_mobile_ctr, query_nodes.avg_mobile_ctr),
                intent = COALESCE(excluded.intent, query_nodes.intent),
                language_level = COALESCE(excluded.language_level, query_nodes.language_level),
                context = COALESCE(excluded.context, query_nodes.context),
                device_category = COALESCE(excluded.device_category, query_nodes.device_category),
                platform = COALESCE(excluded.platform, query_nodes.platform),
                blog_total = COALESCE(excluded.blog_total, query_nodes.blog_total),
                cafe_total = COALESCE(excluded.cafe_total, query_nodes.cafe_total),
                kin_total = COALESCE(excluded.kin_total, query_nodes.kin_total),
                web_total = COALESCE(excluded.web_total, query_nodes.web_total),
                layman_score = COALESCE(excluded.layman_score, query_nodes.layman_score),
                product_affinity = COALESCE(excluded.product_affinity, query_nodes.product_affinity),
                target_products = COALESCE(excluded.target_products, query_nodes.target_products),
                opportunity_score = COALESCE(excluded.opportunity_score, query_nodes.opportunity_score),
                updated_at = excluded.updated_at
            """, (
                q, q_norm, node.get("source_type"), node.get("source_query"), node.get("depth", 0),
                node.get("monthly_pc"), node.get("monthly_mobile"), node.get("monthly_total"), node.get("competition"),
                node.get("avg_pc_ctr"), node.get("avg_mobile_ctr"), node.get("intent"), node.get("language_level"),
                node.get("context"), node.get("device_category"), node.get("platform"),
                node.get("blog_total"), node.get("cafe_total"), node.get("kin_total"), node.get("web_total"),
                layman, affinity, target_prods, opp_score,
                node.get("explored_at", now), now
            ))

    def upsert_edge(self, source_query: str, target_query: str, edge_type: str = "searchad_rel", weight: float = 1.0) -> None:
        now = _now_iso()
        with self.conn() as conn:
            conn.execute("""
            INSERT INTO query_edges (source_query, target_query, edge_type, weight, discovered_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_query, target_query, edge_type) DO UPDATE SET
                weight = excluded.weight
            """, (source_query.strip(), target_query.strip(), edge_type, weight, now))

    def save_seed_config(self, seed: dict) -> None:
        with self.conn() as conn:
            conn.execute("""
            INSERT INTO seed_config (query, seed_group, intent, language_level, active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(query) DO UPDATE SET
                seed_group = excluded.seed_group,
                intent = excluded.intent,
                language_level = excluded.language_level,
                active = excluded.active
            """, (seed["query"].strip(), seed.get("group"), seed.get("intent"), seed.get("language_level"), 1))

    def get_summary(self) -> dict:
        with self.conn() as conn:
            total_nodes = conn.execute("SELECT COUNT(*) FROM query_nodes").fetchone()[0]
            seeds_count = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE depth = 0").fetchone()[0]
            hop1_count = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE depth = 1").fetchone()[0]
            hop2_count = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE depth = 2").fetchone()[0]
            total_edges = conn.execute("SELECT COUNT(*) FROM query_edges").fetchone()[0]
            overlap_edges = conn.execute("SELECT COUNT(*) FROM query_edges WHERE edge_type = 'result_overlap'").fetchone()[0]
            total_volume = conn.execute("SELECT SUM(monthly_total) FROM query_nodes WHERE monthly_total IS NOT NULL").fetchone()[0] or 0
            avg_layman = conn.execute("SELECT AVG(layman_score) FROM query_nodes WHERE layman_score IS NOT NULL").fetchone()[0] or 0.0
            avg_affinity = conn.execute("SELECT AVG(product_affinity) FROM query_nodes WHERE product_affinity IS NOT NULL").fetchone()[0] or 0.0
            high_affinity_count = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE product_affinity >= 0.5").fetchone()[0]
            opportunity_count = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE opportunity_score >= 0.3").fetchone()[0]
            with_totals = conn.execute("SELECT COUNT(*) FROM query_nodes WHERE blog_total IS NOT NULL").fetchone()[0]

            return {
                "total_nodes": total_nodes,
                "seeds_count": seeds_count,
                "hop1_count": hop1_count,
                "hop2_count": hop2_count,
                "total_edges": total_edges,
                "overlap_edges": overlap_edges,
                "total_volume": total_volume,
                "avg_layman": round(avg_layman, 3),
                "avg_affinity": round(avg_affinity, 3),
                "high_affinity_count": high_affinity_count,
                "opportunity_count": opportunity_count,
                "nodes_with_totals": with_totals,
            }

    def list_nodes(self, limit: int = 100, offset: int = 0, sort_by: str = "monthly_total",
                   desc: bool = True, depth: Optional[int] = None, search: Optional[str] = None,
                   language_level: Optional[str] = None, min_affinity: Optional[float] = None,
                   product: Optional[str] = None) -> tuple[list[dict], int]:
        allowed_sort = {
            "monthly_total", "monthly_pc", "monthly_mobile", "layman_score",
            "product_affinity", "opportunity_score", "query", "depth", "blog_total", "kin_total"
        }
        if sort_by not in allowed_sort:
            sort_by = "monthly_total"

        direction = "DESC" if desc else "ASC"
        where_clauses = ["1=1"]
        params: list[Any] = []

        if depth is not None:
            where_clauses.append("depth = ?")
            params.append(depth)
        if search:
            where_clauses.append("query LIKE ?")
            params.append(f"%{search.strip()}%")
        if language_level:
            where_clauses.append("language_level = ?")
            params.append(language_level)
        if min_affinity is not None:
            where_clauses.append("product_affinity >= ?")
            params.append(float(min_affinity))
        if product:
            where_clauses.append("target_products LIKE ?")
            params.append(f"%{product.strip()}%")

        where_sql = " AND ".join(where_clauses)

        with self.conn() as conn:
            count_sql = f"SELECT COUNT(*) FROM query_nodes WHERE {where_sql}"
            total_count = conn.execute(count_sql, params).fetchone()[0]

            query_sql = f"""
            SELECT * FROM query_nodes
            WHERE {where_sql}
            ORDER BY {sort_by} {direction} NULLS LAST
            LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, params + [limit, offset]).fetchall()
            return [dict(r) for r in rows], total_count

    def recalculate_all_affinity(self) -> dict[str, int]:
        """기존 DB 내의 모든 노드에 대해 ProductAffinityScorer를 적용하여 product_affinity 및 opportunity_score 일괄 갱신."""
        scorer = ProductAffinityScorer()
        now = _now_iso()

        with self.conn() as conn:
            rows = conn.execute("SELECT query, layman_score, monthly_total FROM query_nodes").fetchall()
            updated_count = 0
            high_count = 0

            updates = []
            for r in rows:
                q = r["query"]
                s_res = scorer.score(q)
                aff = s_res["product_affinity"]
                prods_json = json.dumps(s_res["target_product_names"], ensure_ascii=False)

                layman = r["layman_score"] or 0.5
                vol = r["monthly_total"] or 0
                opp = content_opportunity_score(layman, aff, vol)

                if aff >= 0.5:
                    high_count += 1
                updates.append((aff, prods_json, opp, now, q))

            conn.executemany("""
            UPDATE query_nodes SET
                product_affinity = ?,
                target_products = ?,
                opportunity_score = ?,
                updated_at = ?
            WHERE query = ?
            """, updates)

            return {
                "total_processed": len(rows),
                "high_affinity_count": high_count
            }

    def get_node(self, query: str) -> Optional[dict]:
        with self.conn() as conn:
            row = conn.execute("SELECT * FROM query_nodes WHERE query = ?", (query.strip(),)).fetchone()
            return dict(row) if row else None

    def get_graph_data(self, min_volume: int = 50, limit_nodes: int = 150) -> dict:
        """D3.js force-directed graph용 nodes + links 반환."""
        with self.conn() as conn:
            node_rows = conn.execute("""
            SELECT query, depth, monthly_total, layman_score, product_affinity, opportunity_score,
                   target_products, language_level, source_type
            FROM query_nodes
            WHERE depth = 0 OR (monthly_total IS NOT NULL AND monthly_total >= ?)
            ORDER BY depth ASC, monthly_total DESC
            LIMIT ?
            """, (min_volume, limit_nodes)).fetchall()

            node_set = {r["query"] for r in node_rows}
            nodes = [
                {
                    "id": r["query"],
                    "depth": r["depth"],
                    "volume": r["monthly_total"] or 0,
                    "layman_score": r["layman_score"] or 0.5,
                    "product_affinity": r["product_affinity"] or 0.0,
                    "opportunity_score": r["opportunity_score"] or 0.0,
                    "target_products": r["target_products"] or "[]",
                    "language_level": r["language_level"] or ("expert" if r["depth"] == 0 else "general"),
                    "source_type": r["source_type"]
                }
                for r in node_rows
            ]

            if not node_set:
                return {"nodes": [], "links": []}

            placeholders = ",".join("?" for _ in node_set)
            edge_rows = conn.execute(f"""
            SELECT source_query, target_query, edge_type, weight
            FROM query_edges
            WHERE source_query IN ({placeholders}) AND target_query IN ({placeholders})
            """, list(node_set) + list(node_set)).fetchall()

            links = [
                {
                    "source": r["source_query"],
                    "target": r["target_query"],
                    "type": r["edge_type"],
                    "weight": r["weight"]
                }
                for r in edge_rows
            ]

            return {"nodes": nodes, "links": links}

    def get_nodes_pending_totals(self, limit: Optional[int] = None) -> list[dict]:
        with self.conn() as conn:
            sql = "SELECT * FROM query_nodes WHERE blog_total IS NULL ORDER BY depth ASC, monthly_total DESC NULLS LAST"
            if limit:
                sql += f" LIMIT {int(limit)}"
            rows = conn.execute(sql).fetchall()
            return [dict(r) for r in rows]

    def update_totals_and_score(self, query: str, totals: dict[str, int]) -> None:
        now = _now_iso()
        with self.conn() as conn:
            row = conn.execute("SELECT * FROM query_nodes WHERE query = ?", (query,)).fetchone()
            if not row:
                return
            node_dict = dict(row)
            node_dict.update({
                "blog_total": totals.get("blog", 0),
                "cafe_total": totals.get("cafearticle", 0),
                "kin_total": totals.get("kin", 0),
                "web_total": totals.get("webkr", 0),
            })
            score = layman_score(node_dict)

            level = node_dict.get("language_level")
            if not level or level == "general":
                if score >= 0.7:
                    level = "colloquial"
                elif score <= 0.2:
                    level = "expert"
                elif score <= 0.4:
                    level = "business"
                else:
                    level = "general"

            affinity = node_dict.get("product_affinity") or 0.0
            vol = node_dict.get("monthly_total") or 0
            opp_score = content_opportunity_score(score, affinity, vol)

            conn.execute("""
            UPDATE query_nodes SET
                blog_total = ?, cafe_total = ?, kin_total = ?, web_total = ?,
                layman_score = ?, opportunity_score = ?, language_level = ?, updated_at = ?
            WHERE query = ?
            """, (
                totals.get("blog", 0), totals.get("cafearticle", 0),
                totals.get("kin", 0), totals.get("webkr", 0),
                score, opp_score, level, now, query
            ))

    def get_all_seed_rels(self) -> dict[str, set[str]]:
        with self.conn() as conn:
            rows = conn.execute("""
            SELECT source_query, target_query
            FROM query_edges
            WHERE edge_type = 'searchad_rel'
            """).fetchall()
            mapping: dict[str, set[str]] = {}
            for r in rows:
                mapping.setdefault(r["source_query"], set()).add(r["target_query"])
            return mapping

    def select_candidates_for_expansion(self, max_count: int = 30) -> list[dict]:
        with self.conn() as conn:
            rows = conn.execute("""
            SELECT * FROM query_nodes
            WHERE depth = 1
              AND (monthly_total IS NOT NULL AND monthly_total >= 50)
              AND (layman_score IS NULL OR layman_score >= 0.35)
            ORDER BY layman_score DESC NULLS LAST, monthly_total DESC
            LIMIT ?
            """, (max_count,)).fetchall()
            return [dict(r) for r in rows]

    def export_csv(self) -> str:
        with self.conn() as conn:
            rows = conn.execute("""
            SELECT query, depth, source_type, source_query, monthly_pc, monthly_mobile, monthly_total,
                   competition, layman_score, product_affinity, opportunity_score, target_products,
                   language_level, blog_total, cafe_total, kin_total, web_total
            FROM query_nodes
            ORDER BY opportunity_score DESC, product_affinity DESC, monthly_total DESC NULLS LAST
            """).fetchall()

            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                "검색어", "단계(Depth)", "소스유형", "발견시드", "PC검색량", "모바일검색량", "총검색량",
                "경쟁도", "일반인지수", "제품연관도", "콘텐츠기회점수", "타깃제품", "언어등급", "블로그문서수", "카페문서수", "지식iN문서수", "웹문서수"
            ])
            for r in rows:
                writer.writerow([
                    r["query"], r["depth"], r["source_type"], r["source_query"] or "",
                    r["monthly_pc"] or 0, r["monthly_mobile"] or 0, r["monthly_total"] or 0,
                    r["competition"] or "", r["layman_score"] or 0.0, r["product_affinity"] or 0.0,
                    r["opportunity_score"] or 0.0, r["target_products"] or "", r["language_level"] or "",
                    r["blog_total"] or 0, r["cafe_total"] or 0, r["kin_total"] or 0, r["web_total"] or 0
                ])
            return buf.getvalue()


# ----------------------------------------------------------------------
# 탐색 실행 로직
# ----------------------------------------------------------------------

def explore_seeds(seeds: list[dict], client: SearchAdClient, store: ExplorerStore,
                  *, depth: int = 1) -> dict:
    """시드 목록을 SearchAd API로 탐색하여 relKeyword 및 검색량을 DB에 저장."""
    for s in seeds:
        store.save_seed_config(s)
        store.upsert_node({
            "query": s["query"],
            "source_type": "seed",
            "source_query": None,
            "depth": 0,
            "intent": s.get("intent"),
            "language_level": s.get("language_level", "general"),
            "layman_score": layman_score({"query": s["query"]}),
        })

    queries = [s["query"] for s in seeds]
    discovered_nodes = 0
    discovered_edges = 0

    for i in range(0, len(queries), 5):
        chunk = queries[i:i + 5]
        try:
            rel_rows = client.keyword_relatives(chunk)
        except Exception as e:
            print(f"Error exploring chunk {chunk}: {e}", file=sys.stderr)
            continue

        for r in rel_rows:
            rel_kw = r.get("relKeyword", "").strip()
            if not rel_kw:
                continue

            pc = _to_int(r.get("monthlyPcQcCnt") if r.get("monthlyPcQcCnt") is not None else r.get("monthlyPcQryCnt"))
            mobile = _to_int(r.get("monthlyMobileQcCnt") if r.get("monthlyMobileQcCnt") is not None else r.get("monthlyMobileQryCnt"))
            total = pc + mobile if isinstance(pc, int) and isinstance(mobile, int) else None
            comp = r.get("compIdx") or r.get("competition") or ""
            pc_ctr = float(r.get("monthlyAvePcCtr") or 0.0)
            mob_ctr = float(r.get("monthlyAveMobileCtr") or 0.0)

            store.upsert_node({
                "query": rel_kw,
                "source_type": "rel_1hop",
                "source_query": chunk[0] if len(chunk) == 1 else "batch_seed",
                "depth": 1,
                "monthly_pc": pc,
                "monthly_mobile": mobile,
                "monthly_total": total,
                "competition": comp,
                "avg_pc_ctr": pc_ctr,
                "avg_mobile_ctr": mob_ctr,
                "layman_score": layman_score({"query": rel_kw}),
            })
            discovered_nodes += 1

            for c_query in chunk:
                store.upsert_edge(c_query, rel_kw, "searchad_rel", 1.0)
                discovered_edges += 1

    return {
        "seeds_count": len(seeds),
        "discovered_nodes": discovered_nodes,
        "discovered_edges": discovered_edges
    }


def compute_overlap_edges(store: ExplorerStore, threshold: float = 0.15) -> int:
    """시드 간 relKeyword의 Jaccard 유사도를 계산하여 result_overlap 엣지 생성."""
    seed_rels = store.get_all_seed_rels()
    seeds = list(seed_rels.keys())
    added = 0

    for i in range(len(seeds)):
        s1 = seeds[i]
        set1 = seed_rels[s1]
        if not set1:
            continue
        for j in range(i + 1, len(seeds)):
            s2 = seeds[j]
            set2 = seed_rels[s2]
            if not set2:
                continue

            intersection = len(set1 & set2)
            if not intersection:
                continue
            union = len(set1 | set2)
            jaccard = intersection / union if union else 0.0

            if jaccard >= threshold:
                store.upsert_edge(s1, s2, "result_overlap", round(jaccard, 3))
                store.upsert_edge(s2, s1, "result_overlap", round(jaccard, 3))
                added += 2

    return added


def collect_document_totals(store: ExplorerStore, client: NaverSearchClient, max_queries: Optional[int] = None) -> int:
    """4개 소스(blog, cafe, kin, webkr) 문서 수집 및 일반인지수 갱신."""
    pending = store.get_nodes_pending_totals(limit=max_queries)
    processed = 0
    for node in pending:
        q = node["query"]
        try:
            totals = client.totals(q)
            store.update_totals_and_score(q, totals)
            processed += 1
            if processed % 10 == 0:
                print(f"[Totals] {processed}/{len(pending)}: '{q}' -> {totals}")
        except Exception as e:
            print(f"[Totals Error] {q}: {e}", file=sys.stderr)
    return processed


def expand_hop_2(store: ExplorerStore, client: SearchAdClient, max_expand: int = 30) -> dict:
    """1-hop 고가치 키워드로 2-hop 확장 탐색."""
    candidates = store.select_candidates_for_expansion(max_count=max_expand)
    if not candidates:
        return {"expanded_seeds": 0, "discovered_nodes": 0}

    queries = [c["query"] for c in candidates]
    discovered_nodes = 0
    discovered_edges = 0

    for i in range(0, len(queries), 5):
        chunk = queries[i:i + 5]
        try:
            rel_rows = client.keyword_relatives(chunk)
        except Exception as e:
            print(f"Error expanding chunk {chunk}: {e}", file=sys.stderr)
            continue

        for r in rel_rows:
            rel_kw = r.get("relKeyword", "").strip()
            if not rel_kw:
                continue

            pc = _to_int(r.get("monthlyPcQcCnt") if r.get("monthlyPcQcCnt") is not None else r.get("monthlyPcQryCnt"))
            mobile = _to_int(r.get("monthlyMobileQcCnt") if r.get("monthlyMobileQcCnt") is not None else r.get("monthlyMobileQryCnt"))
            total = pc + mobile if isinstance(pc, int) and isinstance(mobile, int) else None
            comp = r.get("compIdx") or r.get("competition") or ""
            pc_ctr = float(r.get("monthlyAvePcCtr") or 0.0)
            mob_ctr = float(r.get("monthlyAveMobileCtr") or 0.0)

            store.upsert_node({
                "query": rel_kw,
                "source_type": "rel_2hop",
                "source_query": chunk[0] if len(chunk) == 1 else "hop1_seed",
                "depth": 2,
                "monthly_pc": pc,
                "monthly_mobile": mobile,
                "monthly_total": total,
                "competition": comp,
                "avg_pc_ctr": pc_ctr,
                "avg_mobile_ctr": mob_ctr,
                "layman_score": layman_score({"query": rel_kw}),
            })
            discovered_nodes += 1

            for c_query in chunk:
                store.upsert_edge(c_query, rel_kw, "searchad_rel", 0.8)
                discovered_edges += 1

    return {
        "expanded_seeds": len(candidates),
        "discovered_nodes": discovered_nodes,
        "discovered_edges": discovered_edges
    }


def _load_config_env() -> None:
    cfg_file = os.path.join(BASE_DIR, "config", "config.json")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, encoding="utf-8") as f:
                cdata = json.load(f)
                for k, env_key in [
                    ("ad_customer_id", "NAVER_SEARCHAD_CUSTOMER_ID"),
                    ("naver_searchad_customer_id", "NAVER_SEARCHAD_CUSTOMER_ID"),
                    ("ad_api_key", "NAVER_SEARCHAD_API_KEY"),
                    ("naver_searchad_api_key", "NAVER_SEARCHAD_API_KEY"),
                    ("ad_secret_key", "NAVER_SEARCHAD_SECRET_KEY"),
                    ("naver_searchad_secret_key", "NAVER_SEARCHAD_SECRET_KEY"),
                    ("naver_client_id", "NAVER_CLIENT_ID"),
                    ("naver_client_secret", "NAVER_CLIENT_SECRET"),
                ]:
                    if cdata.get(k):
                        os.environ.setdefault(env_key, str(cdata[k]))
        except Exception:
            pass


def main(argv: Optional[list] = None) -> int:
    _load_config_env()

    default_seeds = os.path.join(BASE_DIR, "config", "seeds.json")
    parser = argparse.ArgumentParser(description="Customer Language DB Keyword Explorer")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite DB path")
    parser.add_argument("--seeds", default=default_seeds, help="Path to seeds JSON")
    parser.add_argument("--depth", type=int, default=1, help="Exploration depth (1 or 2)")
    parser.add_argument("--totals", action="store_true", help="Collect 4-source document totals")
    parser.add_argument("--totals-limit", type=int, default=50, help="Max queries for document totals per run")
    parser.add_argument("--overlap", action="store_true", help="Compute Jaccard relKeyword overlap edges")
    parser.add_argument("--expand", action="store_true", help="Run 2-hop expansion on high-value keywords")
    parser.add_argument("--summary", action="store_true", help="Print summary statistics")
    parser.add_argument("--export-csv", help="Export keyword nodes to CSV file path")

    args = parser.parse_args(argv)
    store = ExplorerStore(args.db)

    if args.export_csv:
        csv_text = store.export_csv()
        with open(args.export_csv, "w", encoding="utf-8-sig") as f:
            f.write(csv_text)
        print(f"Exported to {args.export_csv}")
        return 0

    if args.summary:
        s = store.get_summary()
        print("\n=== Customer Language DB 요약 ===")
        print(f"총 키워드 수: {s['total_nodes']:,}개")
        print(f"  - 시드: {s['seeds_count']:,}개")
        print(f"  - 1-hop 발견: {s['hop1_count']:,}개")
        print(f"  - 2-hop 발견: {s['hop2_count']:,}개")
        print(f"총 연결(엣지): {s['total_edges']:,}개 (의미겹침: {s['overlap_edges']:,}개)")
        print(f"총 검색량 합계: {s['total_volume']:,}")
        print(f"평균 일반인지수: {s['avg_layman']}")
        print(f"문서량 수집 완료: {s['nodes_with_totals']:,}개")
        return 0

    if args.overlap:
        print("시드 간 연관키워드 Jaccard 유사도 계산 중...")
        n = compute_overlap_edges(store)
        print(f"생성된 의미 겹침 엣지: {n}개")
        return 0

    if args.totals:
        print(f"문서량(total) 수집 시작 (최대 {args.totals_limit}개)...")
        sc = NaverSearchClient()
        n = collect_document_totals(store, sc, max_queries=args.totals_limit)
        print(f"수집 완료: {n}개 키워드")
        return 0

    if args.expand:
        print("2-hop 확장 탐색 시작...")
        ac = SearchAdClient()
        res = expand_hop_2(store, ac)
        print(f"2-hop 확장 완료: 시드 {res['expanded_seeds']}개 -> 신규 {res['discovered_nodes']}개 발견")
        return 0

    if os.path.exists(args.seeds):
        with open(args.seeds, encoding="utf-8") as f:
            sdata = json.load(f)
            seeds = sdata.get("seeds", [])
        print(f"시드 {len(seeds)}개 탐색 시작...")
        ac = SearchAdClient()
        res = explore_seeds(seeds, ac, store, depth=args.depth)
        print(f"탐색 완료: {res}")

        print("의미 겹침 계산 중...")
        n_edges = compute_overlap_edges(store)
        print(f"추가된 의미 겹침 엣지: {n_edges}개")

        if args.depth >= 2:
            print("2-hop 확장 진행...")
            exp_res = expand_hop_2(store, ac)
            print(f"2-hop 결과: {exp_res}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
