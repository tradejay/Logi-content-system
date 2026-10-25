"""Local immutable input bindings for an evaluation and its human-label revision."""
import hashlib
import json
from pathlib import Path


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def seal_run(folder, dataset=None):
    folder = Path(folder)
    manifest_path = folder / 'eval-manifest.json'
    if manifest_path.exists():
        verify_run(folder)
        return
    request = json.loads((folder / 'request.json').read_text(encoding='utf-8'))
    (folder / 'policy.snapshot.txt').write_text(request['instruction'], encoding='utf-8')
    split = {item['id']: item['split'] for item in dataset['items']} if dataset else {}
    save(folder / 'split.snapshot.json', split)
    files = ['request.json', 'response.txt', 'parsed.json', 'policy.snapshot.txt', 'split.snapshot.json']
    if (folder / 'draft.md').exists():
        files.append('draft.md')
    save(manifest_path, {'version': 'evaluation-manifest-v1',
                         'files': {name: digest_file(folder / name) for name in files}, 'labels': None})


def verify_run(folder):
    folder = Path(folder)
    manifest = json.loads((folder / 'eval-manifest.json').read_text(encoding='utf-8'))
    required = {'request.json', 'response.txt', 'parsed.json', 'policy.snapshot.txt', 'split.snapshot.json'}
    if manifest.get('version') != 'evaluation-manifest-v1' or not required <= set(manifest.get('files', {})):
        raise ValueError('Incomplete evaluation manifest')
    for name, digest in manifest['files'].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file() or digest_file(path) != digest:
            raise ValueError(f'Evaluation input version mismatch: {name}')
    return manifest


def seal_labels(folder, labels_file):
    folder, labels_file = Path(folder), Path(labels_file)
    manifest = verify_run(folder)
    if manifest.get('labels'):
        verify_labels(folder, labels_file)
        return
    import csv
    with labels_file.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    split = json.loads((folder / 'split.snapshot.json').read_text(encoding='utf-8'))
    claims = json.loads((folder / 'request.json').read_text(encoding='utf-8'))['context']['claims']
    expected = {c['id']: c for c in claims}
    allowed = {'confirmed', 'contradicted', 'insufficient_evidence'}
    if len(rows) != len(expected) or len({r['id'] for r in rows}) != len(rows) or {r['id'] for r in rows} != set(expected):
        raise ValueError('Human label ID coverage mismatch')
    for row in rows:
        if row.get('human_label') not in allowed or not row.get('reviewer', '').strip():
            raise ValueError('Complete human labels and reviewer required')
        if row.get('split') != split.get(row['id']):
            raise ValueError('Label split mismatch')
        if row.get('statement') != expected[row['id']]['statement']:
            raise ValueError('Label statement mismatch')
        for field in ('product', 'conditions', 'official_url', 'locator', 'property', 'quote'):
            if field in expected[row['id']] and row.get(field) != str(expected[row['id']][field]):
                raise ValueError(f'Label context mismatch: {field}')
    target = folder / 'labels.snapshot.csv'
    target.write_bytes(labels_file.read_bytes())
    manifest['labels'] = {'file': target.name, 'sha256': digest_file(target)}
    save(folder / 'eval-manifest.json', manifest)


def verify_labels(folder, labels_file):
    folder = Path(folder)
    manifest = verify_run(folder)
    binding = manifest.get('labels')
    if not binding:
        raise ValueError('Human labels not sealed; use --seal-labels after review')
    if digest_file(folder / binding['file']) != binding['sha256'] or digest_file(labels_file) != binding['sha256']:
        raise ValueError('Human label version mismatch; create a new evaluation revision')
    return manifest
