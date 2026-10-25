"""Attach body/model classifications to Korean browser product-query ranks."""
import argparse,csv,hashlib
from collections import Counter
from pathlib import Path
from services.blog_performance.insights.collect_common_query_ranks import ROOT,read,save
from services.blog_performance.insights.import_product_browser_ranks import identity
from services.blog_performance.insights.merge_browser_body_classifications import build_classifications


def main():
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--result',type=Path,required=True);p.add_argument('--no-activate',action='store_true');a=p.parse_args();base=a.base.resolve();out=base/'body-analysis'
    index,records,bodies,terms,decisions,term_map,catalog=build_classifications(out,a.result)
    panel=read(base/'query-panel.json');products=[];flat=[]
    for q in panel['rows']:
        best={};own_raw=[];matched=0;pending=0
        for row in q['rows']:
            post=identity(row['url']);entry=index[post];blog=post.split('/')[0]
            match=q['product_id'] in entry['product_ids']
            status='catalog_model_name_matched' if match else 'expected_brand_model_unresolved' if q['brand'] in entry['brands'] else 'other_or_unclassified'
            if entry['body_status']!='success':status='body_unavailable'
            if match:
                matched+=1
                if blog not in best or row['rank']<best[blog]['rank']:best[blog]={**row,'blog_id':blog,'classification_basis':entry['classification_basis']}
            elif status in ['expected_brand_model_unresolved','body_unavailable']:pending+=1
            if blog=='oceantech01':own_raw.append({**row,'model_name_matched':match})
            flat.append({'keyword':q['keyword'],'product_id':q['product_id'],'brand':q['brand'],'product':q['product'],'group':q['group'],'rank':row['rank'],'url':row['url'],'title':row['title'],'blog_id':blog,'post_key':post,'status':status,'body_status':entry['body_status'],'matched_product_ids':entry['product_ids']})
        products.append({**{k:q[k] for k in ['keyword','product_id','brand','product','group','captured_at']},'raw_results':len(q['rows']),'model_matched_results':matched,'unresolved_results':pending,
            'own_raw_ranks':own_raw,'own_model_matched_rank':best.get('oceantech01'),'blog_ranks':sorted(best.values(),key=lambda x:x['rank'])})
    manifest=read(base/'manifest.json');report={**manifest,'status':'browser_capture_body_and_term_candidates','search_surface':'naver_blog_tab','sort':'relevance','language':'ko_only','english_capture_available':False,
        'products':products,'rank_rows':flat,'body_collection':{'total':len(bodies),'success':sum(b['status']=='success' for b in bodies.values()),'failed':sum(b['status']!='success' for b in bodies.values())},
        'term_review':{'new_ai_decisions':len(decisions),'reused_prior':len(terms)-len(decisions),'counts':dict(Counter(d['category'] for d in term_map.values()))},'ai_result_sha256':hashlib.sha256(a.result.read_bytes()).hexdigest(),
        'limitations':['사용자 제공 블로그 탭 관련도순 첫 로딩 최대 30개 일반 글. 검색어별 실제 수집 개수는 다르며 0개로 맞춰 채우지 않음.',
          '한글 검색 화면 순서만 사용. 영문 API 결과와 합치거나 평균 점수로 계산하지 않음.',
          '원래 검색 순서 유지. 다른 모델·무관한 글·외부 블로그도 원자료에 보존. 표의 경쟁 블로그 순위는 본문 장비명 매칭 후보 기준.',
          '본문의 브랜드·장비명 기계 매칭 및 미확정 모델 용어 AI 판정이며 전문 의미 검토 완료가 아님.',
          '오우션 원래 위치는 해당 검색어 결과에 나타난 모든 오우션 글 기준으로 별도 보존. 장비명 미확인 글은 구분 표시.',
          '미관측은 실제 미노출 확정이 아니며 PC/모바일·로그인 조건은 미기록.']}
    save(out/'product-report.json',report)
    with (out/'product-rank-rows.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    lines=['# 한글 장비명 검색 · 제공 화면 순서','',f'{len(products)}개 검색어 · {len(flat)}건 / 고유 글 {manifest["unique_posts"]}개. 한글 검색만 수집했고 API·영문 순위는 혼합하지 않았습니다.','',
       f'본문 확보 {report["body_collection"]["success"]}개 · 실패 {report["body_collection"]["failed"]}개','','|검색어|수집 건수|본문 장비명 매칭|오우션 원래 최고 위치|장비명 매칭 여부|','|---|---:|---:|---:|---|']
    for x in products:
        own=x['own_raw_ranks'][0] if x['own_raw_ranks'] else None
        lines.append(f'|{x["keyword"]}|{x["raw_results"]}|{x["model_matched_results"]}|{own["rank"] if own else "—"}|{("매칭" if own["model_name_matched"] else "미확인") if own else "관측 없음"}|')
    lines+=['','## 범위',*['- '+v for v in report['limitations']]];(out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if not a.no_activate:save(base.parent/'latest-products-ko.json',{'base':str(base.relative_to(ROOT)),'report':str((out/'product-report.json').relative_to(ROOT)),'raw_sha256':manifest['raw_sha256']})
    print({'products':len(products),'rows':len(flat),'body_collection':report['body_collection'],'model_matched_rows':sum(x['model_matched_results'] for x in products),'term_review':report['term_review']})

if __name__=='__main__':main()
