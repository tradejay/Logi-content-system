"""Retire topic-design samples while preserving the six operational articles."""
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEEP = {f'CNT-2026W39-{i:03}' for i in range(1, 6)} | {'CNT-LIVE-20261008-VERIFY-001'}


def main():
    registry = ROOT / 'content-system/registry/CONTENT_REGISTRY.csv'
    with registry.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    if {r['content_id'] for r in rows} - KEEP - {'CNT-2026W39-999'}:
        raise ValueError('Unexpected content records; refusing broad cleanup')
    assert {r['content_id'] for r in rows if r['content_id'] in KEEP} == KEEP
    archive = ROOT / 'archive/topic-tests' / datetime.now().strftime('%Y%m%dT%H%M%S')
    archive.mkdir(parents=True)
    shutil.copy2(registry, archive / 'CONTENT_REGISTRY.before.csv')
    targets = [
        'audit/2026-10-06-template-topic-candidates',
        'static/article-topic-data.js',
    ]
    for name in ('topic-bindings.json', 'article-plans.json', 'article-plans.md'):
        targets.append('content-system/00_system/templates/articles/' + name)
    moved = []
    for relative in targets:
        source = (ROOT / relative).resolve()
        if not source.is_relative_to(ROOT.resolve()):
            raise ValueError('Path outside workspace')
        if source.exists():
            destination = archive / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            moved.append(relative)
    template = ROOT / 'content-system/00_system/templates/articles'
    (template / 'topic-bindings.json').write_text(json.dumps({'bindings': []}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (template / 'article-plans.json').write_text(json.dumps({'version': '1.2.0', 'plans': []}, indent=2) + '\n', encoding='utf-8')
    (template / 'article-plans.md').write_text('# 주제별 테스트 계획 정리 완료\n\n20개 테스트 주제는 운영 목록에서 제거했습니다. 운영 원고는 CONTENT_REGISTRY.csv의 6개 항목을 사용합니다.\n', encoding='utf-8')
    with registry.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(r for r in rows if r['content_id'] in KEEP)
    (ROOT / 'static/article-topic-data.js').write_text('window.topicArticleDrafts = [];\n', encoding='utf-8')
    (ROOT / 'static/article-topic-samples.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>테스트 주제 정리 완료</title><h1>테스트 주제 정리 완료</h1><p>20개 테스트 주제는 운영 목록에서 제거했습니다.</p><p><a href="http://127.0.0.1:9000/project/beulrogeu-kontenceu-unyeong/wiki/beulrogeu-geul-mogrog">운영 블로그 글 6개 보기</a></p></html>''', encoding='utf-8')
    result = {'retained': sorted(KEEP), 'removed_registry_ids': [r['content_id'] for r in rows if r['content_id'] not in KEEP], 'archived': moved, 'archive': str(archive)}
    (archive / 'cleanup.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
