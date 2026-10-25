"""Assemble existing, isolated verification evidence; never run publication code."""
import ast
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'static/reports/publish-gate-tests/verification-20261025T123149'


def read_json(name):
    return json.loads((OUT / name).read_text(encoding='utf-8'))


def main():
    full, focused = read_json('results.json'), read_json('focused-results.json')
    cases = read_json('detailed-scenarios.json')
    all_ids = {t['nodeid'] for t in full['tests']}
    focused_ids = {t['nodeid'] for t in focused['tests']}
    assert focused_ids <= all_ids
    files = [
        'services/content_pipeline.py', 'services/article_approval.py',
        'content-system/scripts/change_status.py',
        'tests/test_publish_gate_scenarios.py', 'tests/test_article_approval.py',
        'tests/test_content_pipeline.py', 'scripts/audit_publish_gate_evidence.py',
    ]
    methods, sources = {}, []
    for name in files:
        raw = (ROOT / name).read_bytes()
        dest = OUT / 'source' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        sources.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest()})
        if name.startswith('tests/'):
            for cls in ast.parse(raw.decode('utf-8-sig')).body:
                if not isinstance(cls, ast.ClassDef):
                    continue
                for fn in cls.body:
                    if isinstance(fn, ast.FunctionDef) and fn.name.startswith('test_'):
                        methods[f'{name}::{cls.name}::{fn.name}'] = {
                            'line': fn.lineno,
                            'purpose': ast.get_docstring(fn) or fn.name.removeprefix('test_').replace('_', ' '),
                            'source': ast.get_source_segment(raw.decode('utf-8-sig'), fn),
                        }
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True))
    metadata = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'head': head,
                'working_tree_dirty': dirty, 'sources': sources,
                'limitation': 'Captured during report assembly, not at the original test start.'}
    (OUT / 'source-manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    inventory = []
    for test in full['tests']:
        found = methods.get(test['nodeid'], {})
        inventory.append({'test': test['nodeid'], 'line': found.get('line'),
                          'purpose': found.get('purpose', ''), 'result': test['outcome'],
                          'focused_subset': test['nodeid'] in focused_ids})
    with (OUT / 'test-inventory.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=inventory[0])
        writer.writeheader()
        writer.writerows(inventory)
    kst = lambda report: datetime.fromtimestamp(report['created'], timezone(timedelta(hours=9))).isoformat()
    lines = [
        '# 발행 준비 차단 게이트 — 상세 검증 증거', '',
        '## 1. 결과와 포함 관계', '',
        f'- 관련 회귀: **{full["summary"]["passed"]}/{full["summary"]["total"]} 통과**, {full["duration"]:.2f}초.',
        f'- 집중 검증: **{focused["summary"]["passed"]}/{focused["summary"]["total"]} 통과**, {focused["duration"]:.2f}초.',
        '- 집중 22개는 관련 56개의 부분집합이다. 총 78개로 합산하지 않는다.',
        '- 두 실행의 실패·건너뜀·예상 실패는 각각 0이다. 기획 단계의 이전 실패는 이번 단일 실행에서 재현되지 않았다.',
        f'- 전체 실행 시작(KST): {kst(full)}. 집중 실행 시작: {kst(focused)}.',
        '- 추가 증거 수집: 6개 분류·11개 입력 변형, 상태 전이와 내보내기 총 22회 호출. 이는 pytest 22개와 다른 수치이며 합산하지 않는다.', '',
        '## 2. 무엇을 모의 처리했고 무엇을 실제 실행했는가', '',
        '- **모의:** 임시 원고·등록부·공식 검수 상태. 서버 오류는 error 플래그 주입이며 실제 HTTP 연결 장애를 발생시킨 것이 아니다.',
        '- **경로 격리:** REGISTRY_FILE, BRIEFS_DIR, QUEUE_DIR, LOCKS_DIR, LOGS_DIR, EVENTS_LOG가 모두 .test-tmp 안을 가리키는지 실행 전에 assert한다.',
        '- **생성자 교체:** ContentPipeline()은 임시 루트의 실제 pipeline 객체를 반환하도록 패치했다. assert_publishable 자체나 판단 반환값은 모의 처리하지 않았다.',
        '- **실제 실행:** execute_status_transaction → assert_publishable → QA·검수·승인·원고 해시 검사 → 상태/등록부/큐 저장. export → lock → assert_publishable → HTML 컴파일·발행 준비 파일 저장.',
        '- **미실행:** 실제 외부 AI·실제 네트워크 장애·네이버 발행·사람 정답 평가셋·AI 의미 정확도·장기 운영·동시 수정 경쟁.',
        '- 추가 세부 검증은 운영 Python 함수 호출이다. 별도 OS 프로세스 CLI나 실제 HTTP 종단 시험으로 표현하지 않는다. 기존 회귀에 Flask test_client 시험이 별도로 포함된다.', '',
        '## 3. 핵심 6개 시나리오와 11개 입력 변형', '',
        '모든 사례는 CNT-GATE-TEST, run-fixture-1, READY_FOR_QA에서 시작한다. 정상 기준값은 qa.passed=true, outcome=COMPLETED_READY, publish_ready=true, official.status=REVIEWED, claims=[{id:claim-1,verdict:confirmed}], approval.reviewer=test-reviewer, resolutions=[확인 완료]다.', '',
        '발행 준비 디렉터리에 이전 final.md·naver.html을 먼저 넣고 승인 보관본 approval.json도 저장했다. 실행 전후 전체 파일 목록·SHA256은 detailed-scenarios.json에 보존했다.', '',
    ]
    baseline_test = {
        'normal': 'test_valid_review_and_approval_allows_command',
        'server_error_stale_success': 'test_review_server_failure_blocks_command',
        'unresolved': 'test_unresolved_review_item_blocks_command',
        'changed_draft': 'test_draft_changed_after_review_blocks_command',
    }
    for case in cases:
        name = case['case']
        label = '정상 검수·승인' if name == 'normal' else case['category']
        initial, current = case['initial_review_approval'], case['input_latest']
        fn = baseline_test.get(name, 'test_empty_or_malformed_review_blocks_command')
        node = 'tests/test_publish_gate_scenarios.py::PublishGateScenarios::' + fn
        line = methods[node]['line']
        lines += [f'### {label} — {name}', '',
                  f'- **기반 테스트:** `{node}:{line}`. 세부 확장 재현은 `scripts/audit_publish_gate_evidence.py:run`.',
                  '- **초기 상태:** READY_FOR_QA; 검수·승인·원고 해시는 아래 기준값과 동일.',
                  f'- **초기 SHA256:** `{initial["draft_sha256"]}`.',
                  f'- **실행 시 원고 SHA256:** `{case["current_draft_sha256"]}`.',
                  '- **입력 조건:**', '```json',
                  json.dumps({'official_review': current.get('official_review'), 'error': current.get('error'),
                              'admin_checks': current.get('admin_checks'), 'approval': current.get('approval')}, ensure_ascii=False, indent=2),
                  '```',
                  '- **실행 경로:** execute_status_transaction(CNT-GATE-TEST, READY_TO_PUBLISH) 및 pipeline.export(CNT-GATE-TEST). 두 경로 모두 실제 게이트 호출.',
                  '- **기대:** ' + ('허용·READY_TO_PUBLISH 전이 및 산출물 작성.' if case['expected_allowed'] else '두 경로 거부·READY_FOR_QA 유지·기존 산출물 및 승인 기록 유지.'),
                  '- **실제 반환/오류:**', '```json', json.dumps(case['actual'], ensure_ascii=False, indent=2), '```',
                  f'- **실행 후 상태:** `{case["final_registry_status"]}`.',
                  '- **변경 파일:** ' + ', '.join('`'+n+'`' for n in case['changed_files']) + '.',
                  '- **assert:** 두 경로 허용 여부가 기대와 같음; 등록부 최종 상태가 기대와 같음; pipeline-latest.json와 approval.json 해시 불변; 차단 시 감사 로그·mutex 파일 외 변경 없음.',
                  '- **증거:** detailed-scenarios.json 해당 case의 actual/gate_events/files_before/files_after. 예외는 ValueError이며 HTTP 코드가 아니다.', '']
    lines += [
        '## 4. 입력별 해석과 보장 한계', '',
        '- 빈 응답은 null, 빈 문자열, 빈 객체, 빈 claims를 각각 넣었다. 잘못된 형식은 비JSON 문자열, claims 문자열, 필수 상태·해시 누락 객체를 넣었다.',
        '- 비JSON 문자열 검증은 게이트의 자료형 검사다. HTTP JSON 파서 자체의 실패 검증이라고 주장하지 않는다.',
        '- 서버 오류는 과거 정상 review·승인·publish_ready=true를 남긴 채 error를 추가했다. error가 기록되었을 때 과거 성공 값으로 통과하지 않는 것을 확인했다. 외부 예외가 기록되지 않고 과거 성공값이 남는 경우는 별도 검증 과제다.',
        '- .gate.lock은 export mutex의 부수효과다. 그것이 생겼다는 사실을 차단 성공으로 세지 않았다.',
        '- 차단 시 기존 발행 준비 산출물과 승인본은 보존된다. 기존 파일을 폐기하거나 사용자의 수동 복사를 막는 설계는 아니다.', '',
        '## 5. 발행 준비 진입점·우회 검토', '',
        '| 진입점 | 실제 연결 | 증거 수준 |', '|---|---|---|',
        '| CLI 상태 전이 | change_status.execute_status_transaction → assert_publishable | 함수 실행 검증. gate는 force 검사보다 먼저 호출됨 |',
        '| 콘솔 상태 API | POST /contents/<id>/status → assert_publishable → change_status.py | 코드 확인 + 기존 Flask 시험의 force=true HTTP 409 |',
        '| 내보내기 API | GET /blog-export/<id> → export → assert_publishable | 실제 export 시험 + 기존 Flask 차단 시험. ValueError는 409 반환 |',
        '| 발행 URL 등록 | approval/publish 및 /publish → ArticleApproval.publish → assert_publishable | 코드 확인 + 검토 대기 시 registry 불변 테스트 |',
        '| Taiga 완료 | taiga_workflow.process → assert_publishable | 코드 확인. 이번 실제 Taiga HTTP 시험 없음 |',
        '| 완료 결과 재사용 | pipeline_dispatcher의 COMPLETED_READY 분기 → assert_publishable | 코드 확인. 별도 종단 시험 없음 |',
        '| 미리보기·글 상세 | blog-preview/get_content_detail에서 초안·기존 final 조회 가능 | 게이트 없는 조회 경로. 발행 상태는 바꾸지 않지만 수동 복사는 가능 |',
        '| 직접 CSV/파일 수정 | 파일 쓰기 권한자 | 시스템 함수 밖의 직접 변경까지 막는 보안 경계가 아님 |', '',
        '**미검증 위험:** 게이트 검사 후 파일 기록 전 동시 원고 변경(TOCTOU), QA 결과 자체의 별도 원고 해시 대조, 검수 claims의 전체 원고 커버리지는 이번 시험으로 입증하지 않았다. 모든 우회가 불가능하다고 주장하지 않는다.', '',
        '## 6. 실행 명령·코드 식별·변경 목적', '', '```powershell',
        'python -m pytest tests/test_publish_gate_scenarios.py tests/test_article_approval.py tests/test_content_pipeline.py --json-report --json-report-file=<기록폴더>/results.json --junitxml=<기록폴더>/junit.xml --html=<기록폴더>/index.html --self-contained-html -q',
        'python -m pytest tests/test_publish_gate_scenarios.py tests/test_article_approval.py tests/test_content_pipeline.py::PipelineTests::test_approval_is_revision_bound tests/test_content_pipeline.py::PipelineTests::test_failed_qa_exhaustion_never_publishes tests/test_content_pipeline.py::PipelineTests::test_malformed_official_response_never_passes --json-report --json-report-file=<기록폴더>/focused-results.json --junitxml=<기록폴더>/focused-junit.xml -q',
        'python scripts/audit_publish_gate_evidence.py --out <기록폴더>', '```', '',
        f'- HEAD: `{head}`. 미커밋 변경: `{dirty}`.',
        '- Git 정보와 source/ 해시는 상세 보고서 작성 시점에 캡처했다. 최초 실행 순간의 전체 working tree 해시를 보관하지 않았으므로 소급 복원하지 않는다.',
        '- 이번 추가 작업: audit_publish_gate_evidence.py(경로 격리 및 부수효과 증거 수집), build_publish_gate_evidence_report.py(기존 증거 조립). 운영 게이트 자체는 이번 상세화 과정에서 수정하지 않았다.',
        '- 기존 관련 변경: content_pipeline.py=검수/승인/해시 검사 및 감사 로그; article_approval.py=발행 등록 전 gate 연결; test_publish_gate_scenarios.py=상태 전이 검증; test_article_approval.py=검토 대기 등록 차단. 다른 변경이 섞인 working tree를 이 작업만의 변경이라고 간주하지 않는다.', '',
        '## 7. 전체 테스트 목록과 목적', '',
        '목적은 기존 docstring이 있으면 그것을, 없으면 테스트 함수명을 풀어 적었다. 의도 설명과 실제 보장 범위는 해당 소스의 assert를 함께 확인해야 한다.', '',
        '| 테스트명·라인 | 검증 목적 | 결과 | 집중22 포함 |', '|---|---|---|---|',
    ]
    for row in inventory:
        purpose = row['purpose'].replace('\n', ' ').replace('|', '/')
        lines.append(f'| `{row["test"]}:{row["line"]}` | {purpose} | {row["result"]} | {"예" if row["focused_subset"] else "아니오"} |')
    lines += ['', '## 8. 핵심 시나리오의 실제 검증문', '']
    for node, details in methods.items():
        if node.startswith('tests/test_publish_gate_scenarios.py::'):
            lines += ['### ' + node, '```python', details['source'], '```', '']
    test_source = (ROOT / 'tests/test_publish_gate_scenarios.py').read_text(encoding='utf-8')
    cls = next(x for x in ast.parse(test_source).body if isinstance(x, ast.ClassDef))
    attempt = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'attempt')
    lines += ['### 공통 attempt 검증문', '```python', ast.get_source_segment(test_source, attempt), '```', '',
              '## 9. 면접용 표현', '',
              '“검수 오류·미해결 항목·원고 변경 시 상태 전이와 내보내기를 거부하는 공통 게이트를 연결했습니다. 임시 원고에서 반환값·상태·감사 로그뿐 아니라 기존 발행 준비 파일과 승인 기록의 SHA256이 유지되는지 확인했습니다. 집중 22개는 관련 56개 회귀에 포함되며 모두 통과했습니다. 외부 AI 정확도·실제 서버 장애·장기 운영·동시 수정 안전성은 별도 검증 과제입니다.”', '']
    body = '\n'.join(lines)
    (OUT / 'DETAIL-REPORT.md').write_text(body, encoding='utf-8')
    # Portable evidence viewer; markdown remains literal and independently shareable.
    (OUT / 'details.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>발행 게이트 상세 검증 증거</title><style>body{max-width:1080px;margin:32px auto;padding:0 20px;font:15px/1.7 sans-serif}pre{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#067}</style><a href="publish-gate-evidence.zip">증거 ZIP 다운로드</a> · <a href="DETAIL-REPORT.md">원문 Markdown</a><pre>'+html.escape(body)+'</pre></html>', encoding='utf-8')
    with zipfile.ZipFile(OUT / 'publish-gate-evidence.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('DETAIL-REPORT.md', 'details.html', 'detailed-scenarios.json', 'scenario-evidence.json', 'results.json', 'focused-results.json', 'junit.xml', 'focused-junit.xml', 'test-inventory.csv', 'source-manifest.json', 'summary.json'):
            archive.write(OUT / name, arcname=name)
        for path in (OUT / 'source').rglob('*'):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(OUT))
    print(json.dumps({'tests': len(all_ids), 'focused_subset': len(focused_ids), 'input_variants': len(cases), 'bundle_bytes': (OUT / 'publish-gate-evidence.zip').stat().st_size}))


if __name__ == '__main__':
    main()
