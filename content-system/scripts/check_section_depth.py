#!/usr/bin/env python3
"""
check_section_depth.py (v1.2 Flexible Section Depth & Quality Gate)
Brief의 Section Plan 및 Playbook의 추천 흐름을 기준으로, Draft의 각 섹션이
모듈별 심층 완성 조건(Depth Definitions)을 실제로 충족했는지
정규식 및 의미적 매칭을 통해 유연하고 정확하게 정량 평가합니다.
SEC-xx 명시적 태그뿐 아니라 순차적 번호 헤딩(## 1., ## 2.)도 자동 매핑합니다.
"""

import os
import sys
import re
import yaml
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEFS_DIR = os.path.join(BASE_DIR, "01_keyword_ai", "briefs")
DRAFTS_DIR = os.path.join(BASE_DIR, "02_writer_ai", "drafts")

# Module Depth Criteria Definitions (Enriched Semantic Depth Checklist)
MODULE_DEPTH_CHECKS = {
    "how_to": [
        {"name": "purpose_rationale", "pattern": re.compile(r'이유|목적|필요|배경|위해|최적화|기본값|변경', re.IGNORECASE), "desc": "설정 필요성 및 목적 명시"},
        {"name": "menu_path", "pattern": re.compile(r'>|➔|->|접근 경로|메뉴|포털|Admin|Sync|설정|Settings', re.IGNORECASE), "desc": "정확한 설정 메뉴 접근 경로"},
        {"name": "options_explained", "pattern": re.compile(r'옵션|설정값|프레이밍|모드|선택|파라미터|값|Speaker View|Group View', re.IGNORECASE), "desc": "옵션별 효과 및 설정값 안내"},
        {"name": "verification_and_troubleshooting", "pattern": re.compile(r'확인|검증|테스트|점검|체크|문제|오류|트러블|발언', re.IGNORECASE), "desc": "설정 후 검증 단계 및 문제 해결 가이드"},
        {"name": "asset_or_visual", "pattern": re.compile(r'\{\{asset:|ASSET_REQUIRED|!\[|<img', re.IGNORECASE), "desc": "설정 화면 시각자료 또는 플레이스홀더"}
    ],
    "mechanism": [
        {"name": "detection_inputs", "pattern": re.compile(r'감지|입력|음향|오디오|비전|TDoA|음원|도착 시간차|방향', re.IGNORECASE), "desc": "무엇을 감지하는지 입력 정보 명시"},
        {"name": "hardware_component", "pattern": re.compile(r'센서|마이크|뷰파인더|렌즈|컴포넌트|어레이|DSP', re.IGNORECASE), "desc": "담당 하드웨어 부품 명시"},
        {"name": "pipeline_flow", "pattern": re.compile(r'단계|파이프라인|➔|흐름|스위칭|판단|처리|전환', re.IGNORECASE), "desc": "입력-판단-출력 연산 흐름 제시"},
        {"name": "sensor_fusion", "pattern": re.compile(r'융합|센서 퓨전|교차|복합|매핑|검증|Sensor Fusion', re.IGNORECASE), "desc": "음향+비전 센서 퓨전 설명"}
    ],
    "comparison": [
        {"name": "markdown_table", "pattern": re.compile(r'\|.*\|.*\|', re.IGNORECASE), "desc": "비교 대상 대조표(Table) 구성"},
        {"name": "criteria_defined", "pattern": re.compile(r'기준|방식|거리|화각|모드|제어', re.IGNORECASE), "desc": "동일 비교 기준 적용"},
        {"name": "scenarios", "pattern": re.compile(r'시나리오|적합|추천|상황|용도|규모', re.IGNORECASE), "desc": "모드별 최적 활용 시나리오 제시"}
    ],
    "operating_conditions": [
        {"name": "distance_and_metrics", "pattern": re.compile(r'\d+(?:\.\d+)?\s*(?:m|cm|mm|lux|dB|°|도)', re.IGNORECASE), "desc": "물리적 정량 조건 및 권장 수치(m, dB, lux)"},
        {"name": "environmental_impact", "pattern": re.compile(r'유리|잔향|반사|흡음|배치|각도|벗어나|초과|저하', re.IGNORECASE), "desc": "실내 구조적 요인 및 범위 이탈 시 영향"},
        {"name": "installer_adjustments", "pattern": re.compile(r'조정|설정|마운트|배치|위치|추가|설치|보완|대처|패널', re.IGNORECASE), "desc": "설치자가 현장에서 조정 가능한 옵션"}
    ],
    "limitations": [
        {"name": "physical_boundary", "pattern": re.compile(r'한계|제약|초과|주의|오류|불가|단점|반사', re.IGNORECASE), "desc": "물리적 동작 한계 및 제약 조건"},
        {"name": "operational_impact", "pattern": re.compile(r'영향|오작동|미인식|놓치|지연|누락|불편|헷갈', re.IGNORECASE), "desc": "실제 회의 현장에 미치는 구체적 영향"},
        {"name": "remedy_or_workaround", "pattern": re.compile(r'보완|추가|권장|대안|배치|패널|마이크 팟|우회', re.IGNORECASE), "desc": "한계 극복을 위한 엔지니어링 대안 및 회피책"}
    ],
    "hook": [
        {"name": "user_problem", "pattern": re.compile(r'문제|고충|불편|표정|안 보|답답|어려움|갈증', re.IGNORECASE), "desc": "독자의 실제 회의실 일상 문제 환기"},
        {"name": "quick_answer", "pattern": re.compile(r'요약|결론|핵심|Quick Answer|영상|확인|스위칭|클로즈업', re.IGNORECASE), "desc": "핵심 3줄 요약 또는 시연 결과 제공"}
    ],
    "product_bridge": [
        {"name": "hardware_specs", "pattern": re.compile(r'렌즈|줌|마이크|스피커|화각|4K', re.IGNORECASE), "desc": "핵심 하드웨어 광학/음향 스펙"},
        {"name": "interfaces_ports", "pattern": re.compile(r'HDMI|USB|포트|단자|전원|이더넷|연결|마이크\s*팟|확장', re.IGNORECASE), "desc": "인터페이스 및 마이크 확장 구성"}
    ],
    "cta": [
        {"name": "soft_offer", "pattern": re.compile(r'진단|상담|문의|리포트|시연|안내|지원|컨설팅', re.IGNORECASE), "desc": "부담 없는 전문 기술 지원 제안"}
    ]
}

def split_draft_by_sections(draft_text):
    """
    Splits draft text into sections based on markdown headings:
    Supports SEC-xx tags, numbered headings (## 1., ## 2.), or generic ## (H2 only).
    Does NOT split on H3 (###).
    """
    sections = {}
    current_sec_id = "INTRO"
    current_lines = []
    num_idx = 1

    for line in draft_text.split("\n"):
        sec_match = re.search(r'SEC-(\d+)', line, re.IGNORECASE)
        num_match = re.search(r'^##\s+(\d+)[\.\s]', line)

        # Check for strict H2 (## but not ###)
        is_h2 = line.startswith("## ") or (line.startswith("##") and not line.startswith("###"))
        if is_h2:
            if current_lines:
                sections[current_sec_id] = "\n".join(current_lines)
            if sec_match:
                current_sec_id = f"SEC-{int(sec_match.group(1)):02d}"
            elif num_match:
                current_sec_id = f"SEC-{int(num_match.group(1)):02d}"
            else:
                current_sec_id = f"SEC-{num_idx:02d}"
            num_idx += 1
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_sec_id] = "\n".join(current_lines)

    return sections

def evaluate_section_depth(content_id, draft_path=None):
    if "/" in content_id or "\\" in content_id or "." in content_id:
        base_name = os.path.basename(content_id)
        match = re.search(r'(CNT-\d{4}W\d{2}-\d{3})', base_name)
        if match:
            if not draft_path and (content_id.endswith(".md") or os.path.exists(content_id)):
                draft_path = content_id
            content_id = match.group(1)

    brief_file = os.path.join(BRIEFS_DIR, f"{content_id}.brief.yaml")
    if not os.path.exists(brief_file):
        return False, [f"Brief not found: {brief_file}"], {}

    with open(brief_file, "r", encoding="utf-8") as bf:
        brief = yaml.safe_load(bf) or {}

    planned_sections = brief.get("sections", [])
    if not planned_sections:
        return True, [], {"overall_depth_pct": 100.0, "section_results": []}

    if not draft_path:
        draft_path = os.path.join(DRAFTS_DIR, f"{content_id}.draft.md")

    if not os.path.exists(draft_path):
        return False, [f"Draft not found: {draft_path}"], {}

    with open(draft_path, "r", encoding="utf-8") as df:
        draft_text = df.read()

    draft_sections = split_draft_by_sections(draft_text)

    section_results = []
    total_checks = 0
    passed_checks = 0
    warnings = []

    for p_sec in planned_sections:
        s_id = p_sec.get("id")
        s_type = str(p_sec.get("type", "")).lower()

        # Find matching text
        sec_text = draft_sections.get(s_id, "")
        if not sec_text:
            for k, v in draft_sections.items():
                if s_type in v.lower() or s_id in v:
                    sec_text = v
                    break

        checks = MODULE_DEPTH_CHECKS.get(s_type, [])
        if not checks:
            if "how" in s_type:
                checks = MODULE_DEPTH_CHECKS["how_to"]
            elif "mech" in s_type:
                checks = MODULE_DEPTH_CHECKS["mechanism"]
            elif "comp" in s_type:
                checks = MODULE_DEPTH_CHECKS["comparison"]
            elif "oper" in s_type:
                checks = MODULE_DEPTH_CHECKS["operating_conditions"]
            elif "limit" in s_type:
                checks = MODULE_DEPTH_CHECKS["limitations"]
            elif "hook" in s_type:
                checks = MODULE_DEPTH_CHECKS["hook"]
            elif "bridge" in s_type or "product" in s_type:
                checks = MODULE_DEPTH_CHECKS["product_bridge"]
            elif "cta" in s_type:
                checks = MODULE_DEPTH_CHECKS["cta"]

        sec_total = len(checks)
        sec_passed = 0
        failed_items = []

        if sec_total > 0:
            for c in checks:
                total_checks += 1
                if sec_text and c["pattern"].search(sec_text):
                    passed_checks += 1
                    sec_passed += 1
                else:
                    failed_items.append(c["desc"])

            sec_score = round((sec_passed / sec_total) * 100, 1)
        else:
            sec_score = 100.0

        if sec_score < 60.0:
            warnings.append(f"[{s_id}] '{s_type.upper()}' Section is shallow ({sec_score}%). Missing: {', '.join(failed_items)}")

        section_results.append({
            "section_id": s_id,
            "type": s_type,
            "score_pct": sec_score,
            "passed": sec_score >= 60.0,
            "missing_criteria": failed_items
        })

    overall_depth = round((passed_checks / total_checks * 100), 1) if total_checks > 0 else 100.0

    report = {
        "content_id": content_id,
        "overall_depth_pct": overall_depth,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "section_results": section_results,
        "warnings": warnings
    }

    is_pass = overall_depth >= 75.0 and len(warnings) == 0
    return is_pass, warnings, report

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Evaluate Section Depth of content against Section Plan")
    parser.add_argument("content_id", help="Content ID (e.g. CNT-2026W39-001)")
    parser.add_argument("--draft", help="Optional specific draft path")
    args = parser.parse_args()

    passed, warns, report = evaluate_section_depth(args.content_id, args.draft)
    print(f"=== Section Depth Evaluation for {args.content_id} ===")
    print(f"  Overall Section Depth: {report['overall_depth_pct']}% ({report['passed_checks']}/{report['total_checks']} Criteria)")
    print("\n[Per-Section Depth Breakdown]:")
    for sr in report["section_results"]:
        status_icon = "✓" if sr["passed"] else "⚠️"
        print(f"  {status_icon} [{sr['section_id']}] {sr['type'].upper():<20} : {sr['score_pct']}%")
        if sr["missing_criteria"]:
            print(f"      Missing: {', '.join(sr['missing_criteria'])}")

    if passed:
        print("\n[GATE PASS] All sections fulfill depth completion criteria!")
        sys.exit(0)
    else:
        print(f"\n[GATE FAILED] Section depth score too low or shallow sections found:")
        for w in warns:
            print(f"  - {w}")
        sys.exit(1)
