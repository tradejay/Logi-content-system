"""
services/pipeline_status.py
공통 운영 상태 계산 모듈 (Unified Content Operations Status Plane)
대시보드 집계, 목록 API, 보드(Board), 워크벤치(Workbench), 디스패처가 동일한 현재 상태를 공유합니다.
"""

from contextlib import contextmanager
from datetime import datetime, timezone, date
import json
import os
from pathlib import Path
import psutil
import time
import uuid
from collections import defaultdict
import threading

SERVER_INSTANCE_TOKEN = uuid.uuid4().hex

_CID_LOCKS = defaultdict(threading.RLock)
_GATE_LOCK = threading.Lock()


def get_cid_lock(cid):
    """콘텐츠 ID별 프로세스 내 배타 잠금(RLock)을 반환합니다."""
    with _GATE_LOCK:
        return _CID_LOCKS[cid]


@contextmanager
def cross_process_gate(root, cid, timeout=10.0, retry_interval=0.02):
    """
    콘텐츠 ID별 프로세스 간 원자적 게이트 락 (OS 커널 수준 배타 락).
    Windows(msvcrt)와 POSIX(fcntl)를 모두 지원하며, 프로세스 비정상 종료 시 OS가 자동 해제합니다.
    """
    gate_path = Path(root) / f'content-system/working/{cid}/.gate.lock'
    gate_path.parent.mkdir(parents=True, exist_ok=True)

    with get_cid_lock(cid):
        fd = open(gate_path, 'a+b')
        start_time = time.monotonic()
        locked = False
        while time.monotonic() - start_time < timeout:
            try:
                fd.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
            except (OSError, IOError):
                time.sleep(retry_interval)
        if not locked:
            fd.close()
            raise TimeoutError(f"Could not acquire cross-process gate for {cid} within {timeout}s")
        try:
            yield
        finally:
            try:
                fd.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                fd.close()


ROOT = Path(__file__).resolve().parents[1]


def read_json_file(path):
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def read_pipeline_lock(root, cid):
    """working/{cid}/pipeline.lock 파일 정보를 읽습니다."""
    path = Path(root) / f'content-system/working/{cid}/pipeline.lock'
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding='utf-8').strip()
        if not raw:
            # 빈 파일이거나 단순 텍스트
            return {'raw': '', 'pid': None, 'is_json': False, 'path': str(path),
                    'mtime': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data['is_json'] = True
                data['path'] = str(path)
                return data
        except Exception:
            pass
        # PID 숫자만 적힌 경우
        if raw.isdigit():
            return {'pid': int(raw), 'is_json': False, 'path': str(path)}
        return {'raw': raw, 'pid': None, 'is_json': False, 'path': str(path)}
    except Exception:
        return None


def check_process_liveness(lock_data):
    """
    lock 소유 프로세스의 생존 여부를 정밀 판정합니다.
    Returns: 'ALIVE' | 'DEAD' | 'UNKNOWN'
    """
    if not lock_data:
        return 'DEAD'

    pid = lock_data.get('pid')
    if pid is None:
        return 'UNKNOWN'

    try:
        pid = int(pid)
    except (ValueError, TypeError):
        return 'UNKNOWN'

    if not psutil.pid_exists(pid):
        return 'DEAD'

    try:
        proc = psutil.Process(pid)
        # 프로세스 생성 시각 대조 (PID 재할당 방지)
        recorded_create_time = lock_data.get('process_create_time')
        if recorded_create_time is not None:
            actual_create_time = proc.create_time()
            # 1초 이내 오차 허용
            if abs(actual_create_time - float(recorded_create_time)) > 1.5:
                # PID는 같으나 생성 시각이 다르면 이전 프로세스는 이미 종료되고 새 프로세스가 PID를 재사용한 것임
                return 'DEAD'
        
        # 프로세스 상태 확인
        status = proc.status()
        if status in [psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD]:
            return 'DEAD'

        return 'ALIVE'
    except psutil.AccessDenied:
        return 'UNKNOWN'
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return 'DEAD'
    except Exception:
        return 'UNKNOWN'


def calculate_effective_status(root, content_id, registry_row=None, latest_run=None, draft_text=None):
    """
    단일 글에 대한 공통 상태를 계산하여 일관된 계약 데이터를 반환합니다.
    
    상태 매트릭스:
    - PUBLISHED, ARCHIVED, CANCELLED 등 등록부 종료 상태: 원본 유지
    - 검증된 활성 실행: RUNNING
    - 활성 여부 불명: RUNNING_UNKNOWN (실행 확인 필요 / 새 실행 차단)
    - 종료가 확인된 RUNNING: INTERRUPTED (중단 복구 필요)
    - FAILED 또는 공식 검토 ERROR: FAILED
    - NEEDS_EVIDENCE: NEEDS_EVIDENCE
    - REVISION_REQUIRED: REVISION_REQUIRED
    - COMPLETED_REVIEW_PENDING: COMPLETED_REVIEW_PENDING (관리자 확인 대기)
    - COMPLETED_READY + 유효한 승인: READY_TO_PUBLISH
    - 승인본 원고/입력 변경: REVISION_REQUIRED (재검토 필요 / 발행 준비 해제)
    - 파이프라인 기록 없음: UNVERIFIED
    """
    root = Path(root)
    cid = content_id

    # 1. 최신 run 정보 로드 (전달되지 않은 경우)
    if latest_run is None:
        latest_path = root / f'content-system/working/{cid}/pipeline-latest.json'
        latest_run = read_json_file(latest_path) or {}

    # 2. 등록부 정보 추출
    registry_status = (registry_row or {}).get('status', 'PLANNING') if registry_row else 'PLANNING'

    # 기본 응답 틀
    res = {
        'content_id': cid,
        'registry_status': registry_status,
        'pipeline_outcome': latest_run.get('outcome'),
        'effective_status': 'UNVERIFIED',
        'reason': '',
        'run_id': latest_run.get('run_id'),
        'stage': latest_run.get('stage', 'planning'),
        'qa_passed': False,
        'publish_ready': False,
        'is_interrupted': False,
        'is_locked': False,
        'lock_info': None,
        'admin_pending_count': 0,
        'draft_changed': False,
        'input_changed': False,
        'changed_files': [],
        'details': {}
    }

    # 3. 발행 또는 종료된 글 보존 (PUBLISHED, ARCHIVED, CANCELLED, DUPLICATE)
    if registry_status in ['PUBLISHED', 'ARCHIVED', 'CANCELLED', 'DUPLICATE']:
        res['effective_status'] = registry_status
        res['reason'] = f'등록부 {registry_status} 상태 보존 (자동 재작성 생략)'
        res['publish_ready'] = (registry_status == 'PUBLISHED')
        return res

    # 4. 잠금 상태 및 실행 프로세스 생존 검증
    lock_data = read_pipeline_lock(root, cid)
    if lock_data:
        res['is_locked'] = True
        res['lock_info'] = lock_data
        liveness = check_process_liveness(lock_data)

        import threading
        is_self_lock = (lock_data.get('pid') == os.getpid() and lock_data.get('thread_id') == threading.get_ident())

        if not is_self_lock:
            if liveness == 'ALIVE':
                res['effective_status'] = 'RUNNING'
                stage_name = latest_run.get('stage') or lock_data.get('stage') or 'running'
                res['reason'] = f'파이프라인 실행 중 ({stage_name})'
                return res
            elif liveness == 'UNKNOWN':
                res['effective_status'] = 'RUNNING_UNKNOWN'
                res['reason'] = '실행 잠금이 있으나 프로세스 상태 불명 (확인 필요 / 신규 실행 차단)'
                return res
            else: # DEAD
                res['is_interrupted'] = True
                res['effective_status'] = 'INTERRUPTED'
                res['reason'] = '실행 프로세스가 비정상 종료됨 (중단 복구 필요)'
                return res

    # 잠금은 없지만 latest_run의 outcome이 'RUNNING'으로 남아있는 경우도 중단으로 판정
    if latest_run.get('outcome') == 'RUNNING':
        res['is_interrupted'] = True
        res['effective_status'] = 'INTERRUPTED'
        res['reason'] = '이전 실행이 비정상 종료됨 (결과 기록 RUNNING 방치, 중단 복구 필요)'
        return res

    # 5. 최신 run 기록이 없는 경우
    if not latest_run or not latest_run.get('run_id'):
        res['effective_status'] = 'UNVERIFIED'
        res['reason'] = f'공통 파이프라인 실행 기록 없음 (등록부: {registry_status})'
        return res

    # 6. 최신 run의 outcome별 상세 판정
    outcome = latest_run.get('outcome')
    res['admin_pending_count'] = len(latest_run.get('admin_checks', []))

    # 원고 해시 대조
    from services.pipeline_context import digest, contained
    draft_file = root / f'content-system/02_writer_ai/drafts/{cid}.draft.md'
    current_draft_text = draft_text
    if current_draft_text is None and draft_file.is_file():
        try:
            current_draft_text = draft_file.read_text(encoding='utf-8')
        except Exception:
            current_draft_text = None

    if current_draft_text is not None and latest_run.get('draft_sha256'):
        current_hash = digest(current_draft_text)
        if current_hash != latest_run['draft_sha256']:
            res['draft_changed'] = True
            res['changed_files'].append(f'draft:{cid}')

    # 입력 참조 파일 변경 대조
    for ref in latest_run.get('input_refs', []):
        ref_path_str = ref.get('path', '')
        if ref.get('virtual') or ref_path_str.startswith('virtual:'):
            if ref_path_str.startswith('virtual:product_links:'):
                try:
                    from services.pipeline_context import load_context
                    ctx = load_context(root, cid)
                    cur_digest = digest(json.dumps(ctx.get('product_links', {}), sort_keys=True, ensure_ascii=False))
                    if cur_digest != ref.get('sha256'):
                        res['input_changed'] = True
                        res['changed_files'].append(ref_path_str)
                except Exception:
                    pass
            continue
        try:
            ref_path = contained(root, ref_path_str)
            if not ref_path.is_file() or digest(ref_path.read_text(encoding='utf-8-sig')) != ref.get('sha256'):
                res['input_changed'] = True
                res['changed_files'].append(ref_path_str)
        except Exception:
            res['input_changed'] = True

    # 6-1. FAILED 또는 공식 검토 ERROR
    if outcome in ['FAILED', 'ERROR'] or latest_run.get('error'):
        res['effective_status'] = 'FAILED'
        res['reason'] = latest_run.get('error') or '파이프라인 실행 중 오류 발생'
        return res

    # 6-2. NEEDS_EVIDENCE
    if outcome == 'NEEDS_EVIDENCE':
        res['effective_status'] = 'NEEDS_EVIDENCE'
        res['reason'] = '근거 보완 대기 (누락 팩트 또는 출처 확인 필요)'
        return res

    # 6-3. REVISION_REQUIRED
    if outcome == 'REVISION_REQUIRED':
        res['effective_status'] = 'REVISION_REQUIRED'
        res['reason'] = '수정 필요 및 남은 QA/검토 항목 존재'
        return res

    # 6-4. COMPLETED_REVIEW_PENDING
    if outcome == 'COMPLETED_REVIEW_PENDING':
        if res['draft_changed'] or res['input_changed']:
            res['effective_status'] = 'REVISION_REQUIRED'
            res['reason'] = '관리자 승인 대기 중 원고 또는 입력 변경됨 (재검토 필요)'
        else:
            res['effective_status'] = 'COMPLETED_REVIEW_PENDING'
            res['reason'] = '원고 검증 통과 · 관리자 확인 대기 (발행 준비 아님)'
        res['publish_ready'] = False
        return res

    # 6-5. COMPLETED_READY (승인 유효성 정밀 검증)
    if outcome == 'COMPLETED_READY':
        # 승인 후 원고 또는 입력이 변경되었는지 확인
        if res['draft_changed'] or res['input_changed']:
            res['effective_status'] = 'REVISION_REQUIRED'
            res['reason'] = '승인본 원고 또는 관련 입력 변경 (재검토 필요 / 발행 준비 해제)'
            res['publish_ready'] = False
            return res

        # 승인 완료 확인: approval 객체가 존재하거나 (publish_ready=True 및 admin_checks 없음)
        has_approval = bool(latest_run.get('approval'))
        publish_ready = bool(latest_run.get('publish_ready', False))

        if publish_ready and has_approval:
            res['effective_status'] = 'READY_TO_PUBLISH'
            res['qa_passed'] = True
            res['publish_ready'] = True
            res['reason'] = '발행 준비 완료 (유효한 승인 확인)'
        elif publish_ready and not latest_run.get('admin_checks'):
            res['effective_status'] = 'READY_TO_PUBLISH'
            res['qa_passed'] = True
            res['publish_ready'] = True
            res['reason'] = '발행 준비 완료 (관리자 확인사항 없음)'
        else:
            res['effective_status'] = 'COMPLETED_REVIEW_PENDING'
            res['publish_ready'] = False
            res['reason'] = '승인 항목 또는 관리자 대기 항목 잔존'
        return res

    # 그 외 알려지지 않은 outcome
    res['effective_status'] = outcome or 'UNVERIFIED'
    res['reason'] = f'기타 상태 ({outcome})'
    return res


def get_aggregated_status_counts(root):
    """
    CONTENT_REGISTRY.csv의 모든 글에 대해 calculate_effective_status를 적용하여
    대시보드와 보드에서 완전히 일치하는 집계 카운트를 산출합니다.
    """
    import csv
    root = Path(root)
    registry_file = root / 'content-system/registry/CONTENT_REGISTRY.csv'
    
    counts = {
        'PLANNING': 0,
        'READY_FOR_WRITING': 0,
        'WRITING': 0,
        'READY_FOR_QA': 0,
        'REVISION_REQUIRED': 0,
        'COMPLETED_REVIEW_PENDING': 0,
        'READY_TO_PUBLISH': 0,
        'PUBLISHED': 0,
        'BLOCKED': 0,
        'NEEDS_EVIDENCE': 0,
        'INTERRUPTED': 0,
        'RUNNING': 0,
        'FAILED': 0
    }

    if not registry_file.is_file():
        return counts

    with registry_file.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get('content_id')
            if not cid:
                continue
            st_info = calculate_effective_status(root, cid, registry_row=row)
            eff = st_info['effective_status']

            # 대시보드 카테고리 매핑
            if eff in counts:
                counts[eff] += 1
            elif eff == 'RUNNING_UNKNOWN':
                counts['BLOCKED'] += 1
            elif eff == 'UNVERIFIED':
                reg_st = row.get('status', 'PLANNING')
                if reg_st in counts:
                    counts[reg_st] += 1
                else:
                    counts['PLANNING'] += 1
            else:
                counts['PLANNING'] += 1

    return counts
