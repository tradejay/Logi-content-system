"""
scripts/recover_pipeline.py
파이프라인 중단 복구 도구 (Interrupted Pipeline Recovery Tool)

비정상 종료된 프로세스 또는 고아 잠금(Orphaned Lock)을 정밀 식별하여 안전하게 복구합니다.
살아 있는 프로세스의 잠금은 절대 해제하지 않으며, dry-run 모드를 기본으로 제공합니다.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

# 상위 경로 모듈 로드 지원
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import psutil
import threading
import uuid
from services.pipeline_status import (
    read_pipeline_lock, check_process_liveness, read_json_file,
    cross_process_gate, SERVER_INSTANCE_TOKEN
)
from services.content_pipeline import atomic


def now():
    return datetime.now(timezone.utc).isoformat()


def inspect_recovery_target(root, cid):
    """
    단일 content_id에 대해 복구 필요 여부와 상세 증거를 조사합니다.
    """
    root = Path(root)
    work_dir = root / f'content-system/working/{cid}'
    if not work_dir.is_dir():
        return None

    lock_data = read_pipeline_lock(root, cid)
    latest_path = work_dir / 'pipeline-latest.json'
    latest = read_json_file(latest_path) or {}

    liveness = check_process_liveness(lock_data) if lock_data else 'NO_LOCK'
    is_latest_running = (latest.get('outcome') == 'RUNNING')

    is_eligible = False
    status_summary = 'HEALTHY'
    evidence = []

    if lock_data:
        if liveness == 'DEAD':
            is_eligible = True
            status_summary = 'INTERRUPTED_DEAD_PROCESS'
            evidence.append(f"프로세스 PID {lock_data.get('pid')} 종료 확인됨 (생존 확인: DEAD)")
        elif liveness == 'ALIVE':
            status_summary = 'ACTIVE_RUNNING'
            evidence.append(f"프로세스 PID {lock_data.get('pid')} 실제 실행 중 (생존 확인: ALIVE)")
        else: # UNKNOWN
            status_summary = 'LOCK_UNKNOWN'
            evidence.append(f"잠금 존재하나 프로세스 상태 불명 (PID={lock_data.get('pid')})")
    elif is_latest_running:
        is_eligible = True
        status_summary = 'INTERRUPTED_OUTCOME_RUNNING'
        evidence.append("잠금 파일은 없으나 latest_run의 outcome이 RUNNING 상태로 방치됨")

    planned_changes = []
    if is_eligible:
        if lock_data:
            planned_changes.append(f"DELETE: {lock_data.get('path', str(work_dir / 'pipeline.lock'))}")
        planned_changes.append(f"UPDATE: {latest_path} (stage=finished, outcome=FAILED, publish_ready=false)")
        target_run_id = (lock_data or {}).get('run_id') or latest.get('run_id')
        if target_run_id:
            run_result_path = work_dir / f'runs/{target_run_id}/run-result.json'
            if run_result_path.is_file():
                planned_changes.append(f"UPDATE: {run_result_path}")

    return {
        'content_id': cid,
        'eligible': is_eligible,
        'status': status_summary,
        'liveness': liveness,
        'lock_info': lock_data,
        'latest_run_id': latest.get('run_id'),
        'latest_outcome': latest.get('outcome'),
        'evidence': evidence,
        'planned_changes': planned_changes
    }


@contextmanager
def recovery_exclusive_lock(root, cid, expected_run_id=None, allow_unknown=False):
    """
    복구 대상 콘텐츠에 대해 확인부터 저장 완료까지 프로세스 간 배타 잠금을 유지합니다.
    - cross_process_gate: 프로세스 간 원자적 게이트 락 (OS 커널 수준 배타 락)
    - pipeline.lock: RECOVERING 상태의 배타 잠금을 점유하여 외부 실행 차단
    - lock_token: 고유 소유 토큰을 검증하여 자기 소유 잠금만 안전하게 해제
    """
    root = Path(root)
    work_dir = root / f'content-system/working/{cid}'
    work_dir.mkdir(parents=True, exist_ok=True)
    lock_file = work_dir / 'pipeline.lock'
    latest_path = work_dir / 'pipeline-latest.json'

    recovery_token = uuid.uuid4().hex

    with cross_process_gate(root, cid):
        # 1. 생존 확인: 기존 잠금이 살아있는 프로세스이거나 UNKNOWN(강제 옵션 없을 때)인지 검사
        current_lock = read_pipeline_lock(root, cid)
        if current_lock:
            cur_liveness = check_process_liveness(current_lock)
            if cur_liveness == 'ALIVE':
                raise RuntimeError(f"복구 취소: content {cid}의 프로세스 PID {current_lock.get('pid')}가 실행 중입니다.")
            if cur_liveness == 'UNKNOWN' and not allow_unknown:
                raise RuntimeError(f"복구 취소: content {cid}의 프로세스 PID {current_lock.get('pid')}의 상태가 확인 불가(UNKNOWN)입니다. 강제 복구가 필요한 경우 --force 옵션을 사용하세요.")

        # 2. 최신 run_id 1차 확인 (고아 잠금 교체 전 새 실행 시작 여부 확인)
        if current_lock and expected_run_id and current_lock.get('run_id') and current_lock.get('run_id') != expected_run_id:
            raise RuntimeError(f"복구 취소: content {cid}에 새로운 run({current_lock.get('run_id')})이 감지되었습니다 (기존 예정: {expected_run_id}).")

        latest = read_json_file(latest_path) or {}
        if expected_run_id and latest.get('run_id') and latest.get('run_id') != expected_run_id:
            raise RuntimeError(f"복구 취소: content {cid}에 새로운 run({latest.get('run_id')})이 감지되었습니다 (기존 예정: {expected_run_id}).")

        # 3. 원자적으로 고아 잠금 교체 / 복구 잠금 점유 (소유 토큰 기록)
        cur_proc = psutil.Process()
        rec_lock_payload = {
            'content_id': cid,
            'run_id': expected_run_id,
            'lock_token': recovery_token,
            'pid': os.getpid(),
            'process_create_time': cur_proc.create_time(),
            'server_token': SERVER_INSTANCE_TOKEN,
            'thread_id': threading.get_ident(),
            'started_at': now(),
            'updated_at': now(),
            'status': 'RECOVERING',
            'stage': 'recovery'
        }
        lock_file.write_text(json.dumps(rec_lock_payload, ensure_ascii=False), encoding='utf-8')

    try:
        yield lock_file
    finally:
        with cross_process_gate(root, cid):
            current = read_pipeline_lock(root, cid)
            if current and current.get('lock_token') == recovery_token:
                lock_file.unlink(missing_ok=True)


def recover_target(root, item, reason="관리자 복구 도구에 의한 중단 복구", allow_unknown=False):
    """
    단일 대상에 대해 안전하게 복구를 실행합니다.
    확인부터 저장까지 배타 잠금을 유지하여 복구 경쟁을 원천 방지합니다.
    """
    root = Path(root)
    cid = item['content_id']
    work_dir = root / f'content-system/working/{cid}'
    expected_run_id = item.get('latest_run_id')

    with recovery_exclusive_lock(root, cid, expected_run_id=expected_run_id, allow_unknown=allow_unknown) as lock_file:
        latest_path = work_dir / 'pipeline-latest.json'
        latest = read_json_file(latest_path) or {}

        # 1. 최신 run_id 확인
        if expected_run_id and latest.get('run_id') and latest.get('run_id') != expected_run_id:
            raise RuntimeError(f"복구 취소: content {cid}에 새로운 run({latest.get('run_id')})이 감지되었습니다 (기존 예정: {expected_run_id}).")

        timestamp = now()
        recovery_note = f"파이프라인 실행 비정상 중단 복구 ({reason})"

        # 2. 최신 결과 업데이트 객체 구성
        latest['stage'] = 'finished'
        latest['stage_detail'] = '중단 복구 완료'
        latest['outcome'] = 'FAILED'
        latest['publish_ready'] = False
        latest['error'] = recovery_note
        latest['recovered_at'] = timestamp
        latest['recovered_reason'] = reason

        logs = latest.setdefault('natural_logs', [])
        logs.append({
            'at': timestamp,
            'stage': 'recovery',
            'title': '파이프라인 중단 복구',
            'message': recovery_note,
            'status': 'WARN'
        })

        # 3. 저장 직전 run_id 재검증 (CAS: Compare-And-Swap 검증)
        fresh_latest = read_json_file(latest_path) or {}
        if expected_run_id and fresh_latest.get('run_id') and fresh_latest.get('run_id') != expected_run_id:
            raise RuntimeError(f"복구 취소: content {cid}에 새로운 run({fresh_latest.get('run_id')})이 감지되었습니다 (기존 예정: {expected_run_id}).")

        # 4. 저장 (원자적 파일 갱신)
        atomic(latest_path, latest)

        # 5. 해당 run 디렉터리의 run-result.json 업데이트
        target_run_id = expected_run_id or latest.get('run_id')
        if target_run_id:
            run_res_path = work_dir / f'runs/{target_run_id}/run-result.json'
            if run_res_path.is_file():
                run_data = read_json_file(run_res_path) or {}
                run_data['stage'] = 'finished'
                run_data['outcome'] = 'FAILED'
                run_data['publish_ready'] = False
                run_data['error'] = recovery_note
                run_data['recovered_at'] = timestamp
                atomic(run_res_path, run_data)

    return {
        'content_id': cid,
        'recovered': True,
        'recovered_at': timestamp,
        'run_id': target_run_id
    }


def main():
    parser = argparse.ArgumentParser(description="파이프라인 중단 복구 도구 (Interrupted Pipeline Recovery Tool)")
    parser.add_argument("content_id", nargs="?", default=None, help="복구 대상 콘텐츠 ID (생략 시 전체 스캔)")
    parser.add_argument("--apply", action="store_true", help="실제 복구 적용 (미지정 시 dry-run 미리보기)")
    parser.add_argument("--force", action="store_true", help="상태 불명(UNKNOWN) 잠금도 강제 복구")
    parser.add_argument("--reason", default="비정상 종료된 프로세스 정리", help="복구 사유")
    parser.add_argument("--json", action="store_true", help="JSON 포맷으로 출력")

    args = parser.parse_args()
    root = BASE_DIR
    working_root = root / 'content-system/working'

    if not working_root.is_dir():
        print(f"Working directory not found: {working_root}")
        return 1

    targets = []
    if args.content_id:
        targets.append(args.content_id)
    else:
        for p in sorted(working_root.iterdir()):
            if p.is_dir() and p.name.startswith("CNT-"):
                targets.append(p.name)

    results = []
    for cid in targets:
        info = inspect_recovery_target(root, cid)
        if info:
            if args.force and info['status'] == 'LOCK_UNKNOWN':
                info['eligible'] = True
                info['evidence'].append("--force 옵션으로 UNKNOWN 잠금 복구 대상으로 지정됨")
            results.append(info)

    eligible_items = [r for r in results if r['eligible']]

    if args.json:
        output_payload = {
            'mode': 'apply' if args.apply else 'dry-run',
            'scanned_count': len(results),
            'eligible_count': len(eligible_items),
            'items': results
        }
        if args.apply:
            applied = []
            for item in eligible_items:
                try:
                    res = recover_target(root, item, reason=args.reason, allow_unknown=args.force)
                    applied.append(res)
                except Exception as err:
                    applied.append({'content_id': item['content_id'], 'error': str(err)})
            output_payload['applied'] = applied
        print(json.dumps(output_payload, ensure_ascii=False, indent=2))
        return 0

    print("=" * 65)
    print(f" 파이프라인 중단 복구 도구 ({'APPLY 실행' if args.apply else 'DRY-RUN 미리보기'})")
    print(f" 실행 시각: {now()}")
    print("=" * 65)

    if not eligible_items:
        print("✅ 복구가 필요한 중단 실행 또는 고아 잠금이 없습니다. (모든 작업 정상)")
        for r in results:
            if r['status'] == 'ACTIVE_RUNNING':
                print(f"   - {r['content_id']}: 활성 프로세스 실행 중 (PID {r['lock_info'].get('pid')}) -> 보호됨")
        return 0

    print(f"총 {len(eligible_items)}건의 복구 대상이 감지되었습니다.\n")
    for item in eligible_items:
        print(f"▶ [{item['content_id']}] 상태: {item['status']}")
        for ev in item['evidence']:
            print(f"   • 증거: {ev}")
        print("   • 예정된 변경사항:")
        for chg in item['planned_changes']:
            print(f"     - {chg}")
        print()

    if not args.apply:
        print("-" * 65)
        print("💡 위 작업은 DRY-RUN 미리보기입니다. 실제 적용하려면 --apply 옵션을 사용하세요:")
        print(f"   python scripts/recover_pipeline.py {' '.join(sys.argv[1:])} --apply")
        print("-" * 65)
        return 0

    # 실제 복구 수행
    print("복구를 진행합니다...")
    for item in eligible_items:
        try:
            res = recover_target(root, item, reason=args.reason, allow_unknown=args.force)
            print(f"✅ [{item['content_id']}] 복구 성공 (run_id: {res['run_id']})")
        except Exception as err:
            print(f"❌ [{item['content_id']}] 복구 실패: {err}")

    print("\n복구 작업이 완료되었습니다.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
