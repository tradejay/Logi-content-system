"""Build literal equipment candidates; these are not semantic confirmations."""
import json
import csv
from collections import Counter
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/blog_performance/product-search/20261021T054347Z/relevance-review/body-review'

def compact(value):
    return re.sub(r'[^a-z0-9가-힣]', '', value.lower())

def main():
    catalog = json.loads((ROOT/'services/blog_performance/product-search-catalog.json').read_text(encoding='utf-8'))
    bodies = json.loads((BASE/'bodies.json').read_text(encoding='utf-8'))
    aliases = {'Logitech':['logitech','로지텍'], 'HP Poly':['poly','폴리','폴리콤'],
               'Yealink':['yealink','예링크'], 'Neat':['neat','니트'],
               'Cisco':['cisco','시스코'], 'AVer':['aver','에버'], 'Jabra':['jabra','자브라']}
    output=[]
    for body in bodies:
        text=compact(body.get('body_text',''))
        brands=[brand for brand,names in aliases.items() if any(compact(name) in text for name in names)]
        matches=[]
        for product in catalog:
            names=[product['product'],*product.get('queries',[])]
            # Prefer longer aliases at overlapping positions: Rally Bar Mini must
            # not create Rally / Rally Bar matches from the same mention.
            for name in names:
                needle=compact(name)
                for hit in re.finditer(re.escape(needle),text):
                    matches.append((hit.start(),hit.end(),product['product_id'],name))
        # Out-of-panel successors must suppress an older model's prefix match.
        for name in ['Rally Bar 2','Rally System 2','Rally System 2 Pro','랠리바2','랠리시스템2','랠리시스템2프로']:
            for hit in re.finditer(re.escape(compact(name)),text):
                matches.append((hit.start(),hit.end(),None,name))
        kept=[m for m in matches if not any(n[0]<=m[0] and n[1]>=m[1] and n[1]-n[0]>m[1]-m[0] for n in matches)]
        ids=sorted({m[2] for m in kept if m[2] is not None})
        output.append({'candidate_id':body['candidate_id'],'brand_candidates':brands,
                       'url':body.get('url'),'title':body.get('actual_title'),
                       'catalog_product_candidates':ids,
                       'classification':'catalog_name_found' if ids else 'model_identification_required' if brands else 'no_catalog_name_found',
                       'status':'literal_candidates_only','body_status':body['status']})
    (BASE/'equipment-name-candidates.json').write_text(json.dumps({'items':output,'note':'문자열 후보이며 실제 관련성·목록 외 모델 여부는 본문 의미 검토로 확정한다.'},ensure_ascii=False,indent=2),encoding='utf-8')
    for filename, rows in [('equipment-name-matches.csv',output),('equipment-name-unmatched.csv',[r for r in output if not r['catalog_product_candidates']])]:
        with (BASE/filename).open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader()
            writer.writerows([{k:','.join(v) if isinstance(v,list) else v for k,v in r.items()} for r in rows])
    print(json.dumps(dict(Counter(r['classification'] for r in output))))

if __name__=='__main__':main()
