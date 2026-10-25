"""Apply the requested prose revision without publishing unrelated workspace edits."""
import copy
import json
import shutil
import uuid
from pathlib import Path

from services.policy_manager import PolicyManager, sha, stamp, write
from services.guide_repository import GuideRepository, canonical_json_hash


def main():
    root = Path(__file__).resolve().parent.parent
    manager, repo = PolicyManager(root), GuideRepository(root)
    previous = repo.get_active_release_id()
    old_manifest = repo.verify_release(previous).model_dump()
    rule_id = 'RULE-READER-STYLE'
    additions = [
        ('SHORT-REFERENCE', '재지칭 간결화', '같은 문단이나 바로 앞 문단에서 충분히 설명한 대상·행동은 다시 길게 정의하지 않고 짧은 명칭이나 동사로 이어 쓴다. 지칭 대상이 분명하면 “이 조정”, “끝자리 참석자”처럼 줄인다.', 'shorten_established_references', 'established_references', '대상·행동이 앞 문맥에서 충분히 설명되어 지칭이 명확할 때'),
        ('IMPLICIT-MODIFIER', '자명한 수식어 생략', '앞 문맥으로 이미 알 수 있고 삭제해도 대상·위치·행동이 달라지지 않는 수식어는 생략한다. 회의실 테이블을 설명한 직후의 “테이블 양쪽 끝에 앉은 참석자”는 “양쪽 끝 참석자”로 줄일 수 있다.', 'omit_redundant_modifiers', 'contextually_obvious_modifiers', '수식어를 생략해도 문맥상 의미와 대상이 유지될 때'),
        ('DIRECT-ACTION', '동작을 직접 표현', '이미 설명한 동작을 “이러한 물리적 좌석 재배치 조치” 같은 추상 명사구로 다시 묶지 않는다. “좌석을 이렇게 옮기면”처럼 동사로 이어 쓴다.', 'use_direct_verbs', 'repeated_action_nominalizations', '앞서 설명한 동작을 다음 문장으로 이어 갈 때'),
        ('PRESERVE-PRECISION', '축약의 정확성 경계', '축약 후 지칭 대상이나 작업 방향이 모호해지면 필요한 명칭·방향을 남긴다. 처음 소개하는 제품·기능의 정의, 모델 구분, 지원 조건, 경고, 근거 있는 수치는 보존한다. “뒤로”가 불분명하면 “카메라에서 멀어지도록”처럼 행동에 필요한 방향만 명시한다.', 'preserve_precision_when_shortening', 'essential_definitions_and_conditions', '문장을 축약할 때'),
        ('SUBSTANTIVE-LENGTH', '새 정보로 분량 확보', '글의 분량은 새로운 설명·근거·예시·판단 기준으로 확보한다. 이미 설명한 대상을 다시 길게 부르거나 같은 조치를 되풀이해 분량을 늘리지 않는다. 요약·체크리스트에는 판단과 실행에 필요한 핵심만 다시 제시한다.', 'use_substantive_information_for_length', 'article_length', '본문 분량을 확보하거나 요약·체크리스트를 작성할 때'),
        ('REVIEW-REFERENCE', '앞뒤 문맥을 읽는 문체 검토', '편집 검토에서 각 문장과 앞 문단을 함께 읽고, 재지칭·자명한 수식어·추상 명사구의 반복을 확인한다. 발견하면 원문 인용·위치·간결한 대안·보존할 조건을 피드백으로 남긴다. 단어 반복 횟수만으로 판정하거나, 다른 제품·조건을 구분하는 필수 명칭을 지우지 않는다.', 'review_contextual_redundancy', 'draft_sentences', '자체 검토·재작성에서 문체를 점검할 때'),
    ]
    with manager.lock():
        state = manager.load()
        before = manager.assemble(state)
        style_path = state['documents'][rule_id]['path']
        old_style = (repo.releases_dir / previous / 'rules' / old_manifest['rules'][rule_id]['filename']).read_text(encoding='utf-8-sig')
        assert before[style_path] == old_style, 'Active and workspace style differ; review before applying'
        assert not any(a['id'].startswith(rule_id + '-SHORT-REFERENCE') for a in state['atoms'])
        base = next(a for a in state['atoms'] if a['id'] == rule_id + '-V2N0004')
        new_ids = []
        def atom(pid, title, text, action, obj, condition, target=rule_id):
            item = {**copy.deepcopy(base), 'id': pid, 'revision': 1, 'title': title, 'text': text,
                    'target': target, 'subject': 'editor_ai' if action.startswith('review_') else 'writer_ai',
                    'action': action, 'object': obj, 'condition': condition, 'exception': '',
                    'intent': title, 'kind': 'require', 'stages': ['write', 'feedback'],
                    'tags': ['reader_style', 'conciseness', 'reference_expression'],
                    'applies_to_elements': ['all_content'], 'evaluator': 'semantic_review',
                    'purpose': 'runtime_guardrail', 'purpose_reason': '문맥상 중복 설명을 줄이는 집필·편집 기준',
                    'semantic_review_status': 'semantically_reviewed', 'element_scope_status': 'semantically_reviewed',
                    'relations': [], 'unresolved_questions': [], 'lifecycle': 'active',
                    'authority_issuer': 'user', 'updated_at': stamp(), 'granularity': 'atomic',
                    'review_note': '2026-10-08 사용자 문체 수정 요청; 의미·지원 조건 보존',
                    'source': {'path': 'audit/2026-10-08-concise-reference-style.md', 'line': 1, 'sha256': 'user-request'}}
            manager.check_atom(item)
            state['atoms'].append(item)
            return item
        slots = state['documents'][rule_id]['slots']
        slots.append({'literal': '\n\n## 문맥을 이어 쓰는 간결한 표현\n\n'})
        for suffix, title, text, action, obj, condition in additions:
            pid = rule_id + '-' + suffix
            atom(pid, title, text, action, obj, condition)
            new_ids.append(pid)
            slots.extend([{'policy_id': pid}, {'literal': '\n\n'}])
        version = next(a for a in state['atoms'] if a['id'] == rule_id + '-V2N0002')
        version.update(text=version['text'].replace('1.2.0', '1.3.0'), revision=version['revision'] + 1, updated_at=stamp())
        registry = next(r for r in state['rule_registry']['rules'] if r['id'] == rule_id)
        registry.update(version='1.3.0', change_note='2026-10-08 문맥상 중복 재지칭·수식어·추상 명사구 축약과 편집 검토')

        # Reconcile the two already-existing runtime additions, without changing their text.
        runtime_id = 'GUIDE-08-RUNTIME'
        runtime_doc = state['documents'][runtime_id]
        actual_runtime = (root / runtime_doc['path']).read_text(encoding='utf-8-sig')
        old_runtime = before[runtime_doc['path']]
        heading, remainder = old_runtime.split('\n', 1)
        assert actual_runtime.startswith(heading + '\n') and actual_runtime.endswith(remainder)
        inserted = actual_runtime[len(heading) + 1:len(actual_runtime) - len(remainder)]
        assert 'SYS-PIPELINE-VERIFY-005' in inserted and 'SYS-WEB-PLANNING-004' in inserted
        first = runtime_doc['slots'][0]
        assert 'policy_id' in first and heading in next(a['text'] for a in state['atoms'] if a['id'] == first['policy_id'])
        # Existing source text is provenance, not a new policy change in this release.
        runtime_doc['slots'].insert(1, {'literal': inserted})
        runtime_doc['sha256'] = sha(actual_runtime)
        assert manager.assemble(state)[runtime_doc['path']] == actual_runtime
        validation = manager.validate(state)
        assert validation['valid'], validation
        manager.commit(state, {'policy_id': rule_id, 'before': {'version': '1.2.0'},
                              'after': {'version': '1.3.0', 'added_policy_ids': new_ids,
                                        'runtime_source_reconciled': True}})

        # Keep every other active document byte-identical; do not publish pending workspace policies.
        release_id = 'rel_style_20261008_' + uuid.uuid4().hex[:8]
        destination = repo.releases_dir / release_id
        shutil.copytree(repo.releases_dir / previous, destination)
        manifest = copy.deepcopy(old_manifest)
        style = manager.assemble(state)[style_path]
        target = destination / 'rules' / manifest['rules'][rule_id]['filename']
        target.write_text(style, encoding='utf-8-sig')
        meta = manifest['rules'][rule_id]
        meta.update(version='1.3.0', change_note=registry['change_note'], sha256=sha(style))
        meta['meta_sha256'] = canonical_json_hash(meta, {'sha256', 'meta_sha256'})
        manifest.update(release_id=release_id, created_at=stamp(), eval_report_ref='audit/2026-10-08-concise-reference-style.md')
        # The active bundle had no atom snapshot. Record this amendment without implying all pending atoms were published.
        amendment_path = destination / 'prompts/style-amendment.json'
        write(amendment_path, {'workspace_revision': state['revision'], 'previous_release': previous,
                               'rule_id': rule_id, 'policy_ids': new_ids,
                               'atoms': [a for a in state['atoms'] if a['id'] in new_ids]})
        manifest['prompts']['style-amendment.json'] = {'name': 'style-amendment.json', 'path': 'prompts/style-amendment.json',
                                                     'sha256': sha(amendment_path.read_text(encoding='utf-8-sig'))}
        manifest['bundle_sha256'] = repo.compute_bundle_hash(release_id, manifest['rules'], manifest['guides'],
                                                           manifest['prompts'], manifest['dependencies'], manifest['code_revision'])
        write(destination / 'manifest.json', manifest)
        repo.verify_release(release_id)
        for kind in ('rules', 'guides', 'prompts'):
            for key, entry in old_manifest[kind].items():
                if kind == 'rules' and key == rule_id:
                    continue
                relative = entry.get('path') if kind == 'prompts' else kind + '/' + entry['filename']
                assert (destination / relative).read_bytes() == (repo.releases_dir / previous / relative).read_bytes()
        state['candidates'].append({'release_id': release_id, 'workspace_revision': state['revision'],
                                    'bundle_sha256': manifest['bundle_sha256'], 'reviewer': 'Codex / user-authorized style update',
                                    'created_at': stamp(), 'scope': [rule_id]})
        write(manager.workspace, state)
    manager.activate(release_id, previous)
    config_path = root / 'config/config.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    assert config.get('pipeline_input_token_budget') == 50000
    result = {'previous_release': previous, 'active_release': release_id, 'workspace_revision': state['revision'],
              'input_token_budget': 50000, 'rule_version': '1.3.0', 'added_policy_ids': new_ids,
              'validation': validation, 'unrelated_active_documents': 'byte_identical',
              'api_calls': 0}
    write(root / 'audit/2026-10-08-concise-reference-style.json', result)
    # Authoring MD is the imported original; expose the editable compiled guide separately.
    (root / 'audit/2026-10-08-reader-style-compiled.md').write_text(style, encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
