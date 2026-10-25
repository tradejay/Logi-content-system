#!/usr/bin/env python3
"""
content-system/scripts/build_writing_strategy.py
================================================
동적 Writing Strategy 생성기

원칙:
- 작성 규칙, 플로우, 가이드라인은 파이썬 코드가 아니라 Markdown 문서(WRITING_CORE.md, WRITING_GUIDE.md)가 단일 진실 공급원(SSOT)입니다.
- 본 스크립트는 Brief 메타데이터(주제, 타깃 독자, 키워드)를 읽어 경량의 전략 메타데이터 YAML을 생성하며, 일체의 하드코딩된 원고 본문/질문 텍스트를 포함하지 않습니다.
"""

import os
import sys
import yaml
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
STRATEGY_DIR = os.path.join(BASE_DIR, "02_writer_ai", "strategy")
CORE_DIR = os.path.join(BASE_DIR, "02_writer_ai", "core")

CORE_GUIDE_FILE = os.path.join(CORE_DIR, "WRITING_CORE.md")
WRITING_GUIDE_FILE = os.path.join(BASE_DIR, "02_writer_ai", "WRITING_GUIDE.md")


def build_writing_strategy(content_id: str):
    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if not os.path.exists(brief_file):
        raise FileNotFoundError(f"Brief file not found: {brief_file}")

    with open(brief_file, "r", encoding="utf-8") as f:
        brief = yaml.safe_load(f) or {}

    canonical_topic = brief.get("canonical_topic", "")
    target_keyword = brief.get("target_keyword", "") or brief.get("search", {}).get("primary_keyword", "")
    target_audience = brief.get("target_audience", "IT 관리자 및 기업 총무 담당자")
    tp = brief.get("target_device") or brief.get("target_products", [])
    target_device = tp[0] if isinstance(tp, list) and tp else str(tp)

    topic_lower = canonical_topic.lower()

    # Playbook 매핑 (가벼운 타입 분류)
    if "speaker_tracking" in topic_lower or "화자추적" in topic_lower or "rightsight" in topic_lower:
        primary_playbook = "PB-MECHANISM-EXPLAINER"
        secondary_playbooks = ["PB-PRODUCT-SELECTION", "PB-CONFIG-HOWTO"]
    elif "huddle" in topic_lower or "meetup" in topic_lower or "소형" in topic_lower:
        primary_playbook = "PB-PRODUCT-SELECTION"
        secondary_playbooks = ["PB-CONFIG-HOWTO", "PB-PROBLEM-DIAGNOSIS"]
    elif "microphone" in topic_lower or "acoustics" in topic_lower or "마이크" in topic_lower:
        primary_playbook = "PB-PROBLEM-DIAGNOSIS"
        secondary_playbooks = ["PB-TROUBLESHOOTING", "PB-PRODUCT-SELECTION"]
    elif "touch" in topic_lower or "tap" in topic_lower or "터치" in topic_lower:
        primary_playbook = "PB-PLATFORM-INTEGRATION"
        secondary_playbooks = ["PB-CONFIG-HOWTO", "PB-PRODUCT-SELECTION"]
    else:
        primary_playbook = "PB-PRODUCT-SELECTION"
        secondary_playbooks = ["PB-CONFIG-HOWTO"]

    # 독자 핵심 질문은 Brief의 검색 의도 및 타이틀로부터 동적 도출
    brief_title = brief.get("title", "")
    reader_questions = [
        f"{target_keyword} 도입 시 가장 먼저 고려해야 할 기술적 기준은 무엇인가?",
        f"{target_device or '해당 장비'}는 실제 회의실 환경에서 어떤 방식으로 작동하는가?",
        "공간 규모와 회의실 구조(거리, 벽면 재질 등)에 따른 최적 세팅 및 주의사항은 무엇인가?",
        "관리자 입장에서 초기 설정 및 케이블 배선은 어떻게 구성해야 하는가?"
    ]

    strategy_data = {
        "content_id": content_id,
        "strategy_version": 2,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "canonical_topic": canonical_topic,
        "target_keyword": target_keyword,
        "target_device": target_device,
        "target_audience": target_audience,
        "primary_playbook": primary_playbook,
        "secondary_playbooks": secondary_playbooks,
        "guideline_sources": [
            "content-system/02_writer_ai/core/WRITING_CORE.md",
            "content-system/02_writer_ai/WRITING_GUIDE.md"
        ],
        "reader": {
            "state": f"{target_keyword}에 관한 실무 가이드와 기술적 판단 기준을 찾고 있음",
            "questions": reader_questions
        },
        "article_goal": brief.get("one_line_purpose", f"{target_keyword} 실무 선택 및 세팅 완벽 가이드"),
        "can_omit": ["전원 어댑터 전압/전류 및 소비전력 상세", "패키징 나사 규격", "비관련 부속품"],
        "avoid": [
            "FACT: ... WHAT IT MEANS: 기계적 레이블 박스",
            "과장된 마케팅 미사여구(완벽한, 혁신적인 등)",
            "실제 고객사 구축 사례 날조(총판 쇼룸 실증 기준 필수)",
            "원고 본문에 【FACT-xxx】 내부 태그 노출"
        ]
    }

    os.makedirs(STRATEGY_DIR, exist_ok=True)
    out_file = os.path.join(STRATEGY_DIR, f"{content_id}.strategy.yaml")
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(strategy_data, f, allow_unicode=True, sort_keys=False)

    return out_file, strategy_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate dynamic writing strategy")
    parser.add_argument("content_id", help="Content ID")
    args = parser.parse_args()
    out, strat = build_writing_strategy(args.content_id)
    print(f"Strategy generated: {out}")
