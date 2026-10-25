"""Score saved predictions only after explicit per-item human labels exist."""
import argparse
import csv
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.evaluation_manifest import verify_labels, seal_labels
from services.official_review_contract import validate_claim_verdicts


def score(folder, labels_file):
    manifest = verify_labels(folder, labels_file)
    with labels_file.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    predictions = json.loads((folder / 'parsed.json').read_text(encoding='utf-8'))['claims']
    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
    validate_claim_verdicts({'claims': predictions}, request['context']['claims'])
    predicted = {p['id']: p['verdict'] for p in predictions}
    labels = ['confirmed', 'contradicted', 'insufficient_evidence']
    if (len(rows) != len(predictions) or len({r['id'] for r in rows}) != len(rows)
            or {r['id'] for r in rows} != set(predicted)
            or any(r.get('human_label') not in labels or not r.get('reviewer', '').strip() for r in rows)):
        raise ValueError('Every ID requires one human label and named reviewer; no AI label fallback')
    results = {}
    for split in ('all', 'development', 'holdout'):
        selected = [r for r in rows if split == 'all' or r['split'] == split]
        matrix = {label: {p: 0 for p in labels + ['out_of_scope']} for label in labels}
        for row in selected:
            matrix[row['human_label']][predicted[row['id']]] += 1
        per_class = {}
        for label in labels:
            tp = matrix[label][label]
            actual = sum(matrix[label].values())
            predicted_count = sum(matrix[gold][label] for gold in labels)
            precision = tp / predicted_count if predicted_count else 0
            recall = tp / actual if actual else 0
            per_class[label] = {'precision': precision, 'recall': recall, 'support': actual,
                                'f1': 2*precision*recall/(precision+recall) if precision+recall else 0}
        results[split] = {'n': len(selected), 'confusion_matrix': matrix,
                          'accuracy': sum(matrix[x][x] for x in labels)/len(selected) if selected else None,
                          'per_class': per_class,
                          'macro_f1': sum(x['f1'] for x in per_class.values())/len(labels),
                          'false_rejection': matrix['confirmed']['contradicted'],
                          'missed_error': matrix['contradicted']['confirmed'],
                          'unnecessary_hold': matrix['confirmed']['insufficient_evidence']}
    results['input_manifest'] = manifest
    (folder / 'human-scored-metrics.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    parser.add_argument('--human-labels', type=Path, required=True)
    parser.add_argument('--seal-labels', action='store_true', help='Seal one reviewed label revision before scoring')
    args = parser.parse_args()
    if args.seal_labels:
        seal_labels(args.folder, args.human_labels)
    score(args.folder, args.human_labels)
