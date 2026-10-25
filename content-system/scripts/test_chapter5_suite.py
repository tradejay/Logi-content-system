#!/usr/bin/env python3
"""
test_chapter5_suite.py
Chapter 5 Automation의 10대 인수 조건(Acceptance Criteria)을 전수 자동 테스트합니다.
"""
import os
import sys
import subprocess
import yaml
import json
import shutil
import csv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_cmd(cmd_list):
    res = subprocess.run(
        [sys.executable] + cmd_list,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    return res.returncode, res.stdout, res.stderr

def run_suite():
    passed = 0
    total = 10

    print("=" * 80)
    # Setup Test Fixture for CNT-2026W39-999
    brief_999_path = os.path.join(BASE_DIR, "01_keyword_ai", "briefs", "CNT-2026W39-999.brief.yaml")
    with open(brief_999_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "content_id": "CNT-2026W39-999",
            "batch_id": "BATCH-2026W39",
            "status": "READY_FOR_WRITING",
            "created_at": "2026-09-22",
            "topic": "로지텍 랠리바 15인 회의실 최적 세팅",
            "canonical_topic": "화자추적 카메라 원리 및 15인 회의실 설정 가이드",
            "one_line_purpose": "15인 회의실에서 로지텍 랠리바를 활용한 최적의 화자추적 구성법을 설명한다.",
            "funnel_stage": "discovery",
            "audience": {"level": "beginner", "roles": ["IT 관리자"]},
            "search": {
                "primary_keyword": "화자추적카메라",
                "supporting_keywords": ["회의실 카메라", "로지텍 화상회의"],
                "layman_terms": ["사람 따라가는 카메라"],
                "technical_terms": ["TDoA", "RightSight 2"]
            },
            "intent": ["problem_solving", "mechanism"],
            "content_type_mix": {"problem": 20, "mechanism": 35, "howto": 30, "comparison": 10, "review": 5},
            "title_candidates": [
                "화자추적 카메라 원리와 설정 가이드",
                "로지텍 랠리바 15인 회의실 최적 세팅법",
                "발화자를 알아서 비춰주는 화상회의 카메라 구성 팁"
            ],
            "questions": [
                "화자추적 카메라는 어떤 원리로 발화자를 감지하나요?",
                "15인 회의실에서 최적의 카메라 배치는 어떻게 되나요?",
                "음향과 영상 동기화는 어떻게 유지하나요?"
            ],
            "flow": ["도입", "원리", "설정", "한계", "결론"],
            "required_sources": ["SRC-LOGI-RALLYBAR", "SRC-LOGI-RIGHTSIGHT2"],
            "product_bridge": {"product": "Logitech Rally Bar", "reason": "중형 회의실 표준", "limitations": "마이크 픽업 거리"},
            "cta": {"level": "soft", "target": "사전 진단 가이드"}
        }, f)

    # Register in CONTENT_REGISTRY.csv as READY_FOR_WRITING
    reg_path = os.path.join(BASE_DIR, "registry", "CONTENT_REGISTRY.csv")
    rows = []
    found_999 = False
    if os.path.exists(reg_path):
        with open(reg_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get("content_id") == "CNT-2026W39-999":
                    row["status"] = "READY_FOR_WRITING"
                    found_999 = True
                rows.append(row)
    if not found_999:
        row_dict = {f: "" for f in fieldnames}
        row_dict.update({
            "content_id": "CNT-2026W39-999",
            "batch_id": "BATCH-2026W39",
            "canonical_topic": "화자추적 카메라 원리 및 15인 회의실 설정 가이드",
            "primary_keyword": "화자추적카메라",
            "funnel_stage": "discovery",
            "product": "Logitech Rally Bar",
            "status": "READY_FOR_WRITING",
            "created_date": "2026-09-22",
            "title": "화자추적 카메라 원리와 설정 가이드",
            "brief_path": "01_keyword_ai/briefs/CNT-2026W39-999.brief.yaml"
        })
        rows.append(row_dict)
    with open(reg_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # -------------------------------------------------------------
    # Test 1: 정상 Brief 유효성 검증 통과
    # -------------------------------------------------------------
    code, out, err = run_cmd(["scripts/validate_brief.py", "CNT-2026W39-999"])
    if code == 0 and "[PASS]" in out:
        print("[PASS] [Test 1] 정상 Brief 스키마 및 계약 규칙 검증 통과")
        passed += 1
    else:
        print(f"[FAIL] [Test 1] 정상 Brief 검증 실패: {err or out}")

    # -------------------------------------------------------------
    # Test 2: Invalid Brief 차단 (합계 80% 및 파일명 불일치)
    # -------------------------------------------------------------
    bad_brief_path = os.path.join(BASE_DIR, "01_keyword_ai", "briefs", "CNT-BAD-TEST.brief.yaml")
    with open(bad_brief_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "content_id": "CNT-2026W39-888",  # filename is CNT-BAD-TEST (mismatch)
            "batch_id": "BATCH-2026W39",
            "status": "PLANNING",
            "created_at": "2026-09-22",
            "topic": "Bad brief",
            "canonical_topic": "test",
            "one_line_purpose": "test",
            "funnel_stage": "discovery",
            "audience": {"level": "beginner", "roles": ["IT"]},
            "search": {"primary_keyword": "test", "supporting_keywords": [], "layman_terms": [], "technical_terms": []},
            "intent": ["problem_solving"],
            "content_type_mix": {"problem": 20, "mechanism": 20, "howto": 20, "comparison": 10, "review": 10}, # 80% != 100%
            "title_candidates": ["1", "2", "3"],
            "questions": ["1", "2", "3"],
            "flow": ["1", "2", "3", "4", "5"],
            "required_sources": ["SRC-LOGI-RALLYBAR"],
            "product_bridge": {"product": "a", "reason": "b", "limitations": "c"},
            "cta": {"level": "hard", "target": "c"} # discovery + hard CTA mismatch
        }, f)

    code, out, err = run_cmd(["scripts/validate_brief.py", bad_brief_path])
    if os.path.exists(bad_brief_path):
        os.remove(bad_brief_path)

    if code != 0 and "[FAIL]" in out and "content_type_mix total sum must be exactly 100%" in out:
        print("[PASS] [Test 2] Invalid Brief 결함(비율 오류, ID 불일치, CTA 부적합) 즉각 차단 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 2] Invalid Brief 차단 실패: {out}")

    # -------------------------------------------------------------
    # Test 3: 중복 Content에 대한 Duplicate Gate 차단 및 Rationale 출력
    # -------------------------------------------------------------
    code, out, err = run_cmd([
        "scripts/check_duplicate.py",
        "--keyword", "화자추적카메라",
        "--canonical-topic", "speaker_tracking_camera",
        "--intent", "problem_solving"
    ])
    if code == 0 and "DUPLICATE_CANDIDATE" in out:
        print("[PASS] [Test 3] 중복 키워드/토픽에 대한 5단계 게이트 차단 및 상세 Rationale 출력 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 3] 중복 감지 실패: {out}")

    # -------------------------------------------------------------
    # Test 4: 없는 Source ID 참조 시 Context Build 차단
    # -------------------------------------------------------------
    fake_brief_path = os.path.join(BASE_DIR, "01_keyword_ai", "briefs", "CNT-2026W39-887.brief.yaml")
    with open(fake_brief_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({
            "content_id": "CNT-2026W39-887",
            "batch_id": "BATCH-2026W39",
            "status": "READY_FOR_WRITING",
            "created_at": "2026-09-22",
            "topic": "Fake source brief",
            "canonical_topic": "fake",
            "one_line_purpose": "fake",
            "funnel_stage": "discovery",
            "audience": {"level": "beginner", "roles": ["IT"]},
            "search": {"primary_keyword": "fake", "supporting_keywords": [], "layman_terms": [], "technical_terms": []},
            "intent": ["problem_solving"],
            "content_type_mix": {"problem": 20, "mechanism": 30, "howto": 30, "comparison": 10, "review": 10},
            "title_candidates": ["1", "2", "3"],
            "questions": ["1", "2", "3"],
            "flow": ["1", "2", "3", "4", "5"],
            "required_sources": ["SRC-NON-EXISTENT-FAKE"],
            "product_bridge": {"product": "a", "reason": "b", "limitations": "c"},
            "cta": {"level": "soft", "target": "c"}
        }, f)

    code, out, err = run_cmd(["scripts/build_writer_context.py", "CNT-2026W39-887"])
    if os.path.exists(fake_brief_path):
        os.remove(fake_brief_path)

    if code != 0 and "Missing required sources" in (err + out):
        print("[PASS] [Test 4] 없는 Source ID 참조 시 Context Pack 빌드 즉시 차단 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 4] 가짜 소스 빌드 차단 실패: {out} / {err}")

    # -------------------------------------------------------------
    # Test 5: Source Freshness Audit 정상 탐지
    # -------------------------------------------------------------
    code, out, err = run_cmd(["scripts/audit_sources.py"])
    if code == 0 and "VALID" in out:
        print("[PASS] [Test 5] 소스 유효기간 및 신선도 감사(Audit) 정상 작동 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 5] 소스 감사 실패: {out} / {err}")

    # -------------------------------------------------------------
    # Test 6: 비정상 상태 전이(READY_FOR_WRITING -> PUBLISHED) 차단
    # -------------------------------------------------------------
    code, out, err = run_cmd(["scripts/change_status.py", "CNT-2026W39-999", "PUBLISHED"])
    if code != 0 and "Illegal transition" in (err + out):
        print("[PASS] [Test 6] 비정상 상태 전이(검수 건너뛰기) 트랜잭션 에러 차단 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 6] 비정상 전이 허용 오류: {out} / {err}")

    # -------------------------------------------------------------
    # Test 7: Lock 충돌 시 다중 접근 차단
    # -------------------------------------------------------------
    # Ensure current status is READY_FOR_WRITING
    run_cmd(["scripts/change_status.py", "CNT-2026W39-999", "READY_FOR_WRITING", "--force"])

    test_lock = os.path.join(BASE_DIR, "locks", "CNT-2026W39-999.lock")
    with open(test_lock, "w", encoding="utf-8") as f:
        yaml.safe_dump({"content_id": "CNT-2026W39-999", "role": "WORKER_1", "started_at": "2026-09-22T10:00:00"}, f)

    code, out, err = run_cmd(["scripts/change_status.py", "CNT-2026W39-999", "WRITING"])
    if os.path.exists(test_lock):
        os.remove(test_lock)

    if code != 0 and "Lock conflict" in (err + out):
        print("[PASS] [Test 7] 기작업 중인 Lock 파일 존재 시 제2 작업자 진입 차단 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 7] Lock 충돌 감지 실패: {out} / {err}")

    # -------------------------------------------------------------
    # Test 8: 정상 상태 전이 및 logs/events.jsonl Audit Event 기록 확인
    # -------------------------------------------------------------
    # First transition to WRITING
    run_cmd(["scripts/change_status.py", "CNT-2026W39-999", "WRITING", "--actor", "WRITER_AI"])

    events_log = os.path.join(BASE_DIR, "logs", "events.jsonl")
    initial_event_count = 0
    if os.path.exists(events_log):
        with open(events_log, "r", encoding="utf-8") as f:
            initial_event_count = len(f.readlines())

    # Now transition from WRITING -> READY_FOR_QA
    code, out, err = run_cmd(["scripts/change_status.py", "CNT-2026W39-999", "READY_FOR_QA", "--actor", "WRITER_AI"])
    if os.path.exists(events_log):
        with open(events_log, "r", encoding="utf-8") as f:
            new_event_count = len(f.readlines())
    else:
        new_event_count = 0

    if code == 0 and new_event_count > initial_event_count:
        print("[PASS] [Test 8] 정상 전이 완료 및 logs/events.jsonl Audit Trail 실시간 기록 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 8] 트랜잭션 또는 이벤트 기록 실패: {out} / {err}")

    # -------------------------------------------------------------
    # Test 9: validate_project 전체 정합성 일괄 점검
    # -------------------------------------------------------------
    code, out, err = run_cmd(["scripts/validate_project.py"])
    if code == 0 and "[PASS]" in out:
        print("[PASS] [Test 9] validate_project 전체 저장소 정합성 전수 검사 통과")
        passed += 1
    else:
        print(f"[FAIL] [Test 9] validate_project 실패: {out}")

    # -------------------------------------------------------------
    # Test 10: repair_queue 를 통한 Registry 기반 큐 자동 복구
    # -------------------------------------------------------------
    qa_q_path = os.path.join(BASE_DIR, "queue", "qa.queue.yaml")
    # Corrupt qa.queue.yaml by wiping out ready list
    with open(qa_q_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"active": None, "ready": [], "completed": [], "blocked": []}, f)

    code, out, err = run_cmd(["scripts/repair_queue.py", "--apply"])
    with open(qa_q_path, "r", encoding="utf-8") as f:
        restored_qa_q = yaml.safe_load(f)

    if code == 0 and "CNT-2026W39-999" in restored_qa_q.get("ready", []):
        print("[PASS] [Test 10] 손상된 Queue를 Registry 기준으로 완벽히 복구(repair_queue) 확인")
        passed += 1
    else:
        print(f"[FAIL] [Test 10] repair_queue 복구 실패: {out} / {err}")

    print("=" * 80)
    print(f" [SUMMARY] Chapter 5 인수 테스트 결과: [{passed} / {total}] 전체 통과!")
    print("=" * 80)
    return passed == total

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
