"""Human lifecycle position from stored verdicts, not the terminal 'finished' event."""
STAGE_NAMES = {1: '기획·자료 준비', 2: '집필', 3: '자체 검토', 4: '로지텍 검토',
               5: '이미지 제작·검토', 6: '최종 승인', 7: '발행 준비 완료', 8: '발행 완료'}
STAGE_ACTORS = {1: '기획·자료 AI', 2: '집필 AI', 3: '검토 AI·집필 AI',
                4: '로지텍 AI·피드백 판정 AI', 5: '이미지 작업 AI·관리자',
                6: '관리자', 7: '관리자', 8: '관리자·운영 시스템'}


def current_stage(result, details, registry_status=None):
    def at(number, reason):
        intervention = None
        if number == 3 and (result.get('manual_edit') or {}).get('requires_review'):
            intervention = '수정 내용 확인·재검토 실행'
        elif number in {1, 2, 3, 4} and result.get('outcome') in {'FAILED', 'ERROR', 'REVISION_REQUIRED', 'NEEDS_EVIDENCE'}:
            intervention = '중단 사유 확인·수정 방향 또는 근거 보완'
        elif number == 5 and reason == '이미지 승인 대기':
            intervention = '이미지 내용·출처 검토 및 승인'
        elif number == 6:
            intervention = '최종 원고·사진 승인'
        return {'number': number, 'name': STAGE_NAMES[number], 'reason': reason,
                'actors': STAGE_ACTORS[number], 'intervention_required': bool(intervention),
                'intervention': intervention or '현재 필수 개입 없음'}
    outcome = result.get('outcome')
    if (result.get('manual_edit') or {}).get('requires_review') and outcome == 'REVISION_REQUIRED':
        return at(3, '변경 원고 재검토 대기')
    if registry_status == 'PUBLISHED':
        return at(8, '발행 기록 있음')
    if outcome == 'COMPLETED_READY' and result.get('publish_ready'):
        return at(7, '최종 승인 완료')
    active = {'inputs': 1, 'strategy': 1, 'assets': 1, 'write': 2, 'naver_edit':2, 'feedback': 3,
              'official': 4, 'official_interpret': 4, 'image_generation': 5, 'publish_checks': 6}
    if outcome in {'RUNNING', 'CHECKING', 'FAILED', 'ERROR'} and result.get('stage') in active:
        return at(active[result['stage']], '실행 실패·조치 필요' if outcome in {'FAILED', 'ERROR'} else '진행 중')
    if not details.get('markdown'):
        return at(1, '자료 준비 또는 집필 실행 대기')
    qa = result.get('qa') or {}
    if qa.get('passed') is not True:
        return at(3, '수정 필요' if qa.get('passed') is False else '검토 기록 확인 필요')
    official = result.get('official_review') or {}
    if official.get('status') == 'RESPONSE_RECEIVED':
        return at(4, '로지텍 응답 수신 · Claim별 판정 대기')
    if official.get('status') != 'REVIEWED':
        return at(4, '공식 검토 대기')
    if not official.get('claims'):
        return at(4, '공식 검토 Claim별 판정 누락')
    if any(claim.get('verdict') != 'confirmed' for claim in official.get('claims', [])):
        return at(4, '근거 보완·수정 필요')
    bindings = details.get('asset_bindings') or []
    if any(not b.get('candidate') for b in bindings):
        return at(5, '이미지 확보 대기')
    if any(b.get('status') != 'approved' and (b.get('candidate') or {}).get('review_status') != 'approved' for b in bindings):
        return at(5, '이미지 승인 대기')
    return at(6, '최종 확인·승인 대기')
