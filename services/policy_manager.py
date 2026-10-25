"""Editable policy workspace; compile immutable, runtime-compatible guide releases.

Existing MD sources are imported once and never rewritten by this service.
Natural-language contradictions need explicit review; structured conflicts block build.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

STAGES = ('strategy', 'write', 'feedback', 'official')
KINDS = ('require', 'prohibit', 'permit', 'recommend', 'reference')
EVALUATORS = ('guidance', 'deterministic', 'pattern', 'semantic_review', 'human_review')
RELATION_TYPES = ('requires_context', 'depends_on', 'complements', 'exception_to',
                  'conflicts_with', 'overlaps_with', 'duplicate_of', 'supersedes')
REVIEW_STATUSES = ('unreviewed', 'needs_review', 'semantically_reviewed',
                   'relations_reviewed', 'retrieval_verified')
SUB_ASPECTS = ('alternatives', 'bundle', 'awareness', 'fit_conditions',
               'compatibility', 'evidence', 'product_links', 'placement')
EDIT_FIELDS = {'title', 'text', 'domain', 'level', 'kind', 'stages', 'tags', 'subject',
               'action', 'object', 'evaluator', 'severity', 'enabled', 'review_note', 'purpose',
               'applies_to_elements', 'condition', 'exception', 'intent', 'sub_aspects',
               'relations', 'semantic_review_status', 'unresolved_questions', 'authority_issuer',
               'lifecycle', 'element_scope_status', 'purpose_reason'}


class PolicyError(ValueError):
    pass


class PolicyConflict(PolicyError):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


class PolicyManager:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.authoring = self.root / 'content-system/02_writer_ai/authoring'
        self.directory = self.root / 'content-system/00_system/policy'
        self.workspace = self.directory / 'workspace.json'

    @contextmanager
    def lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / 'edit.lock'
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise PolicyConflict('다른 정책 작업이 진행 중입니다. 잠시 후 다시 시도하세요.')
        try:
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def ensure(self):
        if self.workspace.exists():
            return
        with self.lock():
            if self.workspace.exists():
                return
            rules = read(self.authoring / 'rules/registry.json')
            guides = read(self.authoring / 'guide-registry.json')
            docs, atoms = {}, []
            definitions = []
            for item in rules['rules']:
                definitions.append((item['id'], self.authoring / 'rules' / item['path'], item, 'rule'))
            for item in guides['guides']:
                definitions.append((item['id'], self.authoring / item['path'], item, 'guide'))
            for path in sorted((self.authoring / 'prompts').glob('*.md')):
                definitions.append(('PROMPT-' + path.stem.upper(), path,
                                    {'stages': [path.stem], 'description': path.stem}, 'prompt'))
            for doc_id, path, meta, kind in definitions:
                path = path.resolve()
                if not path.is_relative_to(self.root):
                    raise PolicyError('정책 원본 경로가 프로젝트 밖입니다.')
                body = path.read_text(encoding='utf-8-sig')
                # Preserve exact document layout; split paragraphs rather than lose code/tables.
                parts = re.split(r'(\n\s*\n)', body)
                slots = []
                line = 1
                for part in parts:
                    if not part.strip():
                        slots.append({'literal': part})
                    else:
                        pid = f'{doc_id}-P{len(slots):03d}'
                        reference = part.lstrip().startswith(('#', '```', '|', 'Version:', '문서 버전:'))
                        atom = {'id': pid, 'revision': 1, 'title': part.strip().splitlines()[0][:100],
                                'text': part, 'domain': 'images' if 'ASSET' in doc_id or 'IMAGE' in doc_id else kind,
                                'level': 'L2' if kind == 'rule' else 'L4',
                                'kind': 'reference' if reference else 'require',
                                'stages': [s for s in meta.get('stages', STAGES) if s in STAGES],
                                'tags': [], 'subject': '', 'action': '', 'object': '',
                                'evaluator': 'guidance', 'severity': meta.get('severity', 'review'),
                                'enabled': True, 'review_note': '', 'target': doc_id,
                                'source': {'path': str(path.relative_to(self.root)).replace('\\', '/'),
                                           'line': line, 'sha256': sha(body)},
                                'granularity': 'imported_block', 'updated_at': stamp()}
                        atoms.append(atom)
                        slots.append({'policy_id': pid})
                    line += part.count('\n')
                docs[doc_id] = {'path': str(path.relative_to(self.root)).replace('\\', '/'),
                                'kind': kind, 'sha256': sha(body), 'slots': slots}
            state = {'schema_version': 1, 'revision': 1, 'updated_at': stamp(), 'atoms': atoms,
                     'documents': docs, 'rule_registry': rules, 'guide_registry': guides,
                     'history': [], 'candidates': []}
            write(self.workspace, state)
            write(self.directory / 'history/workspace-000001.json', state)

    def load(self):
        self.ensure()
        return read(self.workspace)

    def public(self):
        from services.policy_elements import ELEMENTS
        state = self.load()
        pointer = self.authoring / 'releases/active_release.json'
        return {**state, 'active_release': read(pointer).get('active_release_id') if pointer.exists() else None,
                'stages': STAGES, 'kinds': KINDS, 'evaluators': EVALUATORS, 'article_elements': ELEMENTS,
                'relation_types': RELATION_TYPES, 'review_statuses': REVIEW_STATUSES, 'sub_aspects': SUB_ASPECTS}

    def check_revision(self, state, expected):
        if type(expected) is not int or state['revision'] != expected:
            raise PolicyConflict('정책이 다른 화면에서 변경됐습니다. 새로고침 후 다시 저장하세요.')

    def check_atom(self, atom):
        from services.policy_elements import ELEMENTS
        elements = atom.get('applies_to_elements', ['unassigned'])
        if not isinstance(elements, list) or not elements or any(not isinstance(e, str) or e not in ELEMENTS for e in elements) or len(elements) != len(set(elements)):
            raise PolicyError('적용할 글 구성 요소를 유효한 목록으로 선택하세요.')
        if 'all_content' in elements and len(elements) > 1:
            raise PolicyError('글 전체는 다른 구성 요소와 함께 선택하지 않습니다.')
        if atom.get('purpose', 'needs_review') not in ('template_design', 'runtime_guardrail', 'runtime_contract', 'reference', 'needs_review'):
            raise PolicyError('정책 용도가 잘못됐습니다.')
        for field in ('title', 'text', 'domain', 'subject', 'action', 'object', 'review_note'):
            if not isinstance(atom.get(field), str) or len(atom[field]) > 50000:
                raise PolicyError(f'{field}: 유효한 텍스트가 필요합니다.')
        if not atom['title'].strip() or not atom['text'].strip():
            raise PolicyError('제목과 정책 본문을 입력하세요.')
        if atom['kind'] not in KINDS or atom['level'] not in ('L1', 'L2', 'L3', 'L4'):
            raise PolicyError('정책 종류 또는 수준이 잘못됐습니다.')
        if atom['evaluator'] not in EVALUATORS or atom['severity'] not in ('blocking', 'review', 'warning'):
            raise PolicyError('판정 방식 또는 심각도가 잘못됐습니다.')
        if type(atom['enabled']) is not bool:
            raise PolicyError('enabled는 boolean이어야 합니다.')
        for field, allowed in [('stages', STAGES), ('tags', None)]:
            value = atom[field]
            if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
                raise PolicyError(f'{field}는 문자열 목록이어야 합니다.')
            if len(value) != len(set(value)) or (allowed and set(value) - set(allowed)):
                raise PolicyError(f'{field}에 중복 또는 지원하지 않는 값이 있습니다.')
        for field in ('condition', 'exception', 'intent', 'authority_issuer', 'purpose_reason'):
            val = atom.get(field, '')
            if not isinstance(val, str) or len(val) > 50000:
                raise PolicyError(f'{field}: 유효한 텍스트여야 합니다.')
        if atom.get('lifecycle', 'active') not in ('active', 'retired', 'draft'):
            raise PolicyError('lifecycle 상태가 잘못됐습니다.')
        if atom.get('semantic_review_status', 'needs_review') not in REVIEW_STATUSES:
            raise PolicyError('semantic_review_status가 잘못됐습니다.')
        sub_aspects = atom.get('sub_aspects', [])
        if not isinstance(sub_aspects, list) or any(not isinstance(s, str) or not s for s in sub_aspects):
            raise PolicyError('sub_aspects는 문자열 목록이어야 합니다.')
        unresolved = atom.get('unresolved_questions', [])
        if not isinstance(unresolved, list) or any(not isinstance(u, str) or not u for u in unresolved):
            raise PolicyError('unresolved_questions는 문자열 목록이어야 합니다.')
        relations = atom.get('relations', [])
        if not isinstance(relations, list):
            raise PolicyError('relations는 목록이어야 합니다.')
        for r in relations:
            if not isinstance(r, dict) or 'type' not in r or 'target_id' not in r:
                raise PolicyError('relation 항목에 type과 target_id가 필요합니다.')
            if r['type'] not in RELATION_TYPES:
                raise PolicyError(f"지원하지 않는 관계 유형입니다: {r['type']}")
            if not isinstance(r['target_id'], str) or not r['target_id'].strip():
                raise PolicyError('relation target_id는 유효한 문자열이어야 합니다.')
        if not atom['stages'] and atom['kind'] != 'reference':
            raise PolicyError('적용 단계를 하나 이상 선택하세요.')

    def save(self, pid, patch, expected):
        if not isinstance(patch, dict) or set(patch) - EDIT_FIELDS:
            raise PolicyError('지원하지 않는 정책 필드입니다.')
        self.ensure()
        with self.lock():
            state = read(self.workspace)
            self.check_revision(state, expected)
            old = next((a for a in state['atoms'] if a['id'] == pid), None)
            if old is None:
                raise PolicyError('정책을 찾을 수 없습니다.')
            atom = {**old, **patch}
            self.check_atom(atom)
            if old['target'] != 'GENERATED' and atom['stages'] != old['stages']:
                raise PolicyError('가져온 문서의 단계는 유지해야 합니다. 단계별 새 정책으로 분리하세요.')
            if all(old.get(k) == atom.get(k) for k in EDIT_FIELDS):
                return self.public()
            if not atom['review_note'].strip():
                raise PolicyError('변경 이유와 의미 검토 내용을 기록하세요.')
            atom.update(revision=old['revision'] + 1, updated_at=stamp())
            state['atoms'] = [atom if a['id'] == pid else a for a in state['atoms']]
            self.commit(state, {'policy_id': pid, 'before': old, 'after': atom})
        return self.public()

    def create(self, payload, expected):
        if not isinstance(payload, dict) or set(payload) - EDIT_FIELDS:
            raise PolicyError('지원하지 않는 정책 필드입니다.')
        self.ensure()
        with self.lock():
            state = read(self.workspace)
            self.check_revision(state, expected)
            atom = {'id': 'POL-' + uuid.uuid4().hex[:12].upper(), 'revision': 1,
                    'title': '', 'text': '', 'domain': 'content', 'level': 'L2', 'kind': 'require',
                    'stages': ['write', 'feedback'], 'tags': [], 'subject': '', 'action': '', 'object': '',
                    'evaluator': 'guidance', 'severity': 'review', 'enabled': True, 'review_note': '',
                    'target': 'GENERATED', 'source': {'path': 'policy-editor', 'line': 0},
                    'granularity': 'atomic', 'updated_at': stamp(), **payload}
            self.check_atom(atom)
            if not atom['review_note'].strip():
                raise PolicyError('제정 이유와 의미 검토 내용을 기록하세요.')
            state['atoms'].append(atom)
            self.commit(state, {'policy_id': atom['id'], 'before': None, 'after': atom})
        return self.public()

    def sync_collections(self, state):
        from services.policy_purposes import PURPOSES, LABELS
        col_dir = self.directory / 'collections'
        if not col_dir.exists():
            return
        for purpose in PURPOSES:
            selected = [a for a in state['atoms'] if not a.get('retired_by') and a.get('enabled') and a.get('purpose') == purpose]
            write(col_dir / f'{purpose}.json', {
                'workspace_revision': state['revision'],
                'purpose': purpose,
                'label': LABELS.get(purpose, purpose),
                'policies': selected
            })

    def commit(self, state, event):
        state['revision'] += 1
        state['updated_at'] = stamp()
        state['history'].append({**event, 'at': stamp(), 'workspace_revision': state['revision']})
        write(self.directory / f"history/workspace-{state['revision']:06d}.json", state)
        write(self.workspace, state)
        self.sync_collections(state)


    def split(self, pid, texts, expected, review_note):
        if not isinstance(texts, list) or len(texts) < 2 or len(texts) > 30 or any(
                not isinstance(t, str) or not t.strip() for t in texts):
            raise PolicyError('분리할 정책 본문을 2~30개 입력하세요.')
        if not isinstance(review_note, str) or not review_note.strip():
            raise PolicyError('분리 이유와 의미 보존 검토를 기록하세요.')
        self.ensure()
        with self.lock():
            state = read(self.workspace)
            self.check_revision(state, expected)
            old = next((a for a in state['atoms'] if a['id'] == pid), None)
            if not old or not old['enabled']:
                raise PolicyError('포함된 규범 정책만 분리할 수 있습니다.')
            children = []
            for text in texts:
                child = {**old, 'id': 'POL-' + uuid.uuid4().hex[:12].upper(), 'revision': 1,
                         'text': text, 'title': text.strip().splitlines()[0][:100],
                         'granularity': 'atomic', 'split_from': pid, 'review_note': review_note,
                         'updated_at': stamp()}
                self.check_atom(child)
                children.append(child)
            if old['target'] != 'GENERATED':
                slots = state['documents'][old['target']]['slots']
                index = next(i for i, slot in enumerate(slots) if slot.get('policy_id') == pid)
                replacement = []
                for child in children:
                    if replacement:
                        replacement.append({'literal': '\n\n'})
                    replacement.append({'policy_id': child['id']})
                slots[index:index + 1] = replacement
            retired = {**old, 'enabled': False, 'revision': old['revision'] + 1,
                       'review_note': review_note, 'updated_at': stamp()}
            state['atoms'] = [retired if a['id'] == pid else a for a in state['atoms']] + children
            self.commit(state, {'policy_id': pid, 'before': old, 'after': retired,
                                'split_into': [c['id'] for c in children]})
        return self.public()

    def validate(self, state):
        conflicts, warnings = [], []
        enabled = [a for a in state['atoms'] if a['enabled'] and a['kind'] != 'reference']
        all_atom_ids = {a['id'] for a in state['atoms']}
        for a in state['atoms']:
            if not a.get('enabled'):
                continue
            for r in a.get('relations', []):
                tid = r.get('target_id')
                if tid and tid not in all_atom_ids and not tid.startswith(('RULE-', 'GUIDE-', 'DRAFT-')):
                    warnings.append({'id': a['id'], 'detail': f"알 수 없는 정책 ID 참조: {tid}"})
                if tid == a['id']:
                    conflicts.append({'ids': [a['id']], 'detail': '자기 자신과의 관계를 정의할 수 없습니다.'})
        for a in enabled:
            self.check_atom(a)
            if not all(a[k].strip() for k in ('subject', 'action', 'object')):
                warnings.append({'id': a['id'], 'detail': '행위 구조 미분류: 자연어 의미 검토 필요'})
            if a['evaluator'] not in ('guidance', 'semantic_review', 'human_review'):
                conflicts.append({'ids': [a['id']], 'detail': '이 편집기에는 새 자동 검사기 연결이 없습니다. 기존 코드 검사와 별도로 판정 방식을 선택하세요.'})
        for i, a in enumerate(enabled):
            if not all(a[k].strip() for k in ('subject', 'action', 'object')):
                continue
            for b in enabled[i + 1:]:
                if (a['subject'], a['action'], a['object']) != (b['subject'], b['action'], b['object']):
                    continue
                if not set(a['stages']) & set(b['stages']):
                    continue
                if 'prohibit' in (a['kind'], b['kind']) and ({a['kind'], b['kind']} & {'require', 'permit'}):
                    conflicts.append({'ids': [a['id'], b['id']], 'detail': '같은 단계·대상·행위에 금지와 의무/허용이 함께 있습니다.'})
        for doc in state['documents'].values():
            path = self.root / doc['path']
            if not path.exists() or sha(path.read_text(encoding='utf-8-sig')) != doc['sha256']:
                conflicts.append({'ids': [], 'detail': f"가져온 원본이 변경됐습니다: {doc['path']}. 편집기 원본과 수동 변경을 먼저 대조하세요."})
        # Prompt response fields must remain compatible with the current parser.
        assembled = self.assemble(state)
        required = {'write': {'markdown', 'claims', 'changes', 'used_asset_need_ids', 'unresolved_items'},
                    'feedback': {'passed', 'issues', 'missing_claims'}}
        for stage, fields in required.items():
            text = assembled[f'content-system/02_writer_ai/authoring/prompts/{stage}.md']
            contract = re.search(r'JSON 객체(?:만 반환한다)?\s*:\s*([^\n.]+)', text)
            names = set(re.findall(r'\b([a-z_]+)\s*\(', contract.group(1))) if contract else set()
            if names != fields:
                conflicts.append({'ids': ['PROMPT-' + stage.upper()],
                                  'detail': '응답 필드 계약 변경은 파이프라인 코드 수정이 필요합니다.'})
        return {'valid': not conflicts, 'conflicts': conflicts, 'warnings': warnings,
                'semantic_complete': False, 'detail': '구조화된 모순 검사입니다. 자연어 전체의 무충돌을 보장하지 않습니다.'}

    def assemble(self, state):
        atoms = {a['id']: a for a in state['atoms']}
        files = {}
        for doc in state['documents'].values():
            files[doc['path']] = ''.join(slot.get('literal', '') if 'literal' in slot else
                                        (atoms[slot['policy_id']]['text'] if atoms[slot['policy_id']]['enabled'] else '')
                                        for slot in doc['slots'])
        added = [a for a in state['atoms'] if a['enabled'] and a['target'] == 'GENERATED']
        for stage in STAGES:
            relevant = [a for a in added if stage in a['stages']]
            if relevant:
                path = f'content-system/02_writer_ai/authoring/prompts/{stage}.md'
                files[path] += '\n\n# 편집기에서 승인한 추가 정책\n' + '\n\n'.join(
                    f"## {a['id']}@{a['revision']} — {a['title']}\n[{a['level']} / {a['kind']}]\n{a['text']}" for a in relevant)
        return files

    def preview(self):
        state = self.load()
        files = self.assemble(state)
        changed = [e['policy_id'] for e in state['history']]
        return {'revision': state['revision'], 'validation': self.validate(state),
                'documents': files, 'changed_policy_ids': sorted(set(changed)),
                'mode': 'observe', 'detail': '문서 조립 미리보기이며 외부 AI 호출·원고 수정·발행은 없습니다.'}

    def build(self, expected, reviewer, review_note):
        if not isinstance(reviewer, str) or not reviewer.strip() or not isinstance(review_note, str) or not review_note.strip():
            raise PolicyError('검토자와 자연어 정합성 검토 내용을 입력하세요.')
        self.ensure()
        from services.guide_repository import GuideRepository, digest_str, get_code_revision
        with self.lock():
            state = read(self.workspace)
            self.check_revision(state, expected)
            report = self.validate(state)
            if not report['valid']:
                raise PolicyConflict('충돌 또는 원본 변경을 해결한 뒤 후보를 생성하세요.')
            release_id = 'rel_policy_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:8]
            staging = Path(tempfile.mkdtemp(prefix='compile-', dir=self.directory))
            try:
                for path, text in self.assemble(state).items():
                    target = staging / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(text, encoding='utf-8')
                authoring = staging / 'content-system/02_writer_ai/authoring'
                write(authoring / 'rules/registry.json', state['rule_registry'])
                write(authoring / 'guide-registry.json', state['guide_registry'])
                staged_repo = GuideRepository(staging)
                manifest = staged_repo.build_release(release_id=release_id)
                rel = staged_repo.releases_dir / release_id
                snapshot = {'schema_version': 1, 'workspace_revision': state['revision'],
                            'atoms': state['atoms'], 'reviewer': reviewer.strip(), 'review_note': review_note.strip(),
                            'validation': report, 'reviewed_at': stamp()}
                # Include provenance in the existing bundle hash and integrity verifier.
                write(rel / 'prompts/policy-snapshot.json', snapshot)
                manifest.prompts['policy-snapshot.json'] = {'name': 'policy-snapshot.json',
                    'path': 'prompts/policy-snapshot.json',
                    'sha256': digest_str((rel / 'prompts/policy-snapshot.json').read_text(encoding='utf-8-sig'))}
                manifest.code_revision = get_code_revision(self.root)
                manifest.bundle_sha256 = staged_repo.compute_bundle_hash(release_id, manifest.rules, manifest.guides,
                    manifest.prompts, manifest.dependencies, manifest.code_revision)
                write(rel / 'manifest.json', manifest.model_dump())
                staged_repo.verify_release(release_id)
                destination = self.authoring / 'releases' / release_id
                destination.parent.mkdir(parents=True, exist_ok=True)
                # Copy into ordinarily inherited project directories; don't persist
                # the private temporary staging directory's permissions as a release.
                publishing = destination.with_name(destination.name + '.building')
                try:
                    shutil.copytree(rel, publishing)
                    GuideRepository(self.root).verify_release(publishing.name)
                    publishing.rename(destination)
                finally:
                    if publishing.exists():
                        shutil.rmtree(publishing)
                record = {'release_id': release_id, 'workspace_revision': state['revision'],
                          'bundle_sha256': manifest.bundle_sha256, 'reviewer': reviewer.strip(), 'created_at': stamp()}
                state['candidates'].append(record)
                write(self.workspace, state)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        return record

    def activate(self, release_id, expected_active):
        self.ensure()
        from services.guide_repository import GuideRepository
        with self.lock():
            state = read(self.workspace)
            record = next((c for c in state['candidates'] if c['release_id'] == release_id), None)
            if not record:
                raise PolicyError('이 편집기에서 검토·생성한 후보만 활성화할 수 있습니다.')
            if record['workspace_revision'] != state['revision']:
                raise PolicyConflict('후보 생성 후 정책이 변경됐습니다. 현재 정책으로 다시 생성하세요.')
            repo = GuideRepository(self.root)
            if repo.get_active_release_id() != expected_active:
                raise PolicyConflict('활성 릴리스가 변경됐습니다. 새로고침 후 확인하세요.')
            if not self.validate(state)['valid']:
                raise PolicyConflict('현재 정책 검증을 통과하지 못했습니다.')
            repo.activate_release(release_id)
            write(self.directory / 'activations' / f'{uuid.uuid4().hex}.json',
                  {'release_id': release_id, 'previous': expected_active, 'at': stamp(), 'reviewer': record['reviewer']})
        return {'active_release_id': release_id}
