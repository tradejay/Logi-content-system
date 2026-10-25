"""Package the five unpublished articles for an IDE-only fresh planning run."""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from services.pipeline_context import load_context

ROOT = Path(__file__).resolve().parents[1]


def main():
    with (ROOT / 'content-system/registry/CONTENT_REGISTRY.csv').open(encoding='utf-8-sig', newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if r['status'] != 'PUBLISHED']
    expected = {f'CNT-2026W39-{i:03}' for i in range(1, 6)}
    if {r['content_id'] for r in rows} != expected:
        raise ValueError('Expected exactly the five retained unpublished articles')
    batch = 'RERUN-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    directory = ROOT / 'worker-control/article-reruns' / batch
    directory.mkdir(parents=True)
    articles, sources, cautions = [], {}, {}
    for row in rows:
        context = load_context(ROOT, row['content_id'])
        articles.append({'content_id': row['content_id'], 'title': row['title'],
                         'brief': context['brief'], 'facts': context['facts'],
                         'product_links': context['product_links'], 'input_gaps': context['missing']})
        sources.update(context['sources'])
        cautions.update({r['id']: r for r in context['cautions']})
        (directory / (row['content_id'] + '.context.json')).write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = {'batch_id': batch, 'articles': articles,
               'already_published': {'content_id': 'CNT-LIVE-20261008-VERIFY-001', 'url': 'https://blog.naver.com/oceantech01/224440463862', 'title': '소형 회의실에서 양끝 참석자가 잘릴 때: 좌석 배치 점검과 MeetUp 2 선택 기준'},
               'source_records': sources, 'cautions': list(cautions.values())}
    (directory / 'planning-input.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    guide_paths = ['content-system/02_writer_ai/authoring/01-topic-and-keywords.md',
                   'content-system/02_writer_ai/authoring/03-opening-body-closing.md',
                   'content-system/02_writer_ai/authoring/rules/reader-and-style.md',
                   'content-system/00_system/rules/web-planning-discovery.md']
    (directory / 'planning-guide.md').write_text('\n\n'.join((ROOT / p).read_text(encoding='utf-8-sig') for p in guide_paths), encoding='utf-8')
    state = {'batch_id': batch, 'directory': directory.relative_to(ROOT).as_posix(), 'content_ids': sorted(expected), 'stage': 'planning_prepared', 'execution_type': 'ide', 'publication_approved': False}
    (directory / 'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT / 'worker-control/article-reruns/latest.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(state, ensure_ascii=False))


if __name__ == '__main__':
    main()
