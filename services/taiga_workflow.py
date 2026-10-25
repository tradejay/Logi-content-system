"""Inbound Taiga actions, separated from managed monitoring descriptions."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid
import yaml


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(value, encoding='utf-8')
    temp.replace(path)


class TaigaWorkflow:
    def __init__(self, root, client, db, project, statuses, stories, pipeline_factory=None):
        self.root, self.client, self.db = Path(root), client, db
        self.project, self.statuses, self.stories = project, statuses, stories
        if pipeline_factory is None:
            from services.content_pipeline import ContentPipeline
            pipeline_factory = ContentPipeline
        self.pipeline = pipeline_factory(root=self.root)
        db.execute('CREATE TABLE IF NOT EXISTS editors (source_key TEXT PRIMARY KEY, story_id INTEGER, base_sha TEXT, last_md TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS workflow_requests (request_id TEXT PRIMARY KEY, source_key TEXT, result TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS remote_snapshots (source_key TEXT PRIMARY KEY, description TEXT)')

    def record(self, task, request_id, result):
        self.db.execute('INSERT OR REPLACE INTO workflow_requests VALUES (?,?,?)',
                        (request_id, task['key'], json.dumps(result, ensure_ascii=False)))
        self.db.commit()
        path = self.root / 'content-system/operations/taiga-actions' / (request_id + '.json')
        write(path, json.dumps({'source_key': task['key'], 'at': datetime.now(timezone.utc).isoformat(),
                              **result}, ensure_ascii=False, indent=2))

    def editor(self, task):
        cid = task['refs']['content_id']
        path = self.pipeline.draft_path(cid)
        if not path.is_file():
            return
        current = path.read_text(encoding='utf-8')
        row = self.db.execute('SELECT story_id,base_sha,last_md FROM editors WHERE source_key=?', (task['key'],)).fetchone()
        subject = '[원고 편집] ' + cid
        if not row:
            found = next((s for s in self.stories if s.get('subject') == subject), None)
            story = found or self.client.request('POST', 'userstories', {
                'project': self.project['id'], 'subject': subject, 'description': current,
                'status': self.statuses[task['state']], 'tags': ['원고편집', 'content-ops']})
            self.stories.append(story) if not found else None
            # Recovering an existing editor must not silently replace its text.
            baseline = story.get('description') or ''
            self.db.execute('INSERT INTO editors VALUES (?,?,?,?)', (task['key'], story['id'], sha(current), baseline))
            self.db.commit()
            row = (story['id'], sha(current), baseline)
        story = self.client.request('GET', 'userstories/' + str(row[0]))
        edited = story.get('description') or ''
        if edited != row[2]:
            request_id = sha(task['key'] + ':edit:' + str(story['version']) + edited)
            if not self.db.execute('SELECT 1 FROM workflow_requests WHERE request_id=?', (request_id,)).fetchone():
                try:
                    if sha(current) != row[1]:
                        raise ValueError('다른 작업이 원고를 변경했습니다. 편집 내용은 보존했으며 원본에는 적용하지 않았습니다.')
                    self.pipeline.save_edit(cid, edited, expected_sha256=row[1], source='taiga:' + str(story['id']))
                    self.db.execute('UPDATE editors SET base_sha=?,last_md=? WHERE source_key=?', (sha(edited), edited, task['key']))
                    self.record(task, request_id, {'status': '변경 검토', 'message': '원고 새 버전 저장·기존 승인 해제 완료. AI 재검토는 콘솔에서 실행하세요.'})
                    current = edited
                    task['state'] = '변경 검토'
                except ValueError as error:
                    self.record(task, request_id, {'status': '막힘', 'message': str(error)})
        elif sha(current) != row[1]:
            story = self.client.request('PATCH', 'userstories/' + str(story['id']),
                                        {'description': current, 'version': story['version']})
            self.db.execute('UPDATE editors SET base_sha=?,last_md=? WHERE source_key=?', (sha(current), current, task['key']))
            self.db.commit()
        if story['status'] != self.statuses[task['state']]:
            story = self.client.request('PATCH', 'userstories/' + str(story['id']),
                                        {'status': self.statuses[task['state']], 'version': story['version']})
        task['editor_url'] = self.client.base.removesuffix('/api/v1') + '/project/' + self.project['slug'] + '/us/' + str(story['ref'])

    def image_review(self, task, story):
        default = {'decision': 'pending', 'asset_id': (task['summary'].get('output') or {}).get('asset_id') or '',
                   'draft_sha256': task['refs'].get('draft_sha256'), 'review_note': '', 'public_url': ''}
        match = re.search(r'## 이미지 검토 입력\b.*?```json\s*(.*?)\s*```', story.get('description') or '', re.S)
        try:
            review = json.loads(match.group(1)) if match else default
            if not isinstance(review, dict):
                raise ValueError('Review input must be an object')
        except ValueError:
            task['workflow_note'] = '이미지 검토 입력 JSON 형식이 잘못되었습니다. 입력을 보존했습니다.'
            task['review_input_raw'] = match.group(1) if match else '{}'
            return
        task['review_input'] = review
        decision = review.get('decision')
        moved_done = story['status'] == self.statuses['완료'] and task['state'] != '완료'
        if decision == 'pending' and not moved_done:
            return
        request_id = sha(task['key'] + ':image:' + json.dumps(review, sort_keys=True) +
                         (':done-request' if decision == 'pending' and moved_done else ''))
        prior = self.db.execute('SELECT result FROM workflow_requests WHERE request_id=?', (request_id,)).fetchone()
        if prior:
            task['workflow_note'] = json.loads(prior[0])['message']
            return
        try:
            if decision not in {'approve', 'revise', 'reject'}:
                raise ValueError('완료 이동만으로 승인할 수 없습니다. 검토 입력의 decision과 review_note를 작성하세요.')
            if not str(review.get('review_note') or '').strip():
                raise ValueError('검토 의견(review_note)이 필요합니다.')
            self.apply_image(task, review)
            task['state'] = {'approve': '완료', 'revise': '수정 요청', 'reject': '반려'}[decision]
            message = '이미지 검토 결과 반영: ' + task['state']
            self.record(task, request_id, {'status': task['state'], 'message': message})
        except ValueError as error:
            message = str(error)
            self.record(task, request_id, {'status': '막힘', 'message': message})
        task['workflow_note'] = message

    def apply_image(self, task, review):
        return apply_asset_review(self.root, self.pipeline, task, review)

    def process(self, task, story):
        if task['category'] == '글':
            self.editor(task)
            if story['status'] == self.statuses['완료'] and task['state'] != '완료':
                request_id = sha(task['key'] + ':complete:' + str(story['version']))
                try:
                    self.pipeline.assert_publishable(task['refs']['content_id'])
                    task['state'] = '완료'
                    message = '최종 승인·현재 원고 검증 통과. 발행 준비 완료이며 자동 발행하지 않습니다.'
                except ValueError as error:
                    message = '완료 요청 보류: ' + str(error) + ' · 상세 콘솔에서 검토 및 최종 승인을 진행하세요.'
                self.record(task, request_id, {'status': task['state'], 'message': message})
                task['workflow_note'] = message
        elif task['category'] == '이미지':
            self.image_review(task, story)
        latest = self.db.execute('SELECT result FROM workflow_requests WHERE source_key=? ORDER BY rowid DESC LIMIT 1', (task['key'],)).fetchone()
        if latest and not task.get('workflow_note'):
            task['workflow_note'] = json.loads(latest[0])['message']

    def preserve_manual_description(self, task, story):
        saved = self.db.execute('SELECT description FROM remote_snapshots WHERE source_key=?', (task['key'],)).fetchone()
        actual = story.get('description') or ''
        if saved and actual != saved[0]:
            request_id = sha(task['key'] + ':description:' + str(story['version']))
            write(self.root / 'content-system/operations/taiga-actions/description-edits' / (request_id + '.md'), actual)
        elif not saved:
            write(self.root / 'content-system/operations/taiga-actions/initial-descriptions' / (sha(task['key']) + '.md'), actual)


def apply_asset_review(root, pipeline, task, review):
    from services.taiga_tracking import yaml_file
    queue_path = root / 'content-system/queue/asset.queue.yaml'
    queue_raw = queue_path.read_bytes()
    queue = yaml_file(queue_path)
    job = queue['jobs'][task['refs']['job_id']]
    cid = job['content_id']
    if review.get('draft_sha256') != job.get('draft_sha256'):
        raise ValueError('원고 hash와 검토 대상이 다릅니다. 최신 작업을 확인하세요.')
    current = pipeline.draft_path(cid).read_text(encoding='utf-8')
    # Existing queues can use raw-file SHA (CRLF); accept only current bytes/text.
    hashes = {sha(current), hashlib.sha256(pipeline.draft_path(cid).read_bytes()).hexdigest()}
    if job.get('draft_sha256') not in hashes:
        raise ValueError('이미지 생성 이후 원고가 변경되었습니다. 현재 문단 적합도를 다시 확인해야 합니다.')
    registry = root / 'content-system/assets' / cid / 'assets.yaml'
    registry_raw = registry.read_bytes()
    data = yaml_file(registry)
    asset = next((a for a in data.get('assets', []) if a.get('asset_id') == review.get('asset_id') and a.get('need_id') == job.get('need_id')), None)
    if not asset:
        raise ValueError('해당 Need에 등록된 이미지 후보를 선택하세요.')
    if review['decision'] == 'approve':
        public = review.get('public_url') or asset.get('public_url') or asset.get('url')
        if not isinstance(public, str) or not re.fullmatch(r'https://[^\s<>"\']+', public):
            raise ValueError('승인에는 공개 HTTPS 이미지 주소가 필요합니다. 로컬 미리보기만으로 승인하지 않습니다.')
        if not asset.get('source_ref') or not asset.get('origin_type'):
            raise ValueError('이미지 출처와 생성 유형이 필요합니다.')
        if asset.get('local_path') and asset.get('origin_type') == 'generated':
            image = (root / asset['local_path']).resolve()
            if not image.is_relative_to(root.resolve()) or not image.is_file() or hashlib.sha256(image.read_bytes()).hexdigest() != asset.get('sha256'):
                raise ValueError('등록 이미지 파일·hash 검증 실패')
        asset.update(public_url=public, review_status='approved', rights_status='approved', lifecycle_status='approved')
        job['status'] = 'completed'
    else:
        asset['review_status'] = 'rejected' if review['decision'] == 'reject' else 'candidate'
        job['status'] = 'rejected' if review['decision'] == 'reject' else 'revision_required'
    asset.update(reviewer=review.get('reviewer') or 'taiga', reviewed_at=datetime.now(timezone.utc).isoformat(), review_note=review['review_note'])
    job['review'] = review
    identity = task['refs']['job_id']
    for bucket in ('ready', 'review', 'blocked'):
        queue[bucket] = [i for i in queue.get(bucket, []) if i != identity]
    if review['decision'] == 'revise':
        queue.setdefault('ready', []).append(identity)
    if queue_path.read_bytes() != queue_raw or registry.read_bytes() != registry_raw:
        raise ValueError('이미지 작업 정보가 동시에 변경됐습니다. 다시 시도하세요.')
    # Preserve exact pre-change files for recovery; do not edit run history.
    backup = root / 'content-system/operations/taiga-actions/backups' / uuid.uuid4().hex
    write(backup / 'assets.yaml', registry_raw.decode('utf-8'))
    write(backup / 'asset.queue.yaml', queue_raw.decode('utf-8'))
    write(registry, yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    write(queue_path, yaml.safe_dump(queue, allow_unicode=True, sort_keys=False))

