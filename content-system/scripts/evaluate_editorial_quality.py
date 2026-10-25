#!/usr/bin/env python3
"""
evaluate_editorial_quality.py (v1.0 Editorial QA Engine)
초안(Draft)이 독자의 실제 검색 의도와 심리적 질문을 효과적으로 해결하고 있는지,
백과사전식 기술 덤프나 과장된 마케팅 미사여구 없이 자연스러운 서사로 작성되었는지
정량적/정성적 지표를 기반으로 평가하고 피드백을 생성합니다.
"""

import os
import sys
import re
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STRATEGY_DIR = os.path.join(BASE_DIR, "02_writer_ai", "strategy")
DRAFTS_DIR = os.path.join(BASE_DIR, "02_writer_ai", "drafts")
WORKING_DIR = os.path.join(BASE_DIR, "02_writer_ai", "working")

BUZZWORDS = ["완벽한", "완벽히", "완벽 분석", "최적의", "업계 표준", "혁신적인", "생생한", "고성능의", "엔터프라이즈급"]
ROBOTIC_LABELS = [r"\bFACT\s*:", r"\bWHAT IT MEANS\s*:", r"\bWHEN IT MATTERS\s*:", r"\bWHAT USER SHOULD DO\s*:"]

def evaluate_editorial_quality(content_id, draft_path=None):
    if "/" in content_id or "\\" in content_id or "." in content_id:
        base_name = os.path.basename(content_id)
        match = re.search(r'(CNT-\d{4}W\d{2}-\d{3})', base_name)
        if match:
            if not draft_path and (content_id.endswith(".md") or os.path.exists(content_id)):
                draft_path = content_id
            content_id = match.group(1)

    strategy_file = os.path.join(STRATEGY_DIR, f"{content_id}.strategy.yaml")
    if not os.path.exists(strategy_file):
        strategy_file = os.path.join(WORKING_DIR, content_id, "strategy.yaml")

    strategy = {}
    if os.path.exists(strategy_file):
        with open(strategy_file, "r", encoding="utf-8") as sf:
            strategy = yaml.safe_load(sf) or {}

    if not draft_path:
        draft_path = os.path.join(DRAFTS_DIR, f"{content_id}.draft.md")

    if not os.path.exists(draft_path):
        return False, [f"Draft not found: {draft_path}"], {}

    with open(draft_path, "r", encoding="utf-8") as df:
        draft_text = df.read()

    lines = draft_text.split("\n")
    issues = []
    strengths = []
    score = 100

    # 1. Robotic Labeling Check
    robotic_matches = []
    for pat in ROBOTIC_LABELS:
        found = re.findall(pat, draft_text, re.IGNORECASE)
        if found:
            robotic_matches.extend(found)
    if robotic_matches:
        score -= 15
        issues.append({
            "type": "ROBOTIC_FORMATTING",
            "severity": "HIGH",
            "reason": f"본문에 기계적 채점용 레이블({', '.join(set(robotic_matches))})이 {len(robotic_matches)}회 노출되었습니다. 자연스러운 문맥 서술로 전환하십시오."
        })
    else:
        strengths.append("기계적 레이블 박스 없이 자연스러운 서사 전개 준수")

    # 2. Marketing Buzzwords Density Check
    found_buzzwords = []
    for bw in BUZZWORDS:
        cnt = draft_text.count(bw)
        if cnt > 0:
            found_buzzwords.append(f"'{bw}' ({cnt}회)")
    if len(found_buzzwords) >= 4:
        score -= 10
        issues.append({
            "type": "BUZZWORD_OVERUSE",
            "severity": "MEDIUM",
            "reason": f"과장된 마케팅 미사여구({', '.join(found_buzzwords)})가 과다 사용되었습니다. 구체적 팩트와 수치로 대체하십시오."
        })
    elif len(found_buzzwords) > 0:
        issues.append({
            "type": "BUZZWORD_WARNING",
            "severity": "LOW",
            "reason": f"상투적 수식어 일부 발견: {', '.join(found_buzzwords)}"
        })
    else:
        strengths.append("과장된 마케팅 미사여구 배제 및 담백한 신뢰감 유지")

    # 3. Jargon Barrier in Introduction Check (First 35 lines)
    intro_text = "\n".join(lines[:35])
    early_jargons = []
    for j in ["TDoA", "Sensor Fusion", "DFOV", "MEMS", "binaural"]:
        if j.lower() in intro_text.lower():
            early_jargons.append(j)
    # Check if layman terms precede them
    has_layman = any(t in intro_text for t in ["말하는 사람", "알아서 비춰주는", "발표자 자동", "표정", "답답"])
    if len(early_jargons) >= 2 and not has_layman:
        score -= 15
        issues.append({
            "type": "JARGON_BARRIER",
            "severity": "HIGH",
            "reason": f"서론 첫머리에 일상적 현상 공감 없이 기술 전문 약어({', '.join(early_jargons)})가 조기 투하되었습니다."
        })
    elif len(early_jargons) >= 2:
        strengths.append("전문 용어 이전에 일상어 및 문제 공감 인트로 배치 확인")

    # 4. Knowledge Dump Check (Checking can_omit violations)
    can_omit = strategy.get("can_omit", [])
    dumped_specs = []
    if "전원 어댑터" in str(can_omit) or "소비전력" in str(can_omit):
        for term in ["19V", "4.74A", "소비전력", "kensington"]:
            if term.lower() in draft_text.lower():
                dumped_specs.append(term)
    if dumped_specs:
        score -= 10
        issues.append({
            "type": "KNOWLEDGE_DUMP",
            "severity": "MEDIUM",
            "reason": f"독자 의사결정과 무관하여 생략 지시된 스펙({', '.join(dumped_specs)})이 본문에 불필요하게 기재되었습니다."
        })
    else:
        strengths.append("불필요한 데이터시트 스펙 덤핑 억제 완료")

    # 5. Reader Questions Coverage Check
    reader_questions = strategy.get("reader", {}).get("questions", [])
    covered_q_count = 0
    missing_q = []
    for q in reader_questions:
        q_keywords = [w for w in re.split(r'[\s\?\(\),]+', q) if len(w) >= 2 and w not in ["진짜", "있나요", "어떻게", "무엇이", "있나요?", "되나요"]]
        hit_count = sum(1 for kw in q_keywords if kw in draft_text)
        if hit_count >= 1:
            covered_q_count += 1
        else:
            missing_q.append(q)

    q_coverage_rate = (covered_q_count / len(reader_questions) * 100) if reader_questions else 100
    if q_coverage_rate < 70.0:
        score -= 20
        issues.append({
            "type": "READER_QUESTIONS_UNANSWERED",
            "severity": "HIGH",
            "reason": f"기획된 핵심 독자 질문 {len(reader_questions)}개 중 {len(missing_q)}개가 본문에서 충분히 다뤄지지 않았습니다."
        })
    else:
        strengths.append(f"핵심 독자 질문 {len(reader_questions)}개 중 {covered_q_count}개 답변 충족 ({round(q_coverage_rate, 1)}%)")

    # 6. Visual Asset Placement Check
    asset_matches = re.findall(r'\{\{asset:(AST-[A-Za-z0-9_-]+)\}\}', draft_text)
    if not asset_matches:
        score -= 10
        issues.append({
            "type": "MISSING_ASSETS",
            "severity": "MEDIUM",
            "reason": "본문에 삽입된 공식 시각 자산({{asset:AST-ID}})이 없습니다."
        })
    else:
        strengths.append(f"공식 시각 자산 {len(set(asset_matches))}개 적재적소 바인딩 확인")

    # 7. Official Device Blog Link Check (1 Post 1 Link Rule & Deduplication)
    official_links = re.findall(r'\[오우션 공식 블로그 \(([^)]+)\)\]\((https?://blog\.naver\.com/[^)]+)\)', draft_text)
    if official_links:
        if len(official_links) > 1:
            score -= 10
            issues.append({
                "type": "DUPLICATE_BLOG_LINKS",
                "severity": "HIGH",
                "reason": f"본문에 공식 블로그 링크가 {len(official_links)}건 배치되었습니다. 포스팅당 대표 메인 장비 링크 1개만 배치해야 합니다 (중복 노출 엄격 금지)."
            })
        else:
            strengths.append(f"오우션 공식 블로그 단일 대표 링크 정상 배치 확인 ({official_links[0][0]})")

    # 8. Distributor Identity & Zero Client Deployments Check
    client_case_matches = re.findall(r'(고객사(?:에|의)?\s*(?:구축|납품|도입|시공|설치)|실제\s*(?:기업\s*)?고객사|실제\s*구축\s*사례|실제\s*납품|실제\s*연동\s*사례|실제\s*\d+인\s*규모\s*회의실에서\s*(?:저희가|직접)\s*(?:설치|구축|검증)|저희가\s*실제\s*기업)', draft_text)
    if client_case_matches:
        score -= 25
        issues.append({
            "type": "FABRICATED_CLIENT_DEPLOYMENT",
            "severity": "CRITICAL",
            "reason": f"오우션테크놀러지는 공식 수입 총판으로 고객사 직접 시공 데이터/사진이 없습니다. 실제 고객사 구축/납품을 사칭한 표현({', '.join(set(client_case_matches))})이 발견되었습니다. '본사 쇼룸/기술 랩 실증' 또는 '제조사 공식 설계 가이드'로 수정하십시오."
        })
    else:
        strengths.append("총판 정체성 준수: 허위 고객사 구축 사례 없이 쇼룸 및 공식 설계 기준 서술")

    # 9. Mic Pod False Speaker Tracking Check
    mic_tracking_matches = []
    for line in lines:
        if re.search(r'(마이크\s*팟|mic\s*pod)', line, re.IGNORECASE):
            if not re.search(r'(지\s*않|않[다으며는음]?|아니|불가|제외|독립|별도|없[다으며는음]?|전혀\s*없|구분|미지원)', line):
                if re.search(r'(?:방위각.*(?:계산|측정)|화자\s*추적.*(?:시너지|연동|수행|클로즈업)|얼굴을\s*놓치지)', line):
                    mic_tracking_matches.append(line.strip()[:60])
    if mic_tracking_matches:
        score -= 25
        issues.append({
            "type": "FALSE_MIC_POD_TRACKING",
            "severity": "CRITICAL",
            "reason": f"마이크 팟은 순수 오디오 수음 장비이며 카메라 화자 추적/방위각 계산 기능이 없습니다. 위반 문장: {'; '.join(mic_tracking_matches)}"
        })
    else:
        strengths.append("하드웨어 기능 무결성: 마이크 팟의 음향 수음 역할 명확히 유지 (화자 추적 왜곡 없음)")


    final_score = max(0, score)
    is_pass = final_score >= 80 and not any(i["severity"] == "CRITICAL" for i in issues)

    report = {
        "content_id": content_id,
        "editorial_score": final_score,
        "status": "PASS" if is_pass else "REVISION_REQUIRED",
        "strengths": strengths,
        "issues": issues,
        "reader_questions_coverage_pct": round(q_coverage_rate, 1),
        "total_reader_questions": len(reader_questions),
        "covered_reader_questions": covered_q_count
    }

    return is_pass, issues, report

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Evaluate Editorial Quality of Draft against Writing Strategy")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    parser.add_argument("--draft", help="Optional path to draft file")
    args = parser.parse_args()

    passed, issues, report = evaluate_editorial_quality(args.content_id, args.draft)
    status_tag = "[EDITORIAL PASS]" if passed else "[EDITORIAL REVISION_REQUIRED]"

    print(f"=== Editorial Quality Assessment for {args.content_id} ===")
    print(f"  Status: {report['status']} (Score: {report['editorial_score']}/100)")
    print(f"  Reader Questions Answered: {report['covered_reader_questions']}/{report['total_reader_questions']} ({report['reader_questions_coverage_pct']}%)\n")

    print("[Editorial Strengths]:")
    for s in report["strengths"]:
        print(f"  ✓ {s}")

    if report["issues"]:
        print("\n[Actionable Editorial Feedback]:")
        for iss in report["issues"]:
            print(f"  ⚠️ [{iss['severity']}] {iss['type']}: {iss['reason']}")

    print(f"\n{status_tag}")
    if not passed:
        sys.exit(1)
    sys.exit(0)
