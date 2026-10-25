"""Prepare reviewable labels; never represent AI-authored candidates as human gold."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'audit/content-quality-eval-20261025'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {
        'M2': {'product': 'MeetUp 2', 'url': 'https://www.logitech.com/content/dam/logitech/en_us/video-collaboration/pdf/meetup2-datasheet.pdf', 'locator': 'PDF page 3, Product Specifications', 'scope': 'US datasheet checked 2026-10-25; no universal firmware/version guarantee'},
        'RB': {'product': 'Rally Bar', 'url': 'https://www.logitech.com/content/dam/logitech/en_us/video-collaboration/pdf/rallybar.pdf', 'locator': 'PDF page 3; Published July 2025', 'scope': 'Standard Rally Bar; not Mini/Huddle or No-Radio variant'},
    }
    # Exact short excerpts total fewer than 25 quoted words per source.
    facts = [
        ('M2', 'package cable', '3 m', 'MeetUp 2 구성품의 USB 케이블 길이는 3m입니다.', 'MeetUp 2 구성품의 USB 케이블 길이는 9m입니다.', 'MeetUp 2 구성품 케이블은 1,000회 연결 후에도 성능을 보장합니다.'),
        ('M2', 'horizontal FOV', '113°', 'MeetUp 2의 수평 화각은 113도입니다.', 'MeetUp 2의 수평 화각은 130도입니다.', 'MeetUp 2의 저조도 인식률은 모든 환경에서 99%입니다.'),
        ('M2', 'vertical FOV', '80°', 'MeetUp 2의 수직 화각은 80도입니다.', 'MeetUp 2의 수직 화각은 50도입니다.', 'MeetUp 2는 모든 실내 조도에서 동일한 색 정확도를 보장합니다.'),
        ('M2', 'zoom', '4X HD digital zoom', 'MeetUp 2는 4배 HD 디지털 줌을 제공합니다.', 'MeetUp 2는 4배 광학 줌을 제공합니다.', 'MeetUp 2의 화자 전환 지연은 항상 100ms 이하입니다.'),
        ('M2', 'camera resolution', '4K', 'MeetUp 2의 카메라 해상도 사양은 4K입니다.', 'MeetUp 2의 카메라 해상도 사양은 8K입니다.', 'MeetUp 2를 도입하면 회의 생산성이 정확히 30% 향상됩니다.'),
        ('RB', 'microphone pickup', '7 m', 'Rally Bar 데이터시트의 마이크 수음 범위 표기는 7m입니다.', 'Rally Bar 데이터시트의 마이크 수음 범위 표기는 17m입니다.', 'Rally Bar는 7m 거리의 발화자 얼굴을 항상 정확히 추적합니다.'),
        ('RB', 'microphone elements', 'Six omnidirectional', 'Rally Bar에는 6개의 전방향 디지털 MEMS 마이크가 있습니다.', 'Rally Bar에는 8개의 전방향 디지털 MEMS 마이크가 있습니다.', 'Rally Bar의 화자 식별 정확도는 모든 방에서 99.9%입니다.'),
        ('RB', 'HDMI output', 'HDMI Out: 2', 'Rally Bar 데이터시트의 HDMI 출력 포트 수는 2개입니다.', 'Rally Bar 데이터시트의 HDMI 출력 포트 수는 3개입니다.', 'Rally Bar는 어떤 HDMI 디스플레이와도 호환성 문제가 없습니다.'),
        ('RB', 'HDMI input', 'HDMI In: 1', 'Rally Bar 데이터시트의 HDMI 입력 포트 수는 1개입니다.', 'Rally Bar 데이터시트의 HDMI 입력 포트 수는 2개입니다.', 'Rally Bar의 모든 펌웨어 버전은 HDMI 공유 지연이 20ms입니다.'),
        ('RB', 'microphone data rate output', '48 kHz', 'Rally Bar의 마이크 데이터 출력 샘플링 사양은 48kHz입니다.', 'Rally Bar의 마이크 데이터 출력 샘플링 사양은 96kHz입니다.', 'Rally Bar는 모든 회의실의 잔향을 완전히 제거합니다.'),
    ]
    items = []
    for idx, (sid, property_name, quote, correct, wrong, unknown) in enumerate(facts):
        source = sources[sid]
        for label, statement in [('confirmed', correct), ('contradicted', wrong), ('insufficient_evidence', unknown)]:
            blind_id = 'EVAL-' + hashlib.sha256(('blind-eval-v2:' + statement).encode()).hexdigest()[:12]
            items.append({'id': blind_id, 'fact_group': idx+1,
                          'split': 'development' if idx < 6 else 'holdout',
                          'statement': statement, 'suggested_label': label, 'human_label': None,
                          'product': source['product'], 'conditions': source['scope'],
                          'source_id': sid, 'official_url': source['url'], 'locator': source['locator'],
                          'property': property_name, 'quote': quote})
    random.Random(20261025).shuffle(items)
    dataset = {'version': 'candidate-v2-blind', 'created_at': datetime.now(timezone.utc).isoformat(),
               'human_review': {'approved': False, 'reviewer': None},
               'evaluation_policy': 'Use only the supplied official excerpt. Missing support means insufficient_evidence, not contradicted. AI labels are proposals, not human ground truth. Split by fact group.',
               'sources': sources, 'items': items}
    path = OUT / 'dataset.json'
    if path.exists():
        print('Existing dataset preserved:', path)
        return
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUT / 'human-labels.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        fields = ['id', 'split', 'statement', 'product', 'conditions', 'official_url', 'locator', 'property', 'quote', 'human_label', 'reviewer']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item.get(k, '') for k in fields})
    request = {'task': dataset['evaluation_policy'], 'allowed_verdicts': ['confirmed', 'contradicted', 'insufficient_evidence'],
               'claims': [{k: item[k] for k in ['id', 'statement', 'product', 'conditions', 'official_url', 'locator', 'property', 'quote']} for item in items]}
    (OUT / 'request.json').write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'request.sha256').write_text(hashlib.sha256((OUT / 'request.json').read_bytes()).hexdigest(), encoding='ascii')
    print('Prepared 30 candidates (10/class), human gold pending; dev18/holdout12')


if __name__ == '__main__':
    main()
