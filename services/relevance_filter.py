"""
relevance_filter.py
===================
노출 점수로 뽑은 경쟁군 후보 중 "주제가 다른 블로그"를 자동으로 걸러내는 모듈.

동작
  1. 후보(노출 점수순)를 앞에서부터 RSS 로 확인한다. (pin 은 확인 없이 통과)
  2. 최근 글 20개 중 주제어가 제목에 들어간 비율(focus_ratio)이 min_focus 이상이면 채택
  3. RSS 를 받을 수 없어 판단 불가('unknown')인 블로그는 채택된 수가 top_n 에 못 미칠 때만 뒤에서 채운다
  4. 채택이 top_n 에 도달하면 나머지 후보는 RSS 를 받지 않고 멈춘다 (호출 절약)
  5. 제외된 블로그와 사유(focus_ratio)를 rejected 로 함께 돌려준다 — 화면/로그에 그대로 노출 가능

이 모듈은 다른 모듈에 의존하지 않는다(keyword_aliases 의 단어 경계 매칭만 사용).
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional

try:
    from .keyword_aliases import title_hits_terms
except ImportError:
    from services.keyword_aliases import title_hits_terms


def focus_ratio(posts: list, terms: Iterable[str], n: int = 20) -> float:
    """최근 n개 글 제목 중 주제어가 포함된 비율. posts 는 최신순 [{'title': ...}]."""
    latest = posts[:n]
    if not latest:
        return 0.0
    terms = list(terms)
    hit = sum(1 for p in latest if title_hits_terms(p.get("title", ""), terms))
    return hit / len(latest)


def select_competitors(candidates: list, fetch_posts: Callable[[str], list], terms: Iterable[str], *,
                       top_n: int = 10, min_focus: float = 0.3, pin: Iterable[str] = (),
                       max_fetch: Optional[int] = None) -> dict:
    """
    candidates : [{'blog_id', 'exposure'}] — 노출 점수 내림차순 (내 블로그/exclude 는 이미 제거된 상태)
    fetch_posts: blog_id -> RSS 글 목록(최신순, 실패 시 빈 리스트)
    반환       : {'selected': [...], 'rejected': [...]}
                 selected 항목 = 입력 항목 + 'relevance'('pinned'|'ok'|'unknown') + 'focus_ratio'
                 rejected 항목 = 입력 항목 + 'focus_ratio'
    """
    terms = list(terms)
    pins = {p.lower() for p in pin}
    pinned: list = []
    ok: list = []
    unknown: list = []
    rejected: list = []
    fetched = 0

    for c in candidates:
        blog_id = c["blog_id"]
        if blog_id in pins:
            pinned.append({**c, "relevance": "pinned", "focus_ratio": None})

    for c in candidates:
        blog_id = c["blog_id"]
        if blog_id in pins:
            continue
        if len(pinned) + len(ok) >= top_n:
            break
        if max_fetch is not None and fetched >= max_fetch:
            break
        fetched += 1
        posts = fetch_posts(blog_id) or []
        if not posts:
            unknown.append({**c, "relevance": "unknown", "focus_ratio": None})
            continue
        ratio = focus_ratio(posts, terms)
        if ratio >= min_focus:
            ok.append({**c, "relevance": "ok", "focus_ratio": round(ratio, 3)})
        else:
            rejected.append({**c, "focus_ratio": round(ratio, 3)})

    room = max(0, top_n - len(pinned))
    selected = pinned + ok[:room]
    if len(selected) < top_n:
        selected += unknown[: top_n - len(selected)]
    selected.sort(key=lambda x: (-x["exposure"], x["blog_id"]))
    return {"selected": selected, "rejected": rejected}
