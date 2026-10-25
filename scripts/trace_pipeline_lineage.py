#!/usr/bin/env python3
"""
scripts/trace_pipeline_lineage.py
=================================
글 작성 파이프라인 전체 파일 참조 및 데이터 흐름 전수 추적기.

어떤 파일로 시작해서, 어떤 코드들이 실행되며, 
그 코드들이 어떤 지식 문서/가이드 문서/데이터 파일을 읽고 쓰는지 
하나도 빠짐없이 전수 추적하여 계층별로 출력합니다.
"""

import os
import sys
import re
import yaml
import json
from typing import Dict, List, Set

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_DIR = os.path.join(BASE_DIR, "content-system")

def get_file_info(rel_path):
    abs_path = os.path.join(BASE_DIR, rel_path) if not os.path.isabs(rel_path) else rel_path
    exists = os.path.exists(abs_path)
    size = os.path.getsize(abs_path) if exists else 0
    lines = 0
    if exists:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = sum(1 for _ in f)
        except Exception:
            lines = -1
    return {
        "rel_path": os.path.relpath(abs_path, BASE_DIR).replace("\\", "/"),
        "abs_path": abs_path,
        "exists": exists,
        "size_bytes": size,
        "line_count": lines
    }

def trace_pipeline(sample_content_id="CNT-2026W39-001"):
    print("=" * 80)
    print(f"  [PIPELINE FULL FILE LINEAGE TRACER] - Target: {sample_content_id}")
    print("=" * 80)

    pipeline_stages = [
        {
            "stage_num": "00",
            "stage_name": "파이프라인 진입점 (Entry Points & API)",
            "executors": [
                {
                    "file": "services/gemini_writer.py",
                    "role": "Gemini 3.8 Flash 메인 작성 엔진 & QA/로지텍AI 오케스트레이터",
                    "calls": [
                        "services.device_blog_registry.get_device_blog_info",
                        "content-system.scripts.validate_claim_evidence.validate_claims",
                        "content-system.scripts.evaluate_editorial_quality.evaluate_editorial_quality",
                        "content-system.scripts.verify_blog_with_logitech_ai.verify_with_ai",
                        "content-system.scripts.export_naver_blog_html.py"
                    ]
                },
                {
                    "file": "services/content_ops_api.py",
                    "role": "웹 UI 워크벤치 REST API 백엔드 (Flask 서버 port 5000)",
                    "calls": ["services.gemini_writer.generate_draft", "static/content_ops.js"]
                },
                {
                    "file": "services/ask_logitech_ai.py",
                    "role": "로지텍 공식 서포트 AI 브라우저 서버 (port 5050)",
                    "calls": ["Kapa AI Support Agent (Headless Playwright)"]
                }
            ],
            "reads": [
                "config/config.json",
                "content-system/registry/CONTENT_REGISTRY.csv"
            ],
            "writes": []
        },
        {
            "stage_num": "01",
            "stage_name": "키워드 갭 분석 & 기획 브리프 (Brief & Keywords)",
            "executors": [
                {
                    "file": "services/gemini_writer.py -> analyze_topic_and_keywords()",
                    "role": "브리프 YAML에서 목표 키워드, 주제, 대상 장비/기능 메타데이터 추출",
                    "calls": []
                }
            ],
            "reads": [
                f"content-system/01_keyword_ai/briefs/{sample_content_id}.brief.yaml",
                "content-system/registry/CONTENT_REGISTRY.csv",
                "content-system/01_keyword_ai/briefs/CNT-2026W39-002.brief.yaml",
                "content-system/01_keyword_ai/briefs/CNT-2026W39-003.brief.yaml",
                "content-system/01_keyword_ai/briefs/CNT-2026W39-004.brief.yaml",
                "content-system/01_keyword_ai/briefs/CNT-2026W39-005.brief.yaml"
            ],
            "writes": []
        },
        {
            "stage_num": "02",
            "stage_name": "장비/기능 스펙 팩트 정밀 추출 (Pinpoint Knowledge Facts)",
            "executors": [
                {
                    "file": "services/gemini_writer.py -> extract_pinpoint_facts()",
                    "role": "전체 문서를 통째로 읽지 않고, 해당 키워드/장비/기능에 매칭되는 8~12개 팩트만 선별 추출",
                    "calls": []
                }
            ],
            "reads": [
                "content-system/03_sources/knowledge/products/KNW-PROD-LOGI-RALLYBAR.yaml",
                "content-system/03_sources/knowledge/features/KNW-FEAT-LOGI-RIGHTSIGHT2.yaml",
                "content-system/03_sources/knowledge/platforms/KNW-PLAT-ZOOM-ROOMS.yaml",
                "content-system/03_sources/knowledge/concepts/KNW-CONC-SPEAKER-TRACKING.yaml",
                "content-system/03_sources/knowledge/products/KNW-PROD-LOGI-MEETUP2.yaml",
                "content-system/03_sources/knowledge/products/KNW-PROD-LOGI-RALLYPLUS.yaml",
                "content-system/03_sources/knowledge/products/KNW-PROD-LOGI-TAP-IP.yaml"
            ],
            "writes": []
        },
        {
            "stage_num": "03",
            "stage_name": "기계적 주의사항 매칭 & Markdown 에디토리얼 가이드 로딩",
            "executors": [
                {
                    "file": "services/gemini_writer.py -> load_cautions_and_disjoint_rules()",
                    "role": "총판 정체성, 마이크 팟 화자추적 금지, FACT 태그 노출 금지 등 Zero-Tolerance 기계적 바인딩",
                    "calls": []
                },
                {
                    "file": "services/gemini_writer.py -> load_markdown_editorial_guidelines()",
                    "role": "파이썬 하드코딩 대신 Markdown 문서 자체를 SSOT로 로드하여 프롬프트에 주입",
                    "calls": []
                }
            ],
            "reads": [
                "content-system/02_writer_ai/core/WRITING_CORE.md",
                "content-system/02_writer_ai/WRITING_GUIDE.md",
                "content-system/02_writer_ai/core/STYLE_CORE.md",
                "content-system/02_writer_ai/core/SAFETY_CORE.md"
            ],
            "writes": []
        },
        {
            "stage_num": "04",
            "stage_name": "시각 자산 매핑 & 공식 디바이스 블로그 링크 실시간 조회",
            "executors": [
                {
                    "file": "services/gemini_writer.py -> build_visual_asset_guide()",
                    "role": "INDEX.yaml에서 에셋 목적/캡션을 조회하여 3단계 본문 적재적소 배치 가이드 생성",
                    "calls": []
                },
                {
                    "file": "services/device_blog_registry.py -> get_device_blog_info()",
                    "role": "Blog Manager DB(index.json) 실시간 조회하여 포스팅당 단 1개 대표 장비 링크 생성",
                    "calls": []
                }
            ],
            "reads": [
                "content-system/03_sources/assets/INDEX.yaml",
                "data/index.json"
            ],
            "writes": []
        },
        {
            "stage_num": "05",
            "stage_name": "초안 생성 (3단계: 초반/Hook -> 중반/원리·배선 -> 마감/CTA)",
            "executors": [
                {
                    "file": "services/gemini_writer.py -> call_gemini()",
                    "role": "Google Gemini 3.8 Flash API 4개 키 로테이션 및 마크다운 원고 스트리밍 생성",
                    "calls": ["https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"]
                }
            ],
            "reads": [],
            "writes": [
                f"content-system/02_writer_ai/drafts/{sample_content_id}.draft.md",
                f"content-system/02_writer_ai/drafts/{sample_content_id}.draft_v1.md"
            ]
        },
        {
            "stage_num": "06",
            "stage_name": "QA 평가 게이트 (Gate 1 기술 사실 + Gate 2 에디토리얼 품질)",
            "executors": [
                {
                    "file": "content-system/scripts/validate_claim_evidence.py",
                    "role": "원고 내 수치/단위/주장 추출 후 property_ontology 및 Knowledge Facts와 100% 대조",
                    "calls": ["content-system/scripts/extract_claims.py"]
                },
                {
                    "file": "content-system/scripts/evaluate_editorial_quality.py",
                    "role": "미사여구 남발, 기계적 레이블, 링크 중복, 고객사 사칭, 마이크팟 추적 왜곡 검점 (100점 만점)",
                    "calls": []
                }
            ],
            "reads": [
                f"content-system/02_writer_ai/drafts/{sample_content_id}.draft.md",
                "content-system/00_system/taxonomy/property_ontology.yaml",
                f"content-system/02_writer_ai/strategy/{sample_content_id}.strategy.yaml"
            ],
            "writes": [
                f"content-system/04_qa_ai/reports/{sample_content_id}.qa.yaml"
            ]
        },
        {
            "stage_num": "07",
            "stage_name": "로지텍 AI 공식 팩트체크 및 2개 대기열(Queue) 분기 적재",
            "executors": [
                {
                    "file": "content-system/scripts/verify_blog_with_logitech_ai.py",
                    "role": "원고를 로지텍 RAG 서포트 봇(port 5050)으로 전송하여 공식 스펙/외부 내용 전수 검토",
                    "calls": ["http://127.0.0.1:5050/ask"]
                }
            ],
            "reads": [
                f"content-system/02_writer_ai/drafts/{sample_content_id}.draft.md",
                f"content-system/01_keyword_ai/briefs/{sample_content_id}.brief.yaml"
            ],
            "writes": [
                f"content-system/04_qa_ai/reports/{sample_content_id}_logitech_ai_factcheck_*.md",
                f"content-system/04_qa_ai/verification/{sample_content_id}.verification.yaml",
                "content-system/04_qa_ai/verification/knowledge_update_queue.yaml",
                "content-system/04_qa_ai/verification/admin_review_queue.yaml",
                "content-system/logs/events.jsonl"
            ]
        },
        {
            "stage_num": "08",
            "stage_name": "네이버 블로그 HTML 컴파일 & 발행 준비 동기화",
            "executors": [
                {
                    "file": "content-system/scripts/export_naver_blog_html.py",
                    "role": "마크다운 원고를 네이버 스마트에디터 호환 인라인 스타일 HTML 및 비즈니스 배너로 컴파일",
                    "calls": []
                }
            ],
            "reads": [
                f"content-system/02_writer_ai/drafts/{sample_content_id}.draft.md"
            ],
            "writes": [
                f"content-system/05_publish/ready/{sample_content_id}.final.md",
                f"content-system/05_publish/ready/{sample_content_id}.naver.html"
            ]
        },
        {
            "stage_num": "09",
            "stage_name": "UI 워크벤치 및 콘솔 관리자 체크사항(Admin Checkpoints) 노출",
            "executors": [
                {
                    "file": "static/content_ops.js",
                    "role": "콘텐츠 상세 모달 및 관리자 승인 큐 UI 렌더링",
                    "calls": ["/api/content-system/contents/<id>/verify-item"]
                },
                {
                    "file": "services/gemini_writer.py -> print_pipeline_summary()",
                    "role": "CLI 터미널에 파이프라인 단계별 성공 여부 및 관리자 체크포인트 전수 출력",
                    "calls": []
                }
            ],
            "reads": [
                f"content-system/04_qa_ai/verification/{sample_content_id}.verification.yaml",
                "content-system/04_qa_ai/verification/admin_review_queue.yaml"
            ],
            "writes": []
        }
    ]

    all_read_files = set()
    all_write_files = set()
    all_exec_files = set()

    for stage in pipeline_stages:
        print(f"\n================================================================================")
        print(f" [단계 {stage['stage_num']}] {stage['stage_name']}")
        print(f"================================================================================")

        print(f"\n  [실행 코드 및 모듈 (Executors)]:")
        for exe in stage["executors"]:
            fn = exe["file"].split(" -> ")[0]
            info = get_file_info(fn)
            status = f"존재 ({info['line_count']}줄, {info['size_bytes']:,}B)" if info["exists"] else "미존재/동적"
            print(f"    - 파일: {exe['file']}")
            print(f"      상태: {status}")
            print(f"      역할: {exe['role']}")
            if exe.get("calls"):
                print(f"      참조/호출: {', '.join(exe['calls'])}")
            all_exec_files.add(fn)

        if stage["reads"]:
            print(f"\n  [참조/입력 문서 및 데이터 (Reads)]:")
            for rf in stage["reads"]:
                info = get_file_info(rf)
                st = f"✓ 정상 ({info['line_count']}줄, {info['size_bytes']:,}B)" if info["exists"] else "⚠ 미존재"
                print(f"    - {rf} [{st}]")
                all_read_files.add(rf)

        if stage["writes"]:
            print(f"\n  [생성/적재 결과 파일 (Writes)]:")
            for wf in stage["writes"]:
                info = get_file_info(wf)
                st = f"✓ 파일있음 ({info['size_bytes']:,}B)" if info["exists"] else "⏳ 파이프라인 실행 시 생성"
                print(f"    - {wf} [{st}]")
                all_write_files.add(wf)

    print("\n" + "=" * 80)
    print(f"  [전체 파이프라인 관여 파일 총 집계]")
    print(f"  - 실행 엔진/스크립트: {len(all_exec_files)}개 파일")
    print(f"  - 참조/입력 문서/지식/규칙: {len(all_read_files)}개 파일")
    print(f"  - 생성/출력/대기열/리포트: {len(all_write_files)}개 파일")
    print("=" * 80)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "CNT-2026W39-001"
    trace_pipeline(target)
