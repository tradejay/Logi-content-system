"""Explicit live Logitech transport experiment; no Gemini or production state writes."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.pipeline_provider import ModelProvider, parse_object
from services.official_review_contract import validate_claim_verdicts

OUT = ROOT / 'audit/content-quality-eval-20261025'


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def evaluate_predictions(items, predicted):
    labels = ['confirmed', 'contradicted', 'insufficient_evidence']
    reviewed = all(i.get('human_label') in labels for i in items)
    by_id = {p['id']: p for p in predicted}
    matrix = {label: {other: 0 for other in labels + ['out_of_scope']} for label in labels}
    if reviewed:
        for item in items:
            actual = by_id[item['id']]['verdict']
            matrix[item['human_label']][actual] += 1
    return {'human_gold_available': reviewed, 'confusion_matrix': matrix if reviewed else None,
            'accuracy': sum(matrix[x][x] for x in labels) / len(items) if reviewed else None,
            'insufficient_evidence_rate': sum(p['verdict'] == 'insufficient_evidence' for p in predicted) / len(items),
            'prediction_count': len(predicted), 'labelled_count': sum(i.get('human_label') in labels for i in items)}


def run(kind):
    OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / (kind + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    folder.mkdir(exist_ok=False)
    instruction = (ROOT / 'content-system/02_writer_ai/authoring/prompts/official.md').read_text(encoding='utf-8')
    if kind == 'quality':
        data = json.loads((OUT / 'dataset.json').read_text(encoding='utf-8'))
        request = json.loads((OUT / 'request.json').read_text(encoding='utf-8'))
        instruction += '\n이번 시험에서는 제공한 근거만 사용하세요. 근거에 없으면 insufficient_evidence입니다. 정답표는 전달되지 않습니다.'
        claims = request['claims']
    else:
        from services.content_pipeline import ContentPipeline
        pipeline = ContentPipeline(ROOT)
        latest = pipeline.latest('CNT-2026W39-002')
        draft = pipeline.draft_path('CNT-2026W39-002').read_text(encoding='utf-8')
        claim_map = json.loads(Path(latest['claim_map_file']).read_text(encoding='utf-8'))
        claims = claim_map['claims']
        request = {'content_id': 'CNT-2026W39-002', 'draft': {'markdown': draft}, 'claims': claims}
        (folder / 'draft.md').write_text(draft, encoding='utf-8')
        save(folder / 'draft-identity.json', {'sha256': hashlib.sha256(draft.encode()).hexdigest(), 'source_run_id': latest['run_id']})
    save(folder / 'request.json', {'instruction': instruction, 'context': request})
    meta = {'kind': kind, 'started_at': datetime.now(timezone.utc).isoformat(),
            'request_sha256': hashlib.sha256((folder / 'request.json').read_bytes()).hexdigest(),
            'status': 'sent', 'claim_count': len(claims)}
    save(folder / 'status.json', meta)
    start = time.perf_counter()
    try:
        provider = ModelProvider(ROOT)
        if provider.config.get('logitech_ai_url', 'http://127.0.0.1:5050/ask') != 'http://127.0.0.1:5050/ask':
            raise ValueError('Only the explicitly authorized local Logitech relay is permitted')
        raw = provider.official(instruction, request)
        (folder / 'response.txt').write_text(raw, encoding='utf-8')
        meta.update(transport='success', elapsed_seconds=round(time.perf_counter()-start, 3))
        parsed = parse_object(raw)
        verdicts = validate_claim_verdicts(parsed, claims)
        save(folder / 'parsed.json', parsed)
        from services.evaluation_manifest import seal_run
        seal_run(folder, data if kind == 'quality' else None)
        meta.update(status='parsed', schema_compliance=1.0)
        if kind == 'quality':
            metrics = evaluate_predictions(data['items'], verdicts)
            metrics['human_review_approved'] = data['human_review']['approved']
            if not data['human_review']['approved']:
                metrics.update(accuracy=None, confusion_matrix=None)
            save(folder / 'metrics.json', metrics)
        else:
            save(folder / 'official-review.json', {'status': 'REVIEWED', 'claims': verdicts,
                 'draft_sha256': hashlib.sha256(draft.encode()).hexdigest(), 'raw_file': 'response.txt',
                 'note': 'Direct official structured output; IDE official_interpret stage not executed in this transport probe.'})
    except Exception as error:
        meta.update(status='failed', error_type=type(error).__name__, error=str(error)[:300],
                    elapsed_seconds=round(time.perf_counter()-start, 3))
    save(folder / 'status.json', meta)
    save(OUT / f'latest-{kind}.json', {'folder': folder.relative_to(ROOT).as_posix(), **meta})
    print(json.dumps({'folder': str(folder), **meta}, ensure_ascii=False))
    return 0 if meta['status'] == 'parsed' else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['quality', 'article'])
    raise SystemExit(run(parser.parse_args().kind))


if __name__ == '__main__':
    main()
