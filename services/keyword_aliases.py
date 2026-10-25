"""
keyword_aliases.py
==================
제목에 키워드(또는 표기 변형)가 들어 있는지 판정하는 모듈.

기존 방식(공백 제거 후 부분 문자열 검색)의 문제
  * 'tap' 이 'laptop', 'startup' 에 걸림
  * 단독 'meetup' 이 밋업 2 와 무관한 행사 글에 걸림
개선
  * 영문/숫자로 시작하거나 끝나는 표기는 앞뒤가 영문/숫자가 아닐 때만 일치 (단어 경계)
  * 공백 유무는 무시 ('rally bar' = 'rallybar' = 'rally  bar')
  * 일치가 키워드 그대로(exact)인지 별칭(alias)인지 구분해서 반환

이 모듈은 다른 모듈에 의존하지 않는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Optional

# 키워드 → 제목에 나타날 수 있는 표기들. 키워드 자신은 자동으로 포함된다.
# 영문 단독 약어('tap', 'meetup')는 넣지 말고 반드시 브랜드와 함께 쓸 것.
KEYWORD_ALIASES: dict = {
    # 핀포인트
    "로지텍 랠리바": ["로지텍랠리바", "logitech rally bar", "logitech rallybar", "rally bar", "rallybar", "랠리바"],
    "로지텍 랠리바 미니": ["로지텍랠리바미니", "logitech rally bar mini", "rally bar mini", "rallybar mini", "랠리바 미니"],
    "로지텍 밋업 2": ["로지텍 밋업2", "로지텍밋업2", "logitech meetup 2", "logitech meetup2", "meetup 2", "meetup2", "밋업 2", "밋업2"],
    "로지텍 랠리 마이크 팟": ["로지텍랠리마이크팟", "logitech rally mic pod", "rally mic pod", "rally micpod", "랠리 마이크 팟", "마이크 팟", "마이크팟"],
    "로지텍 탭": ["로지텍탭", "logitech tap"],
    # 메인 / 제너럴
    "화상회의 구축": ["화상회의구축", "화상회의 시스템 구축", "화상회의시스템구축"],
    "화상회의 장비": ["화상회의장비", "화상회의 장비 추천", "화상장비", "화상회의 기기"],
    "화상회의": ["화상 회의", "video conference", "videoconference", "video conferencing"],
    "화상회의 솔루션": ["화상회의솔루션", "화상 솔루션"],
    "회의실 화상카메라": ["회의실화상카메라", "회의실 카메라", "화상카메라", "화상 카메라"],
    # 보조 키워드는 자기 이름만 사용 (메인 키워드와 이중 집계 방지)
    "화상회의 장비 추천": ["화상회의 장비추천", "화상장비 추천"],
    "화상회의 시스템 구축": ["화상회의 시스템구축"],
}

_ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")


@dataclass(frozen=True)
class KeywordMatch:
    pos: int  # 제목(원문) 안에서 일치가 시작되는 위치
    alias: str  # 일치한 표기
    exact: bool  # 키워드 그대로(공백/대소문자 무시) 일치했는가


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


@lru_cache(maxsize=1024)
def _pattern(term: str) -> Optional["re.Pattern"]:
    term = (term or "").strip()
    if not term:
        return None
    body = r"\s*".join(re.escape(part) for part in term.split())
    pre = r"(?<![a-z0-9])" if _ASCII_ALNUM.match(term[0]) else ""
    post = r"(?![a-z0-9])" if _ASCII_ALNUM.match(term[-1]) else ""
    return re.compile(pre + body + post, re.IGNORECASE)


def find_term(title: str, term: str) -> int:
    """title 안에서 term 이 처음 나타나는 위치. 없으면 -1."""
    pat = _pattern(term)
    if pat is None:
        return -1
    m = pat.search(title or "")
    return m.start() if m else -1


def contains_term(title: str, term: str) -> bool:
    return find_term(title, term) >= 0


def title_hits_terms(title: str, terms: Iterable[str]) -> bool:
    return any(contains_term(title, t) for t in terms)


def aliases_for(keyword: str) -> list:
    """키워드 자신 + 등록된 별칭 (중복 제거, 순서 유지)."""
    seen, out = set(), []
    for term in [keyword, *KEYWORD_ALIASES.get(keyword, [])]:
        key = _norm(term)
        if key and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def find_keyword_pos(title: str, keyword: str) -> Optional[KeywordMatch]:
    """가장 앞에서 일치하는 표기를 반환. 위치가 같으면 키워드 그대로 일치를 우선. 없으면 None."""
    best: Optional[KeywordMatch] = None
    for term in aliases_for(keyword):
        pos = find_term(title, term)
        if pos < 0:
            continue
        cand = KeywordMatch(pos=pos, alias=term, exact=_norm(term) == _norm(keyword))
        if best is None or cand.pos < best.pos or (cand.pos == best.pos and cand.exact and not best.exact):
            best = cand
    return best
