#!/usr/bin/env python3
"""
check_duplicate.py (5-C Duplicate Safety)
신규 기획 대상 키워드 및 토픽에 대해 5단계 다차원 중복 심사를 수행하고,
판정 점수표와 권고 조치(NEW, UPDATE_CANDIDATE, DUPLICATE_CANDIDATE, REVIEW_REQUIRED)를 상세 출력합니다.
"""
import os
import sys
import re
import csv
import json
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_FILE = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")

def normalize_text(text):
    if not text:
        return ""
    return re.sub(r"[\s\-_.,/()\[\]]", "", str(text)).lower()

def jaccard_similarity(s1, s2):
    t1 = set(s1.split())
    t2 = set(s2.split())
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)

def check_duplicate(primary_keyword, canonical_topic, intent="", funnel="", purpose=""):
    norm_kw = normalize_text(primary_keyword)
    norm_topic = normalize_text(canonical_topic)

    output = {
        "result": "NEW",
        "matched_content": None,
        "scores": {
            "exact_keyword": False,
            "normalized_keyword": False,
            "canonical_topic": False,
            "intent_match": False,
            "funnel_match": False,
            "purpose_similarity": 0.0
        },
        "reason": "기존 레지스트리에 등록된 어떤 콘텐츠와도 핵심 속성이 겹치지 않는 완전 신규 토픽입니다.",
        "recommended_action": "신규 Content Brief 생성 승인 (NEW)"
    }

    if not os.path.exists(REGISTRY_FILE):
        return output

    rows = []
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return output

    candidates = []

    for r in rows:
        reg_cid = r.get("content_id")
        reg_kw = r.get("primary_keyword", "")
        reg_topic = r.get("canonical_topic", "")
        reg_intent = r.get("search_intent", "")
        reg_funnel = r.get("funnel_stage", "")
        reg_purpose = r.get("one_line_purpose", "")

        exact_kw = (reg_kw == primary_keyword)
        norm_kw_match = (normalize_text(reg_kw) == norm_kw)
        topic_match = (normalize_text(reg_topic) == norm_topic)
        intent_match = bool(intent and reg_intent and (intent in reg_intent or reg_intent in intent))
        funnel_match = bool(funnel and reg_funnel and (funnel == reg_funnel))
        purpose_sim = jaccard_similarity(purpose, reg_purpose) if purpose and reg_purpose else 0.0

        score_dict = {
            "exact_keyword": exact_kw,
            "normalized_keyword": norm_kw_match,
            "canonical_topic": topic_match,
            "intent_match": intent_match,
            "funnel_match": funnel_match,
            "purpose_similarity": round(purpose_sim, 2)
        }

        # 1. Level 1: Exact keyword + same topic
        if exact_kw and topic_match:
            if intent_match:
                return {
                    "result": "DUPLICATE_CANDIDATE",
                    "matched_content": {
                        "content_id": reg_cid,
                        "primary_keyword": reg_kw,
                        "canonical_topic": reg_topic,
                        "title": r.get("title")
                    },
                    "scores": score_dict,
                    "reason": f"기존 콘텐츠({reg_cid})와 대표 키워드 및 검색 의도가 완전히 동일합니다.",
                    "recommended_action": f"기존 글 {reg_cid} 업데이트 또는 다른 의도로 재기획 필요"
                }
            else:
                return {
                    "result": "UPDATE_CANDIDATE",
                    "matched_content": {
                        "content_id": reg_cid,
                        "primary_keyword": reg_kw,
                        "canonical_topic": reg_topic,
                        "title": r.get("title")
                    },
                    "scores": score_dict,
                    "reason": f"대표 키워드는 동일하나 검색 의도가 다릅니다. 기존 글의 파생 하위 글로 발행 가능.",
                    "recommended_action": f"신규 작성 허용 (단, {reg_cid}와 상호 내부 링크 연결 필수)"
                }

        # 2. Level 2: Normalized keyword match
        if norm_kw_match and topic_match:
            return {
                "result": "DUPLICATE_CANDIDATE",
                "matched_content": {
                    "content_id": reg_cid,
                    "primary_keyword": reg_kw,
                    "canonical_topic": reg_topic,
                    "title": r.get("title")
                },
                "scores": score_dict,
                "reason": f"기존 키워드 '{reg_kw}'와 공백/기호만 다른 실질적 동일 키워드입니다.",
                "recommended_action": f"기존 글 {reg_cid} 업데이트 권고"
            }

        # 3. Level 3 & 4: Same topic with high purpose similarity
        if topic_match and purpose_sim >= 0.70:
            return {
                "result": "REVIEW_REQUIRED",
                "matched_content": {
                    "content_id": reg_cid,
                    "canonical_topic": reg_topic,
                    "title": r.get("title")
                },
                "scores": score_dict,
                "reason": f"토픽이 같고 한 줄 목적 유사도가 {int(purpose_sim*100)}%로 매우 높아 중복 잠식 우려가 있습니다.",
                "recommended_action": "사람 관리자 검토 필요 (REVIEW_REQUIRED)"
            }

    return output

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="5-Stage Duplicate Gate Checker with Rationale")
    parser.add_argument("--keyword", required=True, help="Primary Keyword")
    parser.add_argument("--canonical-topic", required=True, help="Canonical Topic (e.g. speaker_tracking_camera)")
    parser.add_argument("--intent", default="", help="Search intent (e.g. problem_solving)")
    parser.add_argument("--funnel", default="", help="Funnel stage (e.g. discovery)")
    parser.add_argument("--purpose", default="", help="One line purpose")
    parser.add_argument("--yaml", action="store_true", help="Output as YAML")
    args = parser.parse_args()

    res = check_duplicate(args.keyword, args.canonical_topic, args.intent, args.funnel, args.purpose)
    if args.yaml:
        print(yaml.safe_dump(res, allow_unicode=True, sort_keys=False))
    else:
        print(json.dumps(res, ensure_ascii=False, indent=2))
