"""Persist source-backed human web research separately from worker guesses."""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/blog_performance/product-search/20261021T054347Z/relevance-review/body-review/brand-only-review'

SOURCES={
 'yealink_models':'https://support.yealink.com/docs/yealink-management-cloud-service-ymcs/supported-device-models/7affe919d2ff4d35a02d274cb0ed2210',
 'yealink_rooms':'https://support.yealink.com/it-it/docs/a25/famiglia-di-prodotti-camere/a41569a4624e44718fe6aa5e5b2c7658',
 'yealink_legacy':'https://www.yealink.com/en/onepage/video-conferencing-deal-registration-program-eligible-skus',
 'yealink_eyepro':'https://support.yealink.com/products/video-conferencing-product/meetingeye-400-pro/0199142874a27c57825eb3bf71296d44?categoryID=01991428-74a4-7752-ae3e-a4e436e3af04&resourceType=0',
 'yealink_mics':'https://www.yealink.com/en/onepage/list-video-conference-hardware',
 'yealink_vcm36':'https://www.yealink.com/en/product-detail/accessories-vcm36-w',
 'yealink_eos':'https://www.yealink.com/en/product-list/eos-products',
 'hp_a2':'https://kaas.hpcloud.hp.com/pdf-public/pdf_11944358_en-US-1.pdf',
 'hp_a2bridge':'https://h20195.www2.hp.com/v2/GetDocument.aspx?docname=c09178670',
 'hp_a2mic':'https://h20195.www2.hp.com/v2/GetDocument.aspx?docname=c09178671',
 'hp_usb':'https://www.hp.com/us-en/poly/video-conferencing/usb/studio-v72.html',
 'hp_video':'https://kaas.hpcloud.hp.com/pdf-public/pdf_10162905_en-US-1.pdf',
 'hp_g7500':'https://support.hp.com/us-en/product/setup-user-guides/g7500-kit-series/model/2101738661',
 'hp_p009':'https://kaas.hpcloud.hp.com/pdf-public/pdf_10008262_en-US-1.pdf',
 'hp_p15':'https://kaas.hpcloud.hp.com/pdf-public/pdf_9122829_en-US-1.pdf',
 'hp_debut':'https://support.hp.com/emea_africa-en/product/details/rp-series/model/2101791589',
 'aver_usb':'https://www.aver.com/Downloads/search?q=VB342+Pro',
 'aver_old':'https://communication.aver.com/discontinued-products/usb-videoconferencing',
 'aver_room':'https://pro.averusa.com/products/software/room-management',
 'aver_ptz':'https://presentation.aver.com/DownloadFile.ashx?n=2551&t=ModelOther1',
 'aver_ep65':'https://tw.communication.aver.com/model/ep65',
 'aver_fone':'https://www.aver.com/Downloads/search?q=FONE540',
 'jabra_20':'https://www.jabra.com/-/media/Images/Campaigns/SMB/Login-Page/Files/JABRA-SOLUTIONS-FOR-WORK-Interactive-130623',
 'jabra_40':'https://www.jabra.com/business/video-conferencing/jabra-panacast-40-vbs',
 'jabra_50':'https://www.jabra.com/_/media/Jabra_VXi_Product-Documentation/Jabra-PanaCast-50-VBS/Tech-specs/RevE/EN-PanaCast-50-VBS-TechSpec_EMEA-SKUs-13082025.pdf',
 'jabra_55':'https://www.jabra.com/en-APAC/supportpages/jabra-panacast-55-vbs',
 'jabra_speak':'https://www.jabra.com/de-de/business/speakerphones/Jabra-speak-series',
 'jabra_55speak':'https://www.jabra.com/en-in/business/speakerphones/jabra-speak-series/jabra-speak2-55/buy',
 'jabra_810':'https://www.jabra.com/supportpages/jabra-speak-810',
 'logi_meetup':'https://hub.sync.logitech.com/meetup/post/specifications-meetup-rwHjvleBQUMPejN',
 'logi_c930':'https://hub.sync.logitech.com/c930e/post/specifications---webcam-c930e-l1ZbNFnUtInUpc1',
 'logi_bcc':'https://hub.sync.logitech.com/bcc950/post/specifications---bcc950-conferencecam-o7RYvMWKQWVcNLF',
 'logi_connect':'https://hub.sync.logitech.com/connect/post/conferencecam-connect-specifications-gh1So1shzPbEgtw',
 'logi_connect_regulator':'https://telcor.gob.ni/wp-content/uploads/2023/03/Prueba4.pdf',
 'cisco_dx':'https://www.cisco.com/c/en/us/products/collateral/collaboration-endpoints/webex-desk-series/datasheet-c78-731879.html',
 'cisco_accessories':'https://www.cisco.com/c/ja_jp/products/collateral/collaboration-endpoints/spark-room-kit-series/datasheet-c78-738729.html',
 'avaya':'https://www.avaya.com/jp/documents/fs-cu-360-uc8096en.pdf',
 'tenveo':'https://cn.tenveo.com/product/all-in-one-conference-kit/400.html',
 'barco':'https://www.barco.com/en/support/knowledge-base/7974-clickshare-base-c-5-c-10-cx-20-and-cx-30-2nd-generation',
 'sony_d21':'https://www.sony.com/electronics/support/uwp-d-wireless-series-uwp-d-series-microphone-packages/uwp-d21',
 'sony_mics':'https://www.sony.fr/camera-accessories/microphones',
 'nikon':'https://imaging.nikon.com/history/chronicle/history-f4/',
 'thinksound':'https://thinksound.com/pages/faq',
 'ucotech':'https://www.ucotech.co.kr/product/ESP1',
 'ucotech_re1':'https://www.ucotech.co.kr/blogPost/RE1',
 'lunalab':'https://lunalab.co.kr/58/?idx=145',
 'apple_m5':'https://www.apple.com/newsroom/2025/10/apple-introduces-the-powerful-new-ipad-pro-with-the-m5-chip/',
 'hp_g9':'https://support.hp.com/us-en/document/ish_14918739-11736569-16',
 'logi_meetup_cable':'https://hub.sync.logitech.com/meetup',
 'lg_board':'https://eu.lg-informationdisplay.com/products-solutions/digital-signage/lg-createboard-idb/65TR3DQ',
 'epson':'https://www.epson.com.au/support/product/eb-810e/',
 'yamaha':'https://usa.yamaha.com/products/proaudio/mixers/mg_series_xu_model/',
 'beyer':'https://support.beyerdynamic.com/hc/en-us/articles/360001575734-What-s-the-difference-between-the-DT770-990-PRO-and-the-DT-1770-1990-PRO',
 'at_monitor':'https://www.audio-technica.com.hk/index.php?action=details&lang=eng&nid=1273&op=newsList',
 'sennheiser':'https://my.sennheiser-hearing.com/pages/product-manual-index',
}

def main():
    data=json.loads((BASE/'model-term-decisions.json').read_text(encoding='utf-8'))['items']
    decisions={}
    def add(terms,brand,model,kind,source,status='official_model_confirmed',note=''):
        for term in terms.split('|'):
            decisions[term.lower()]={'researched_brand':brand,'researched_model':model,'equipment_type':kind,
              'research_status':status,'sources':[SOURCES[s] for s in source.split('|')], 'research_note':note,
              'post_identity_confirmed':False,'scoring_eligible':False}
    for n in ['A10','A20','A30','A40']:add(n,'Yealink','MeetingBar '+n,'비디오바','yealink_models')
    for n in ['MeetingEye400','MeetingEye600']:add(n,'Yealink',n.replace('Eye','Eye '),'회의실 단말','yealink_models')
    add('MeetingEye400Pro','Yealink','MeetingEye 400 Pro','회의실 단말','yealink_eyepro')
    for n in ['MVC860','MVC940']:add(n,'Yealink',n,'회의실 구성 키트','yealink_models')
    for n in ['UVC20','UVC80']:add(n,'Yealink',n,'카메라','yealink_legacy')
    add('UVC40','Yealink','UVC40','USB 비디오바','yealink_rooms')
    add('CP900','Yealink','CP900','스피커폰','yealink_eos')
    add('CPW90','Yealink','CPW90','확장 마이크','yealink_eos')
    for n in ['VCM34','VCM35','VCM38']:add(n,'Yealink',n,'마이크','yealink_mics')
    add('VCM36','Yealink','VCM36-W','무선 마이크','yealink_vcm36','family_candidate','원문 VCM36 약칭. -W 세부 표기는 확정하지 않음.')
    for n in ['WPP20','WPP30']:add(n,'Yealink',n,'무선 공유 장치','yealink_rooms')
    add('A2','HP Poly','Studio A2','오디오 솔루션 제품군','hp_a2',note='단독 비디오바가 아닌 오디오 제품군')
    add('A2Audio','HP Poly','Studio A2 Audio Bridge','오디오 브리지','hp_a2bridge')
    add('A2MIC|A2Table','HP Poly','Studio A2 Table Microphone','탁상 마이크','hp_a2mic')
    for n in ['V12','V52','V72','R30']:add(n,'HP Poly','Studio '+n,'USB 비디오바','hp_usb')
    for n in ['G62','X32','X50','X52','X72']:add(n,'HP Poly','Studio '+n,'회의실 시스템' if n=='G62' else '비디오바','hp_video')
    add('X701','HP Poly','Studio X70','비디오바','hp_video','context_repaired','원문 X70 - 1개가 병합됨. X701 모델이 아님.')
    for n in ['E70','G7500','TC8','TC10']:add(n,'HP Poly',('Studio ' if n=='E70' else '')+n,'카메라' if n=='E70' else '회의실 시스템' if n=='G7500' else '컨트롤러','hp_g7500')
    add('P009','HP Poly','Studio USB','USB 비디오바','hp_p009',note='P009는 규제 모델 번호')
    add('P15','HP Poly','Studio P15','개인용 비디오바','hp_p15')
    for n,model in [('CAM340','CAM340 / CAM340+'),('CAM540Conference','CAM540'),('VB342','VB342'),('VC520','VC520'),('VC520Pro','VC520 Pro'),('VC520Pro2','VC520 Pro2')]:
        add(n,'AVer',model,'비디오바' if n=='VB342' else '카메라/회의 키트','aver_old|aver_usb','family_candidate' if n=='CAM340' else 'official_model_confirmed', 'CAM340과 CAM340+는 별도 제품. 플러스 기호 유실 주의.' if n=='CAM340' else '')
    add('BV342','AVer','VB342+','비디오바','aver_old','suspected_typo','원문 BV342+는 공식 VB342+의 글자 순서 오타 후보. 자동 매칭 금지.')
    for n in ['DL10','DL30','PTC310','PTC330','PTC500S']:add(n,'AVer',n,'강의/추적 카메라','aver_ptz')
    add('EP65AIO','AVer','EP65','회의용 터치 디스플레이','aver_ep65')
    add('FONE540','AVer','FONE540','스피커폰','aver_fone')
    add('Panacast20','Jabra','PanaCast 20','개인용 카메라','jabra_20')
    add('PanaCast40VBS','Jabra','PanaCast 40 VBS','비디오바','jabra_40')
    add('PanaCast55VBS','Jabra','PanaCast 55 VBS','비디오바','jabra_55',note='기존 AI의 50 VBS 매칭 오류 정정. 55는 별도 제품.')
    add('VBS50','Jabra','PanaCast 50 VBS','비디오바','jabra_50','context_alias','원문 Panacast VBS50 문맥의 약칭. 공식 정식명은 PanaCast 50 Video Bar System.')
    add('Speak2','Jabra','Speak2','스피커폰 제품군','jabra_55speak','family_candidate','시리즈 이름만으로 개별 모델 확정 금지')
    add('Speak255','Jabra','Speak2 55','스피커폰','jabra_55speak')
    for n in ['Speak410','Speak750']:add(n,'Jabra',n.replace('Speak','Speak '),'스피커폰','jabra_speak')
    add('Speak810','Jabra','Speak 810','스피커폰','jabra_810')
    add('R0007','Logitech','MeetUp','비디오바','logi_meetup',note='원문 V-R0007의 일부 코드')
    add('VR0013','Logitech','ConferenceCam Connect','휴대형 회의 카메라','logi_connect_regulator','regulatory_model_confirmed','기존 AI Rally Bar 매칭 오류 정정. 국가 규제기관 VR0013=ConferenceCam Connect 확인.')
    add('U0029','Logitech',None,'회의용 카메라','logi_bcc|logi_connect|logi_c930','source_conflict','C930e는 V-U0031. V-U0029는 공식 BCC950와 Connect 문서 양쪽에 나타나므로 단독 코드로 모델 확정 금지.')
    add('DX80','Cisco','Webex DX80','데스크형 회의 단말','cisco_dx')
    add('MIC20','Cisco','Table Microphone 20','탁상 마이크','cisco_accessories','context_alias','MIC20만으로 일반 모델을 식별하지 말고 Cisco 문맥 필요')
    add('Touch10x','Cisco','Touch 10','컨트롤러','cisco_accessories','context_alias','Touch10 뒤 x 결합된 추출 후보')
    add('CU360','Avaya','Collaboration Unit CU360','회의 단말','avaya')
    add('VA2000E','Tenveo','TEVO-VA2000(E)','회의 키트','tenveo','official_search_listing_confirmed','공식 검색 색인에서 확인. 직접 페이지 열기는 시간 초과. E 세부 변형 원문 보존.')
    # Previously unresolved tokens repaired only where original nearby text resolves them.
    for term,base in [('A21','A2'),('DL302','DL30'),('DL303','DL30'),('G75003','G7500'),('V121','V12'),('V521','V52'),('V721','V72'),('VCM341','VCM34')]:
        decisions[term.lower()]={**decisions[base.lower()],'research_status':'context_repaired','research_note':'원문 모델명 뒤 수량/항목번호가 결합된 추출 오류. 독립 모델 아님.'}
    add('Debut1','HP Poly','RealPresence Debut','회의 단말','hp_debut','context_repaired','Debut - 1개의 수량이 결합됨')
    add('APP2','AVer','PTZApp 2','소프트웨어','aver_old','context_repaired','장비가 아닌 관리 소프트웨어')
    add('C5','Barco','ClickShare C-5','무선 화면 공유','barco')
    add('CX30','Barco','ClickShare CX-30','무선 회의 연결','barco')
    add('D21','Sony','UWP-D21','무선 마이크','sony_d21','context_repaired','원문 SONY UWP-D21에서 접두어 유실')
    add('B10','Sony','ECM-B10','카메라용 마이크','sony_mics','context_repaired','원문 SONY ECM-B10에서 접두어 유실')
    add('D26','Sony','UWP-D26','무선 마이크','sony_mics','context_repaired','원문 SONY UWP-D26에서 접두어 유실')
    for n in ['F601','F801']:add(n,'Nikon',n.replace('F','F-'),'필름 카메라','nikon',note='VC 장비 아님. 원문 관련글 링크에 등장해 본문 주제 판정에는 사용 금지.')
    for n in ['on1','on2']:add(n,'Thinksound',n,'헤드폰','thinksound',note='화상회의 장비가 아닌 음악용 헤드폰')
    add('p1','UCOTECH','ES-P1','이어폰','ucotech','context_repaired','원문 es-p1의 접두어 유실')
    add('RE1','UCOTECH','RE-1','이어폰','ucotech_re1','context_repaired','기존 AI HiFiMAN 브랜드 추정을 정정. 원문 유코텍 문맥 필요.')
    add('N05','LUNA LAB','N05','노트북 거치대','lunalab')
    add('M5','Apple','iPad Pro (M5)','태블릿/칩 표기','apple_m5','context_repaired','M5 자체는 칩 이름. 원문 iPad Pro 11 문맥으로 제품군 식별.')
    add('G9Plus','HP Poly','Studio Base Kit G9 Plus','회의실 PC/컨트롤러 키트','hp_g9','context_alias','HP G9 일반 PC가 아닌 원문 회의실 Base Kit 여부 구분 필요.')
    add('10mMic','Logitech','MeetUp Mic Extension Cable (10m)','마이크 연장 케이블','logi_meetup_cable')
    add('65TR3DQ','LG','65TR3DQ','회의용 터치 디스플레이','lg_board')
    add('EB810E','Epson','EB-810E','프로젝터','epson')
    add('MG12XU','Yamaha','MG12XU','오디오 믹서','yamaha')
    for n in ['DT1770PRO','DT1990PRO','DT770PRO','DT990PRO']:add(n,'Beyerdynamic',n,'모니터 헤드폰','beyer')
    for n in ['M50x','M70x','R70x']:add(n,'Audio-Technica','ATH-'+n,'모니터 헤드폰','at_monitor')
    for n in ['HD560S','HD600','HD650','IE300']:add(n,'Sennheiser',n,'헤드폰/이어폰','sennheiser')
    out=[]
    for row in data:
        detail=decisions.get(row['term'].lower(),{'researched_brand':row.get('brand'),'researched_model':None,'equipment_type':None,'research_status':'not_individually_verified','sources':[],'research_note':'기존 AI 후보 분류만 보존. 온라인 실재/모델 매칭 미확정.','post_identity_confirmed':False,'scoring_eligible':False})
        # Keep worker guesses for audit, but never expose them as confirmed IDs.
        revised={**row,**detail,'ai_proposed_product_ids':row.get('product_ids',[]),'product_ids':[]}
        # A matching fragment is not a model. Local evidence is retained without
        # pretending a manufacturer page was needed to classify an address.
        local_exclusions={
          'b01':'원문의 상가 B01호 주소. 장비명 아님.',
          'f3':'원문의 F3.5-5.6 렌즈 조리개 사양 일부. 모델명 아님.',
          'haze2':'원문의 Haze 2% 표면 수치. 모델명 아님.',
          'i57':'원문의 Intel Core i5 7세대 요구사항. 제품 모델 번호 아님.',
          'off1':'NoiseBlockAI Off - 1.8M 수치 결합. 모델명 아님.',
          'on4':'NoiseBlockAI On - 4.3M 수치 결합. 모델명 아님.',
          'sony1':'SONY 1인치 센서의 수치 결합. 독립 모델명 아님.',
        }
        if row['term'].lower() in local_exclusions:
            revised.update(researched_brand=None,researched_model=None,equipment_type=None,research_status='not_equipment_context_verified',sources=[],research_note=local_exclusions[row['term'].lower()])
        out.append(revised)
    target=BASE/'web-research';target.mkdir(exist_ok=True)
    (target/'equipment-research.json').write_text(json.dumps({'research_started':'2026-10-21','research_updated':'2026-10-22','scope':'397개 전 항목 추적. VC 후보 71개 및 미확정 34개 우선 조사; 기타 장비는 관련 항목만 보완.','items':out,'sources':SOURCES},ensure_ascii=False,indent=2),encoding='utf-8')
    cols=['id','term','category','researched_brand','researched_model','equipment_type','research_status','research_note','sources','post_ids']
    with (target/'equipment-by-brand.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for r in sorted(out,key=lambda r:(r.get('researched_brand') or '~',r.get('researched_model') or r['term'])):w.writerow({k:' | '.join(r[k]) if isinstance(r.get(k),list) else r.get(k) for k in cols})
    groups=defaultdict(list)
    for r in out:
        if r['sources']:groups[r['researched_brand']].append(r)
    lines=['# 추출 장비 온라인 조사 — 갱신 2026-10-22','','제조사 공식 페이지·공식 지원 문서 우선. VR0013은 국가 규제기관 문서로 확인. 제품 존재와 각 게시글의 실제 모델 매칭은 별개다. 점수·원본 카탈로그에는 자동 반영하지 않았다.','','397개 원시 후보 중 VC로 분류된 71개와 불명확 34개를 우선 조사했다. 기타 장비 222개 전수 온라인 확인은 수행하지 않았으며 미확인 항목은 CSV/JSON에 별도 상태로 남긴다.','','## 브랜드별 조사 항목']
    for brand,rs in sorted(groups.items()):
        lines+=['',f'### {brand}','','| 추출 표기 | 확인 모델/제품군 | 종류 | 확인 상태 | 근거 |','|---|---|---|---|---|']
        for r in rs:lines.append(f"| {r['term']} | {r['researched_model'] or '모델 확정 보류'} | {r['equipment_type']} | {r['research_status']} | "+' / '.join(f'[자료{i+1}]({u})' for i,u in enumerate(r['sources']))+' |')
    lines+=['','## 매칭 보류와 정정','','- U0029: C930e 매칭 폐기. 공식 C930e는 V-U0031이며 V-U0029는 BCC950/Connect 문서 충돌로 보류.','- VR0013: Rally Bar 매칭 폐기. 규제기관은 ConferenceCam Connect로 명시.','- PanaCast55VBS: PanaCast 50 VBS와 합치지 않고 55 VBS로 분리.','- CAM340과 CAM340+, VB342와 VB342+는 별도 변형. 추출 때 플러스 기호를 버린 후보는 확정하지 않음.','- BV342: 원문 오타 후보이며 VB342+로 자동 덮어쓰지 않음.','- VCM36, Speak2는 세부모델 미확정 제품군 후보.','- X701, DL302, G75003 등은 원문 인접 수량/항목번호 병합을 확인해 보정한 것으로 새 모델이 아님.','','## 미확정 항목','','출처가 없는 후보는 `not_individually_verified`로 유지한다. 단어의 제품 실재 여부 확인은 해당 블로그가 장비를 실제로 다루는지의 확정을 대체하지 않는다.']
    (target/'equipment-by-brand.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'source_linked_terms':sum(bool(r['sources']) for r in out),'unverified_terms':sum(not r['sources'] for r in out),'brands':list(sorted(groups)),'status_counts':dict(Counter(r['research_status'] for r in out))},ensure_ascii=False))

if __name__=='__main__':main()
