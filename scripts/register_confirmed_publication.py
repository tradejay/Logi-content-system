"""Record the user's confirmed publication without changing QA or approval."""
import csv
import json
import shutil
from datetime import datetime
from services.taiga_tracking import ROOT, synchronize


def main():
    cid = 'CNT-LIVE-20261008-VERIFY-001'
    url = 'https://blog.naver.com/oceantech01/224440463862'
    registry = ROOT / 'content-system/registry/CONTENT_REGISTRY.csv'
    with registry.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    row = next(r for r in rows if r['content_id'] == cid)
    backup = ROOT / 'archive/publication-registration' / datetime.now().strftime('%Y%m%dT%H%M%S')
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(registry, backup / registry.name)
    row.update(status='PUBLISHED', published_url=url, published_date='2026-10-13')
    with registry.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    from services.performance_db import register_content
    register_content(content_id=cid, blog_id='oceantech01', title=row['title'], primary_keyword=row['primary_keyword'], canonical_topic=row['canonical_topic'], published_date=row['published_date'], published_url=url)
    report = synchronize()
    ticket = next(t for t in report['tickets'] if t['key'] == 'content:' + cid)
    print(json.dumps({'content_id': cid, 'published_url': url, 'published_date': row['published_date'], 'state': ticket['state'], 'ticket': ticket['url']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
