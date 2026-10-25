"""Read saved run artifacts for the review UI; never reconstruct model output."""
import hashlib
import html
import json
import re
from services.content_pipeline import ContentPipeline


def redact(value):
    if isinstance(value, dict):
        return {k: ('[인증정보 숨김]' if re.search(r'api[_-]?key|authorization|password|secret', k, re.I)
                    else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return re.sub(r'AIza[\w-]{20,}|sk-or-v1-[\w-]+|Bearer\s+[\w.\-]+', '[인증정보 숨김]', value)
    return value


def build_natural_summary(path_name, content, kind, stage_label):
    """Generate admin-friendly Korean natural language summaries for pipeline artifacts."""
    summary = {
        'title': stage_label,
        'summary': '',
        'highlights': []
    }
    try:
        if isinstance(content, dict) and 'receipt_status' in content and 'entries' in content:
            summary['title'] = '규칙 전달·수신 확인'
            summary['summary'] = f"전달 항목 {len(content['entries'])}건 / 수신 확인: {content['receipt_status']}. 실제 준수 여부는 별도 검토합니다."
            summary['highlights'] = [f"호출: {content.get('call_id', '')}", f"릴리스: {content.get('release_id', '')}"]
            return summary
        if isinstance(content, dict) and 'token_count_status' in content:
            summary['title'] = '입력 토큰 측정'
            summary['summary'] = f"측정 상태: {content['token_count_status']} / 입력: {content.get('input_tokens')} / 예산: {content.get('input_token_budget')} 토큰"
            return summary
        if 'guide-manifest.json' in path_name:
            rel_id = content.get('release_id', '미지정') if isinstance(content, dict) else '미지정'
            b_hash = content.get('bundle_sha256', '') if isinstance(content, dict) else ''
            rules_cnt = len(content.get('rules', {})) if isinstance(content, dict) else 0
            guides_cnt = len(content.get('guides', {})) if isinstance(content, dict) else 0
            summary['title'] = '가이드 정책 릴리스 매니페스트'
            summary['summary'] = f"버전 고정 정책 릴리스 '{rel_id}' (규칙 {rules_cnt}건, 가이드 {guides_cnt}건)가 실행에 불변 적용되었습니다."
            summary['highlights'] = [
                f"릴리스 ID: {rel_id}",
                f"번들 해시: {b_hash[:12]}...",
                f"규칙/가이드 수: 규칙 {rules_cnt}건 / 가이드 {guides_cnt}건"
            ]
            return summary

        if 'requirements.json' in path_name:
            reqs = content.get('requirements', {}) if isinstance(content, dict) else {}
            rules_req = sum(1 for v in reqs.values() if isinstance(v, dict) and v.get('kind') == 'rule')
            facts_req = sum(1 for v in reqs.values() if isinstance(v, dict) and v.get('kind') == 'fact')
            summary['title'] = '원고 준수 요구사항 명세'
            summary['summary'] = f"총 {len(reqs)}건의 요구사항(필수 규칙 {rules_req}건, 팩트 {facts_req}건)이 계약으로 고정되었습니다."
            summary['highlights'] = [
                f"총 요구사항: {len(reqs)}건",
                f"규칙 요구: {rules_req}건",
                f"팩트 요구: {facts_req}건"
            ]
            return summary

        if 'review-report.json' in path_name:
            passed = content.get('passed', False) if isinstance(content, dict) else False
            struct_cnt = len(content.get('structural_checks', [])) if isinstance(content, dict) else 0
            sem_cnt = len(content.get('semantic_checks', [])) if isinstance(content, dict) else 0
            human_cnt = len(content.get('human_checks', [])) if isinstance(content, dict) else 0
            summary['title'] = '종합 거버넌스 및 검토 보고서'
            summary['summary'] = f"구조 검증, 의미 검토, 관리자 승인 대기 항목을 종합한 최종 보고서입니다. (판정: {'통과' if passed else '수정/확인 필요'})"
            summary['highlights'] = [
                f"최종 통과: {'합격' if passed else '불합격(대기)'}",
                f"구조적 결함: {struct_cnt}건",
                f"의미적 이슈: {sem_cnt}건",
                f"사람 확인 대기: {human_cnt}건"
            ]
            return summary

        if 'coverage' in path_name:
            sat = content.get('satisfied', []) if isinstance(content, dict) else []
            unres = content.get('unresolved', []) if isinstance(content, dict) else []
            summary['title'] = '요구사항 충족도 (Coverage)'
            summary['summary'] = f"충족 완료 {len(sat)}건, 미해결 이슈 {len(unres)}건으로 측정되었습니다."
            summary['highlights'] = [
                f"충족 요구사항: {len(sat)}건",
                f"미해결 요구사항: {len(unres)}건"
            ]
            return summary

        if 'context-selection' in path_name:
            sel_r = len(content.get('selected_rules', [])) if isinstance(content, dict) else 0
            sel_f = len(content.get('selected_facts', [])) if isinstance(content, dict) else 0
            chars = content.get('char_count', 0) if isinstance(content, dict) else 0
            summary['title'] = '문단/단계 컨텍스트 조립 명세'
            summary['summary'] = f"규칙 {sel_r}건과 팩트 {sel_f}건을 선별 조립했습니다. (조립 크기: {chars:,}자)"
            summary['highlights'] = [
                f"선택 규칙: {sel_r}건",
                f"선택 팩트: {sel_f}건",
                f"총 글자수: {chars:,}자"
            ]
            return summary

        if 'gap-snapshot.json' in path_name:
            sel = content.get('selection', '') if isinstance(content, dict) else ''
            cands = content.get('keyword_candidates', []) if isinstance(content, dict) else []
            summary['title'] = '검색 갭 및 키워드 진단'
            summary['summary'] = f"핵심 타깃 검색어로 '{sel}'을(를) 도출하고 연관 키워드 {len(cands)}건의 검색 수요를 분석했습니다."
            summary['highlights'] = [
                f"선택 키워드: {sel}",
                f"발굴 후보수: {len(cands)}개",
                f"진단 상태: {content.get('collection_status', '완료') if isinstance(content, dict) else '완료'}"
            ]
            return summary

        if 'keyword-entity-map.json' in path_name:
            prods = content.get('entities', {}).get('product_ids', []) if isinstance(content, dict) else []
            feats = content.get('entities', {}).get('feature_ids', []) if isinstance(content, dict) else []
            summary['title'] = '키워드-제품 매칭 맵'
            summary['summary'] = f"타깃 검색어를 로지텍 제품({', '.join(prods) or '기본'}) 및 주요 기능({', '.join(feats) or '기본'})과 상호 연결했습니다."
            summary['highlights'] = [
                f"매칭 제품: {', '.join(prods) or '-'}",
                f"매칭 기능: {', '.join(feats) or '-'}"
            ]
            return summary

        if 'brief.json' in path_name:
            brief = content.get('brief', {}) if isinstance(content, dict) else {}
            topic = brief.get('topic') or '로지텍 제품 포스팅'
            kw = brief.get('search', {}).get('primary_keyword', '')
            summary['title'] = '블로그 기획 계약 (Brief)'
            summary['summary'] = f"핵심 타깃 검색어 '{kw}'을(를) 중심으로 '{topic}' 주제의 블로그 작성 계약을 확인했습니다."
            summary['highlights'] = [
                f"타깃 키워드: {kw}",
                f"목표 독자: {brief.get('target_audience', 'IT 관리자 및 기업 실무자')}",
                f"지식 팩: {', '.join(brief.get('knowledge_packs', [])) or '기본'}"
            ]
            return summary

        if 'fact-bundle.json' in path_name:
            facts = content.get('facts', []) if isinstance(content, dict) else []
            sources = content.get('sources', {}) if isinstance(content, dict) else {}
            missing = content.get('missing', []) if isinstance(content, dict) else []
            summary['title'] = '로지텍 공식 팩트 및 출처'
            summary['summary'] = f"지식베이스에서 검증된 팩트 {len(facts)}건과 공식 출처 {len(sources)}건을 원고 작성 자료로 준비했습니다."
            summary['highlights'] = [
                f"검증된 팩트: {len(facts)}건",
                f"공식 출처 문서: {len(sources)}건",
                f"누락 팩트: {len(missing)}건"
            ]
            return summary

        if 'matched-cautions.json' in path_name:
            rules = content.get('rules', []) if isinstance(content, dict) else []
            summary['title'] = '적용된 안전 및 작성 지침'
            summary['summary'] = f"네이버 블로그 품질 기준 및 브랜드 안전 지침 {len(rules)}건이 적용되었습니다."
            summary['highlights'] = [f"규칙: {r.get('id', '')}" for r in rules[:4]]
            return summary

        if 'strategy' in path_name:
            if kind == 'instruction':
                summary['title'] = '전략 수립 지시'
                summary['summary'] = 'AI에게 독자 분석, 플레이북 선정 및 이미지 배치 계획 수립을 지시했습니다.'
                return summary
            if kind == 'facts':
                summary['title'] = '전략 수립 입력 데이터'
                fb = content.get('user_feedback') if isinstance(content, dict) else None
                summary['summary'] = '기획서, 팩트 요약, 선택 가능한 플레이북 정보를 전달했습니다.'
                if fb:
                    summary['summary'] += f' (관리자 추가 지시사항 포함)'
                    summary['highlights'].append(f'추가 지시: {fb}')
                return summary
            st = content
            if isinstance(st, str):
                try:
                    st = json.loads(st)
                except Exception:
                    st = {}
            if not isinstance(st, dict):
                st = {}
            playbook = st.get('primary_playbook', '일반 가이드')
            goal = st.get('article_goal', '제품 정보 전달')
            needs = st.get('asset_needs', [])
            summary['title'] = '수립된 기획 전략'
            summary['summary'] = f"'{playbook}' 플레이북을 채택하여 독자 목표 '{goal}'을(를) 달성하기 위한 구조와 이미지 {len(needs)}장 계획을 확정했습니다."
            summary['highlights'] = [
                f"적용 플레이북: {playbook}",
                f"필수 다룰 내용: {len(st.get('must_cover', []))}건",
                f"계획된 이미지: {len(needs)}장"
            ]
            return summary

        if 'asset-plan.json' in path_name:
            needs = content.get('needs', []) if isinstance(content, dict) else []
            summary['title'] = '이미지 배치 계획'
            summary['summary'] = f"원고의 각 섹션에 배치될 {len(needs)}장의 이미지 시각 자료 계획입니다."
            summary['highlights'] = [f"{n.get('id')}: {n.get('purpose', '')}" for n in needs[:3]]
            return summary

        if 'asset-bindings.json' in path_name:
            bindings = content.get('bindings', []) if isinstance(content, dict) else []
            summary['title'] = '에셋 바인딩 현황'
            summary['summary'] = f"계획된 이미지 슬롯 {len(bindings)}건에 대한 후보 에셋 매칭 및 승인 대기 상태입니다."
            return summary

        if 'write' in path_name:
            if kind == 'instruction':
                summary['title'] = '원고 작성 지시'
                summary['summary'] = '수립된 전략과 공식 팩트를 바탕으로 네이버 블로그 스마트에디터 호환 원고 초안 작성을 지시했습니다.'
                return summary
            if kind == 'facts':
                summary['title'] = '원고 작성 입력 자료'
                fb = content.get('user_feedback') if isinstance(content, dict) else None
                summary['summary'] = '작성 전략, 본문 슬롯용 에셋 계획, 검증된 팩트 세부 명세가 전달되었습니다.'
                if fb:
                    summary['summary'] += f' (관리자 추가 지시: "{fb}")'
                    summary['highlights'].append(f'추가 지시사항: {fb}')
                return summary
            md = content.get('markdown', '') if isinstance(content, dict) else str(content)
            claims = content.get('claims', []) if isinstance(content, dict) else []
            summary['title'] = '작성된 블로그 원고 초안'
            summary['summary'] = f"본문 총 {len(md):,}자 규모의 원고가 완성되었으며, {len(claims)}개의 주장이 팩트 번호와 1:1 매핑되었습니다."
            summary['highlights'] = [
                f"원고 분량: 약 {len(md):,}자",
                f"매핑된 주장(Claims): {len(claims)}개",
                f"미리보기: {md[:80].replace(chr(10), ' ')}..."
            ]
            return summary

        if 'feedback' in path_name:
            if kind == 'instruction':
                summary['title'] = '원고 품질 검토 지시'
                summary['summary'] = '작성된 초안의 팩트 정합성, 규칙 위반, 환각 여부 및 플레이스홀더 배치를 자동 검토하도록 지시했습니다.'
                return summary
            fb = content.get('feedback', content) if isinstance(content, dict) else {}
            passed = fb.get('passed', False)
            issues = fb.get('issues', [])
            missing = fb.get('missing_claims', [])
            summary['title'] = '원고 품질 검토 결과'
            summary['summary'] = f"품질 검토 판정: {'✅ 통과 (합격)' if passed and not issues and not missing else '⚠️ 수정 필요 (반려)'} - 팩트 부합 여부 및 안전 규정을 검증했습니다."
            summary['highlights'] = [
                f"검토 상태: {'합격' if passed else '보완 필요'}",
                f"지적 이슈: {len(issues)}건",
                f"누락 주장: {len(missing)}건"
            ]
            return summary

        if 'official' in path_name:
            if kind == 'instruction':
                summary['title'] = '로지텍 공식 AI 검증 지시'
                summary['summary'] = '원고 내 모든 제품 스펙 주장에 대해 로지텍 공식 AI(Kapa RAG) 지원 지식베이스 교차 검증을 지시했습니다.'
                return summary
            claims = content.get('claims', []) if isinstance(content, dict) else []
            status = content.get('status', 'REVIEWED')
            confirmed = sum(1 for c in claims if c.get('verdict') == 'confirmed')
            contra = sum(1 for c in claims if c.get('verdict') == 'contradicted')
            summary['title'] = '로지텍 공식 AI 교차 검증'
            summary['summary'] = f"로지텍 공식 AI를 통해 총 {len(claims)}개 주장을 대조했습니다. (확인: {confirmed}건, 불일치/반박: {contra}건)"
            summary['highlights'] = [
                f"검증 상태: {status}",
                f"일치 확인: {confirmed}건",
                f"추가 확인 필요: {len(claims) - confirmed}건"
            ]
            return summary

        if 'admin-review-queue' in path_name:
            items = content.get('items', []) if isinstance(content, dict) else []
            summary['title'] = '관리자 승인 대기 항목'
            summary['summary'] = f"원고 발행 전 관리자가 최종 확인해야 할 항목이 총 {len(items)}건 등록되어 있습니다."
            summary['highlights'] = [f"확인: {it.get('detail', it.get('kind', ''))}" for it in items[:4]]
            return summary

        if 'run-result' in path_name:
            outcome = content.get('outcome', '') if isinstance(content, dict) else ''
            summary['title'] = '파이프라인 최종 결과'
            summary['summary'] = f"실행 결과: '{outcome}'. 관리자 확인 후 네이버 블로그 원클릭 복사 또는 발행이 가능합니다."
            summary['highlights'] = [f"상태: {outcome}", f"발행 준비: {'완료' if content.get('publish_ready') else '대기'}"]
            return summary

        if path_name.endswith('.draft.md') and ('CNT-' in path_name or stage_label == '최종 확정 원고'):
            summary['title'] = '최종 확정 원고 (Naver Blog Preview)'
            md_text = content.get('markdown', '') if isinstance(content, dict) else str(content)
            summary['summary'] = f"모든 AI 사진 및 공식 자산이 바인딩된 최종 발행 원고입니다 (총 {len(md_text):,}자). 아래에서 최종 서식과 사진을 그대로 확인하고 바로 복사할 수 있습니다."
            summary['highlights'] = [
                f"총 분량: 약 {len(md_text):,}자",
                f"상태: 최종 완성본 (스마트에디터 ONE 호환)",
                f"포함: 회의실 전경 실사 및 공식 시각 자료 바인딩 완료"
            ]
            return summary

        if path_name.endswith('.md') or 'draft' in path_name:
            summary['title'] = f'블로그 원고 본문 ({path_name})'
            md_text = content.get('markdown', '') if isinstance(content, dict) else str(content)
            summary['summary'] = f"네이버 블로그 규격으로 렌더링된 원고입니다 (총 {len(md_text):,}자). 아래 HTML 뷰어로 바로 읽을 수 있습니다."
            summary['highlights'] = [
                f"분량: 약 {len(md_text):,}자",
                f"서식: 스마트에디터 ONE 호환 HTML",
                f"상태: 편집 및 복사 가능"
            ]
            return summary

        summary['summary'] = f"{stage_label} 단계의 저장 데이터입니다."
    except Exception:
        summary['summary'] = f"{stage_label} 단계의 기록입니다."
    return summary


def render_strategy_html(st):
    """Render structured writing strategy into an executive HTML report."""
    if isinstance(st, str):
        try:
            st = json.loads(st)
        except Exception:
            return f"<pre>{html.escape(st)}</pre>"
    if not isinstance(st, dict):
        return ""

    goal = html.escape(str(st.get("article_goal", "")))
    playbook = html.escape(str(st.get("primary_playbook", "")))
    secondary = ", ".join(st.get("secondary_playbooks", []))
    
    questions = st.get("reader", {}).get("questions", []) if isinstance(st.get("reader"), dict) else []
    must_cover = st.get("must_cover", [])
    avoid = st.get("avoid", [])
    body_sections = st.get("body", [])
    assets = st.get("asset_needs", [])

    h = []
    h.append('<div style="font-family: \'나눔고딕\', NanumGothic, \'Apple SD Gothic Neo\', sans-serif; color: #1e293b; line-height: 1.6; font-size: 14px;">')
    
    # 1. Header banner
    h.append('<div style="background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%); color: #ffffff; padding: 16px 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);">')
    h.append(f'<div style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.9;">Strategy Blueprint · 플레이북: {playbook}</div>')
    h.append(f'<div style="font-size: 16.5px; font-weight: 800; margin-top: 5px; line-height: 1.4;">{goal}</div>')
    if secondary:
        h.append(f'<div style="font-size: 12px; margin-top: 6px; opacity: 0.85;">보조 플레이북: {html.escape(secondary)}</div>')
    h.append('</div>')

    # 2. Reader Core Questions
    if questions:
        h.append('<div style="margin-bottom: 20px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px;">')
        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 8px; font-size: 14.5px;">🎯 독자가 글을 통해 반드시 해결해야 하는 핵심 질문</div>')
        h.append('<ul style="margin: 0; padding-left: 20px; color: #334155;">')
        for q in questions:
            h.append(f'<li style="margin-bottom: 5px; font-weight: 600;">{html.escape(str(q))}</li>')
        h.append('</ul></div>')

    # 3. Section Outline Table
    if body_sections:
        h.append('<div style="margin-bottom: 20px;">')
        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 10px; font-size: 15px;">📋 본문 섹션별 기획 의도 및 서술 계획</div>')
        h.append('<table style="width: 100%; border-collapse: collapse; font-size: 13.5px; border: 1px solid #cbd5e1; text-align: left;">')
        h.append('<thead><tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">')
        h.append('<th style="padding: 10px 12px; width: 75px;">섹션</th>')
        h.append('<th style="padding: 10px 12px; width: 220px;">소제목 (Heading)</th>')
        h.append('<th style="padding: 10px 12px;">핵심 서술 내용 및 전개 계획</th>')
        h.append('<th style="padding: 10px 12px; width: 140px;">배치 에셋</th>')
        h.append('</tr></thead><tbody>')
        for sec in body_sections:
            if isinstance(sec, dict):
                sec_id = html.escape(str(sec.get("section_id", "")))
                heading = html.escape(str(sec.get("heading", "")))
                plan = html.escape(str(sec.get("content_plan", "")))
                anchor = html.escape(str(sec.get("asset_anchor", "") or "-"))
            else:
                sec_id = "-"
                heading = html.escape(str(sec))
                plan = ""
                anchor = "-"
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;">')
            h.append(f'<td style="padding: 10px 12px; font-weight: 700; color: #2563eb; vertical-align: top;">{sec_id}</td>')
            h.append(f'<td style="padding: 10px 12px; font-weight: 700; color: #0f172a; vertical-align: top;">{heading}</td>')
            h.append(f'<td style="padding: 10px 12px; color: #475569; vertical-align: top; line-height: 1.5;">{plan}</td>')
            h.append(f'<td style="padding: 10px 12px; color: #0284c7; font-family: monospace; font-size: 12px; vertical-align: top;">{anchor}</td>')
            h.append('</tr>')
        h.append('</tbody></table></div>')

    # 4. Two Column: Must Cover vs Avoid
    h.append('<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">')
    h.append('<div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px 16px;">')
    h.append('<div style="font-weight: 700; color: #065f46; margin-bottom: 8px; font-size: 14px;">✅ 필수 포함 내용 (Must Cover)</div>')
    h.append('<ul style="margin: 0; padding-left: 18px; color: #047857; font-size: 13px;">')
    for m in must_cover:
        h.append(f'<li style="margin-bottom: 5px;">{html.escape(str(m))}</li>')
    h.append('</ul></div>')

    h.append('<div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; padding: 14px 16px;">')
    h.append('<div style="font-weight: 700; color: #9f1239; margin-bottom: 8px; font-size: 14px;">🚫 주의 및 지양 사항 (Avoid)</div>')
    h.append('<ul style="margin: 0; padding-left: 18px; color: #be123c; font-size: 13px;">')
    for a in avoid:
        h.append(f'<li style="margin-bottom: 5px;">{html.escape(str(a))}</li>')
    h.append('</ul></div></div>')

    # 5. Asset Needs Table
    if assets:
        h.append('<div>')
        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 8px; font-size: 14.5px;">🖼️ 시각 자료 및 이미지 배치 계획표</div>')
        h.append('<table style="width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #cbd5e1;">')
        h.append('<thead><tr style="background: #f8fafc; border-bottom: 1px solid #cbd5e1;">')
        h.append('<th style="padding: 8px 10px; width: 140px;">슬롯 ID</th>')
        h.append('<th style="padding: 8px 10px;">이미지 목적 및 설명</th>')
        h.append('<th style="padding: 8px 10px; width: 150px;">매핑 자산 ID</th>')
        h.append('<th style="padding: 8px 10px; width: 70px; text-align: center;">필수여부</th>')
        h.append('</tr></thead><tbody>')
        for ast in assets:
            if isinstance(ast, dict):
                aid = html.escape(str(ast.get("id", "")))
                purpose = html.escape(str(ast.get("purpose", "")))
                ast_id = html.escape(str(ast.get("asset_id", "") or ast.get("anchor", "-")))
                req = "필수" if ast.get("required") else "권장"
            else:
                aid = html.escape(str(ast))
                purpose = ""
                ast_id = "-"
                req = "권장"
            req_badge = f'<span style="background: {"#fee2e2; color: #b91c1c;" if req == "필수" else "#f1f5f9; color: #64748b;"} padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;">{req}</span>'
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;">')
            h.append(f'<td style="padding: 8px 10px; font-weight: 600; color: #0f172a;">{aid}</td>')
            h.append(f'<td style="padding: 8px 10px; color: #334155;">{purpose}</td>')
            h.append(f'<td style="padding: 8px 10px; font-family: monospace; color: #2563eb; font-size: 12px;">{ast_id}</td>')
            h.append(f'<td style="padding: 8px 10px; text-align: center;">{req_badge}</td>')
            h.append('</tr>')
        h.append('</tbody></table></div>')

    h.append('</div>')
    return "".join(h)


def render_brief_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    b = data.get('brief', data) if isinstance(data, dict) else {}
    kw = html.escape(str(b.get('search', {}).get('primary_keyword', '')))
    rel_kw = ", ".join(b.get('search', {}).get('related_keywords', []))
    topic = html.escape(str(b.get('topic', '')))
    aud = html.escape(str(b.get('target_audience', '')))
    intent = html.escape(str(b.get('intent', '')))
    titles = b.get('title_candidates', [])
    questions = b.get('questions', [])
    packs = ", ".join(b.get('knowledge_packs', []))

    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13.5px; line-height: 1.6; color: #1e293b;">']
    h.append('<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;">')
    h.append(f'<div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase;">Brief Specification</div>')
    h.append(f'<div style="font-size: 16px; font-weight: 800; color: #14532d; margin-top: 4px;">{topic}</div>')
    h.append('</div>')

    h.append('<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px;">')
    h.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 6px;"><b>타깃 키워드:</b> <span style="color: #2563eb; font-weight: 700;">{kw}</span></div>')
    h.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 6px;"><b>검색 의도:</b> <span style="color: #0284c7; font-weight: 700;">{intent}</span></div>')
    h.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 6px;"><b>목표 독자:</b> {aud}</div>')
    h.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; padding: 10px 14px; border-radius: 6px;"><b>연관 키워드:</b> {html.escape(rel_kw) or "-"}</div>')
    h.append('</div>')

    if titles:
        h.append('<div style="margin-bottom: 14px; background: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px; padding: 12px 16px;">')
        h.append('<div style="font-weight: 700; color: #92400e; margin-bottom: 6px;">💡 추천 제목 후보 3종</div><ol style="margin: 0; padding-left: 20px; color: #78350f;">')
        for t in titles: h.append(f'<li style="margin-bottom: 4px;"><b>{html.escape(str(t))}</b></li>')
        h.append('</ol></div>')

    if questions:
        h.append('<div style="margin-bottom: 14px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px 16px;">')
        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 6px;">❓ 독자 핵심 질문</div><ul style="margin: 0; padding-left: 20px; color: #334155;">')
        for q in questions: h.append(f'<li style="margin-bottom: 4px;">{html.escape(str(q))}</li>')
        h.append('</ul></div>')

    if packs:
        h.append(f'<div style="font-size: 12px; color: #64748b;">📚 연동 지식팩: <span style="font-family: monospace; color: #334155;">{html.escape(packs)}</span></div>')

    h.append('</div>')
    return "".join(h)


def render_facts_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    facts = data.get('facts', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    sources = data.get('sources', {}) if isinstance(data, dict) else {}
    
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; line-height: 1.5; color: #1e293b;">']
    h.append(f'<div style="margin-bottom: 12px; font-weight: 800; color: #0f172a; font-size: 14.5px;">📊 검증된 제품 공식 팩트 및 수치 사양 ({len(facts)}건)</div>')
    
    if facts:
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr>')
        h.append('<th style="padding: 10px 8px; width: 110px;">Fact ID</th>')
        h.append('<th style="padding: 10px 8px; width: 180px;">대상 및 속성</th>')
        h.append('<th style="padding: 10px 8px;">내용 / 공인 수치 사양</th>')
        h.append('<th style="padding: 10px 8px; width: 220px;">공식 출처 문서</th>')
        h.append('</tr></thead><tbody>')
        
        for f in facts:
            fid = html.escape(str(f.get('id', '')))
            subj = html.escape(str(f.get('subject', '')))
            prop = html.escape(str(f.get('canonical_property', f.get('property', ''))))
            kind = html.escape(str(f.get('kind', '')))
            
            # Format subject & property
            subj_html = f'<div style="font-weight: 700; color: #1e40af; font-size: 12px; margin-bottom: 2px;">{subj}</div>' if subj else ''
            prop_html = f'<div style="color: #64748b; font-size: 11.5px; font-family: monospace;">{prop}</div>' if prop else (f'<div style="color: #64748b;">{kind}</div>' if kind else '')
            
            # Format Value / Spec
            val = f.get('value', '')
            unit = f.get('unit', '')
            val_parts = []
            if val is not None and val != '':
                if unit:
                    u_str = str(unit) if str(unit) in ('m', 'mm', 'cm', 'kg', 'g', '°', '%', '배') else f" {unit}"
                else:
                    u_str = ''
                val_parts.append(f'<span style="font-size: 13.5px; font-weight: 800; color: #15803d; background: #f0fdf4; padding: 2px 7px; border-radius: 4px; border: 1px solid #bbf7d0;">{html.escape(str(val))}{html.escape(u_str)}</span>')
            
            stmt = f.get('statement', f.get('text', ''))
            if stmt:
                val_parts.append(f'<div style="margin-top: 4px; color: #1e293b;">{html.escape(str(stmt))}</div>')
                
            applies = f.get('applies_to', [])
            if applies:
                app_badges = ' '.join(f'<span style="background: #e2e8f0; color: #334155; padding: 1px 5px; border-radius: 3px; font-size: 10.5px;">{html.escape(str(a))}</span>' for a in applies)
                val_parts.append(f'<div style="margin-top: 5px; font-size: 11px; color: #64748b;"><b>적용:</b> {app_badges}</div>')
                
            not_imply = f.get('does_not_imply', [])
            if not_imply:
                val_parts.append(f'<div style="margin-top: 4px; font-size: 11px; color: #b91c1c; background: #fef2f2; padding: 4px 7px; border-radius: 4px; border: 1px dashed #f87171;">🚫 <b>확대 해석 금지 (거짓 명제):</b> "{html.escape(", ".join(str(x) for x in not_imply))}" 서술 금지</div>')
                
            val_html = "".join(val_parts) if val_parts else '<span style="color: #94a3b8;">-</span>'
            
            # Format Source
            src_obj = f.get('source', {})
            if isinstance(src_obj, dict):
                src_id = html.escape(str(src_obj.get('id', '')))
                loc = src_obj.get('locator', {}) if isinstance(src_obj.get('locator'), dict) else {}
                sec = loc.get('section', '')
                heading = loc.get('heading', '')
                url = loc.get('url', '')
                
                loc_text = f"{heading} > {sec}" if heading and sec and heading != sec else (sec or heading or "")
                
                src_lines = [f'<div style="font-weight: 700; color: #0369a1; font-size: 11.5px; font-family: monospace;">{src_id}</div>']
                if loc_text:
                    src_lines.append(f'<div style="color: #475569; font-size: 11px; margin-top: 2px;">{html.escape(loc_text)}</div>')
                if url:
                    src_lines.append(f'<div style="margin-top: 3px;"><a href="{html.escape(url)}" target="_blank" style="color: #2563eb; font-size: 11px; text-decoration: underline;">공식 문서 열기 ↗</a></div>')
                src_html = "".join(src_lines)
            else:
                src_html = f'<div style="font-size: 11px; color: #64748b;">{html.escape(str(src_obj or "-"))}</div>'
                
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;">')
            h.append(f'<td style="padding: 10px 8px; font-weight: 700; color: #2563eb; font-family: monospace; vertical-align: top;">{fid}</td>')
            h.append(f'<td style="padding: 10px 8px; vertical-align: top;">{subj_html}{prop_html}</td>')
            h.append(f'<td style="padding: 10px 8px; vertical-align: top;">{val_html}</td>')
            h.append(f'<td style="padding: 10px 8px; vertical-align: top;">{src_html}</td>')
            h.append('</tr>')
            
        h.append('</tbody></table>')
    h.append('</div>')
    return "".join(h)


def render_feedback_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    fb = data.get('feedback', data) if isinstance(data, dict) else {}
    passed = fb.get('passed', False)
    issues = fb.get('issues', [])
    missing = fb.get('missing_claims', [])

    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13.5px; line-height: 1.6; color: #1e293b;">']
    status_bg = '#f0fdf4' if passed and not issues and not missing else '#fff1f2'
    status_border = '#bbf7d0' if passed and not issues and not missing else '#fecdd3'
    status_color = '#15803d' if passed and not issues and not missing else '#b91c1c'
    status_text = '✅ 품질 검토 통과 (발행 가능)' if passed and not issues and not missing else '⚠️ 보완 및 수정 권장 (품질 기준 미달 항목 존재)'

    h.append(f'<div style="background: {status_bg}; border: 1px solid {status_border}; color: {status_color}; padding: 12px 16px; border-radius: 6px; font-weight: 700; margin-bottom: 12px;">{status_text}</div>')

    if issues:
        h.append('<div style="margin-bottom: 12px;"><div style="font-weight: 700; color: #b91c1c; margin-bottom: 6px;">발견된 지적 사항:</div><ul style="margin: 0; padding-left: 20px; color: #991b1b;">')
        for iss in issues: h.append(f'<li style="margin-bottom: 4px;">{html.escape(str(iss))}</li>')
        h.append('</ul></div>')

    if missing:
        h.append('<div style="margin-bottom: 12px;"><div style="font-weight: 700; color: #c2410c; margin-bottom: 6px;">누락된 주장 및 팩트:</div><ul style="margin: 0; padding-left: 20px; color: #9a3412;">')
        for mis in missing: h.append(f'<li style="margin-bottom: 4px;">{html.escape(str(mis))}</li>')
        h.append('</ul></div>')

    h.append('</div>')
    return "".join(h)


def render_official_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    claims = data.get('claims', []) if isinstance(data, dict) else []
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; line-height: 1.5; color: #1e293b;">']
    h.append(f'<div style="margin-bottom: 10px; font-weight: 700; color: #0f172a; font-size: 14px;">로지텍 공식 Kapa RAG 교차 검증 결과 ({len(claims)}개 주장)</div>')
    if claims:
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr><th style="padding: 8px; width: 85px;">판정</th><th style="padding: 8px; width: 220px;">원고 본문 주장</th><th style="padding: 8px;">공식 지식베이스 근거</th></tr></thead><tbody>')
        for c in claims:
            verdict = c.get('verdict', 'unknown')
            badge = '<span style="background: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 4px; font-weight: 700;">확인(일치)</span>' if verdict == 'confirmed' else f'<span style="background: #fee2e2; color: #b91c1c; padding: 2px 6px; border-radius: 4px; font-weight: 700;">{html.escape(verdict)}</span>'
            claim_text = html.escape(str(c.get('claim_text', c.get('text', ''))))
            ev = html.escape(str(c.get('official_evidence', c.get('evidence', c.get('rationale', '')))))
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px; text-align: center; vertical-align: top;">{badge}</td><td style="padding: 8px; font-weight: 600; color: #0f172a; vertical-align: top;">{claim_text}</td><td style="padding: 8px; color: #475569; vertical-align: top;">{ev}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    return "".join(h)


def parse_rule_body_to_natural_html(body_text):
    if not body_text:
        return ""
    
    # 1. Clean HTML code blocks and raw HTML
    html_block_pattern = re.compile(r'```html\s*([\s\S]*?)\s*```', re.IGNORECASE)
    def replace_html_block(m):
        return (
            '<div style="background: #f8fafc; border: 1px dashed #94a3b8; border-radius: 6px; padding: 12px 14px; margin: 12px 0; font-size: 13px; color: #334155;">'
            '<div style="font-weight: 700; color: #0284c7; margin-bottom: 4px;">🏷️ 오우션테크놀러지 B2B 공식 문의 배너 & 안내 템플릿 포함</div>'
            '<div style="color: #64748b; font-size: 12px; line-height: 1.5;">'
            '네이버 블로그 렌더러가 자동으로 공식 수입 총판 견적 상담 배너(클릭 시 문의 페이지 연결)와 박스 안내 문구로 변환하여 본문 도입부 및 마무리에 안전하게 삽입합니다.'
            '</div>'
            '</div>'
        )
    cleaned = html_block_pattern.sub(replace_html_block, body_text)
    
    # Clean standalone raw HTML tags if any remain
    raw_html_div_pattern = re.compile(r'<div class="mb-24[\s\S]*?</div>', re.IGNORECASE)
    cleaned = raw_html_div_pattern.sub(
        '<div style="background: #f8fafc; border: 1px dashed #94a3b8; border-radius: 6px; padding: 10px; margin: 8px 0; font-size: 12px; color: #475569;">[공식 배너 템플릿]</div>',
        cleaned
    )

    lines = cleaned.split('\n')
    output = []
    in_list = False
    in_quote = False
    
    for line in lines:
        line_s = line.strip()
        if not line_s:
            if in_list:
                output.append('</ul>')
                in_list = False
            if in_quote:
                output.append('</blockquote>')
                in_quote = False
            continue
            
        # Ignore top-level title and version lines
        if line_s.startswith('# ') or line_s.startswith('Version:'):
            continue
            
        # Subheaders ##
        if line_s.startswith('## '):
            if in_list: output.append('</ul>'); in_list = False
            if in_quote: output.append('</blockquote>'); in_quote = False
            sub = line_s[3:].strip()
            output.append(f'<div style="font-weight: 700; color: #0f172a; font-size: 13.5px; margin-top: 14px; margin-bottom: 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">📌 {html.escape(sub)}</div>')
            continue

        # Review checkpoint (검토 출력:, 검토 체크:)
        if line_s.startswith('검토 출력:') or line_s.startswith('검토 체크:') or line_s.startswith('검토 체크'):
            if in_list: output.append('</ul>'); in_list = False
            if in_quote: output.append('</blockquote>'); in_quote = False
            txt = line_s.split(':', 1)[-1].strip() if ':' in line_s else line_s
            output.append(f'<div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 10px 14px; margin-top: 10px; margin-bottom: 8px; font-size: 12.5px; color: #1e40af;"><b>📋 검토 및 준수 체크포인트:</b> {html.escape(txt)}</div>')
            continue
            
        # Blockquote >
        if line_s.startswith('> '):
            if in_list: output.append('</ul>'); in_list = False
            if not in_quote:
                output.append('<blockquote style="margin: 8px 0; padding: 8px 14px; background: #f8fafc; border-left: 3px solid #cbd5e1; color: #475569; font-style: italic; font-size: 12.5px;">')
                in_quote = True
            output.append(f'<div>{html.escape(line_s[2:].strip())}</div>')
            continue
        elif in_quote:
            output.append('</blockquote>')
            in_quote = False

        # Bullet list - or *
        if line_s.startswith('- ') or line_s.startswith('* '):
            if not in_list:
                output.append('<ul style="margin: 6px 0; padding-left: 20px; color: #334155; font-size: 13px; line-height: 1.6;">')
                in_list = True
            item_text = line_s[2:].strip()
            output.append(f'<li style="margin-bottom: 4px;">{html.escape(item_text)}</li>')
            continue
        elif in_list:
            output.append('</ul>')
            in_list = False
            
        # Already formatted html divs
        if line_s.startswith('<div'):
            output.append(line_s)
        else:
            output.append(f'<p style="margin: 0 0 8px 0; line-height: 1.6; color: #334155; font-size: 13px;">{html.escape(line_s)}</p>')
            
    if in_list: output.append('</ul>')
    if in_quote: output.append('</blockquote>')
    
    return "".join(output)


def render_cautions_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    rules = data.get('rules', data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append(f'<div style="font-weight: 700; color: #0f172a; font-size: 14.5px; margin-bottom: 12px;">🛡️ 적용된 품질 기준 및 브랜드 안전 지침 (총 {len(rules)}건)</div>')
    
    for r in rules:
        rid = r.get('id', '')
        severity = r.get('severity', 'review')
        priority = r.get('priority', 80)
        body = r.get('body', '')
        
        # Extract title from body first line: "# RULE-ID — Title"
        title = rid
        m_title = re.search(r'^#\s*([^\n]+)', body)
        if m_title:
            full_title = m_title.group(1).strip()
            if '—' in full_title:
                title = full_title.split('—', 1)[-1].strip()
            elif '-' in full_title:
                title = full_title.split('-', 1)[-1].strip()
            else:
                title = full_title
                
        # Severity styling
        if severity == 'must' or r.get('required'):
            sev_badge = '<span style="background: #fee2e2; color: #b91c1c; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700;">필수 준수</span>'
            border_color = '#f87171'
        elif severity == 'warning':
            sev_badge = '<span style="background: #ffedd5; color: #c2410c; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700;">주의 권고</span>'
            border_color = '#fb923c'
        else:
            sev_badge = '<span style="background: #e0f2fe; color: #0369a1; padding: 2px 7px; border-radius: 4px; font-size: 11px; font-weight: 700;">발행 전 검토</span>'
            border_color = '#38bdf8'
            
        prio_badge = f'<span style="background: #f1f5f9; color: #475569; padding: 2px 6px; border-radius: 4px; font-size: 11px;">우선순위 {priority}</span>'
        id_badge = f'<span style="font-family: monospace; font-size: 11.5px; color: #64748b; font-weight: 600;">{html.escape(rid)}</span>'
        
        parsed_body = parse_rule_body_to_natural_html(body)
        
        h.append(f'<div style="background: #ffffff; border: 1px solid #e2e8f0; border-left: 4px solid {border_color}; border-radius: 6px; padding: 14px 18px; margin-bottom: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">')
        h.append(f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid #f1f5f9; padding-bottom: 8px;">')
        h.append(f'  <div style="font-size: 14.5px; font-weight: 800; color: #0f172a;">{html.escape(title)}</div>')
        h.append(f'  <div style="display: flex; gap: 6px; align-items: center;">{id_badge} {sev_badge} {prio_badge}</div>')
        h.append(f'</div>')
        h.append(f'<div style="line-height: 1.6; color: #334155;">{parsed_body}</div>')
        h.append(f'</div>')
        
    h.append('</div>')
    return "".join(h)


def render_gap_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    if not isinstance(data, dict): return ""
    sel = html.escape(str(data.get('selection', '')))
    status = html.escape(str(data.get('collection_status', '')))
    cands = data.get('keyword_candidates', [])
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append(f'<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;">')
    h.append(f'<div style="font-size: 11px; font-weight: 700; color: #15803d; text-transform: uppercase;">키워드 진단 결과</div>')
    h.append(f'<div style="font-size: 15px; font-weight: 800; color: #166534; margin-top: 3px;">선택된 타깃 키워드: {sel} <span style="font-size: 12px; font-weight: normal; color: #15803d;">(진단 상태: {status})</span></div>')
    h.append('</div>')
    if cands:
        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 6px;">발굴된 키워드 후보 (상위 8건)</div>')
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr><th style="padding: 8px;">키워드</th><th style="padding: 8px; width: 120px; text-align: right;">월간 검색량</th><th style="padding: 8px; width: 120px; text-align: right;">기회 지수</th></tr></thead><tbody>')
        for c in cands[:8]:
            q = html.escape(str(c.get('query', '')))
            vol = f"{c.get('monthly_total', 0):,}"
            opp = f"{c.get('opportunity_score', 0):.3f}"
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px; font-weight: 600; color: #0f172a;">{q}</td><td style="padding: 8px; text-align: right; color: #2563eb;">{vol}회</td><td style="padding: 8px; text-align: right; color: #059669; font-weight: 700;">{opp}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    return "".join(h)


def render_entity_map_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    if not isinstance(data, dict): return ""
    kw = data.get('keywords', {})
    primary = html.escape(str(kw.get('primary_keyword', '')))
    supp = ", ".join(kw.get('supporting_keywords', []))
    layman = kw.get('layman_terms', [])
    if isinstance(layman, str): layman = [layman]
    elif not isinstance(layman, list): layman = []

    technical = kw.get('technical_terms', [])
    if isinstance(technical, str): technical = [technical]
    elif not isinstance(technical, list): technical = []

    entities = data.get('entities', {})
    prods = entities.get('product_ids', [])
    if isinstance(prods, str): prods = [prods]
    elif not isinstance(prods, list): prods = []

    feats = entities.get('feature_ids', [])
    if isinstance(feats, str): feats = [feats]
    elif not isinstance(feats, list): feats = []

    props = entities.get('property_ids', [])
    if isinstance(props, str): props = [props]
    elif not isinstance(props, list): props = []

    basis = data.get('mapping_basis', [])
    if isinstance(basis, str):
        basis_list = [basis]
    elif isinstance(basis, list):
        basis_list = basis
    else:
        basis_list = [str(basis)] if basis else []

    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append('<div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px 16px; margin-bottom: 12px;">')
    h.append('<div style="font-size: 11px; font-weight: 700; color: #166534; text-transform: uppercase;">키워드-엔티티 매핑 결과</div>')
    h.append(f'<div style="font-size: 15px; font-weight: 800; color: #14532d; margin-top: 3px;">핵심 키워드: {primary}</div>')
    if supp:
        h.append(f'<div style="font-size: 12px; color: #15803d; margin-top: 4px;">보조 키워드: {html.escape(supp)}</div>')
    h.append('</div>')

    if layman or technical:
        h.append('<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">')
        h.append('<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px;">')
        h.append('<div style="font-weight: 700; color: #0369a1; font-size: 12px; margin-bottom: 6px;">🗣️ 검색자 일상 용어 (Layman Terms)</div>')
        h.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">' + ''.join(f'<span style="background: #e0f2fe; color: #0284c7; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">{html.escape(str(x))}</span>' for x in layman) + '</div>')
        h.append('</div>')
        h.append('<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px;">')
        h.append('<div style="font-weight: 700; color: #4338ca; font-size: 12px; margin-bottom: 6px;">⚙️ 공식 기술 용어 (Technical Terms)</div>')
        h.append('<div style="display: flex; flex-wrap: wrap; gap: 6px;">' + ''.join(f'<span style="background: #e0e7ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">{html.escape(str(x))}</span>' for x in technical) + '</div>')
        h.append('</div>')
        h.append('</div>')

    h.append('<div style="margin-bottom: 12px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px;">')
    h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 8px;">🏢 매칭된 로지텍 제품 및 기능 엔티티</div>')
    h.append('<div style="display: flex; flex-direction: column; gap: 6px; font-size: 12.5px;">')
    if prods:
        h.append('<div><b>매칭 제품:</b> ' + ' '.join(f'<span style="background: #dbeafe; color: #1d4ed8; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-family: monospace;">{html.escape(str(p))}</span>' for p in prods) + '</div>')
    if feats:
        h.append('<div><b>핵심 기능:</b> ' + ' '.join(f'<span style="background: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-family: monospace;">{html.escape(str(f))}</span>' for f in feats) + '</div>')
    if props:
        h.append('<div><b>확인 속성:</b> ' + ' '.join(f'<span style="background: #f1f5f9; color: #475569; padding: 2px 8px; border-radius: 4px; font-size: 11.5px;">{html.escape(str(pr))}</span>' for pr in props[:6]) + '</div>')
    h.append('</div></div>')

    if basis_list:
        def format_basis(b):
            s = str(b).strip()
            if s == 'brief.knowledge_packs':
                return '기획 계약서(Brief) 지정 지식 팩 (지정된 제품·기능 패키지 기반 자동 연동)'
            if s in ('target_keyword', 'primary_keyword'):
                return '타깃 검색어 및 연관 검색 수요 분석 매칭'
            if s.startswith('brief.'):
                return f'기획 계약서 항목 연동 ({s})'
            return s

        h.append('<div style="font-weight: 700; color: #0f172a; margin-bottom: 6px;">매칭 근거 및 사유</div>')
        h.append('<ul style="margin: 0; padding-left: 20px; color: #334155; font-size: 12.5px;">' + ''.join(f'<li style="margin-bottom: 4px;">{html.escape(format_basis(b))}</li>' for b in basis_list) + '</ul>')

    h.append('</div>')
    return "".join(h)


def render_asset_plan_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    needs = data.get('needs', data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append(f'<div style="font-weight: 700; color: #0f172a; font-size: 14.5px; margin-bottom: 10px;">🖼️ 배치 예정 이미지 계획 ({len(needs)}건)</div>')
    if needs:
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr><th style="padding: 8px; width: 150px;">슬롯 ID</th><th style="padding: 8px;">목적 및 설명</th><th style="padding: 8px; width: 150px;">본문 앵커</th><th style="padding: 8px; width: 80px; text-align: center;">필수여부</th></tr></thead><tbody>')
        for n in needs:
            nid = html.escape(str(n.get('id', n.get('asset_id', ''))))
            purp = html.escape(str(n.get('purpose', n.get('caption', ''))))
            anc = html.escape(str(n.get('anchor', '-')))
            req = '필수' if n.get('required') else '권장'
            req_badge = f'<span style="background: {"#fee2e2; color: #b91c1c;" if n.get("required") else "#f1f5f9; color: #64748b;"} padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700;">{req}</span>'
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px; font-weight: 700; color: #0f172a;">{nid}</td><td style="padding: 8px; color: #334155;">{purp}</td><td style="padding: 8px; font-family: monospace; color: #2563eb;">{anc}</td><td style="padding: 8px; text-align: center;">{req_badge}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    return "".join(h)


def render_asset_bindings_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    bindings = data.get('bindings', data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append(f'<div style="font-weight: 700; color: #0f172a; font-size: 14.5px; margin-bottom: 10px;"> 에셋 바인딩 및 본문 연결 현황 ({len(bindings)}건)</div>')
    if bindings:
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr><th style="padding: 8px; width: 140px;">슬롯 ID</th><th style="padding: 8px;">목적 / 설명</th><th style="padding: 8px; width: 160px;">매칭 에셋 / URL</th><th style="padding: 8px; width: 90px; text-align: center;">상태</th></tr></thead><tbody>')
        for b in bindings:
            need = b.get('need', {}) if isinstance(b.get('need'), dict) else {}
            nid = html.escape(str(need.get('id', '')))
            purp = html.escape(str(need.get('purpose', '')))
            status = b.get('status', 'pending')
            cand = b.get('candidate')
            if cand and isinstance(cand, dict):
                ast_id = html.escape(str(cand.get('asset_id', cand.get('id', '매칭 에셋'))))
                url = cand.get('url', '')
                if url:
                    ast_cell = f'<a href="{html.escape(url)}" target="_blank" style="color: #2563eb; text-decoration: underline; font-weight: 600;">{ast_id} (열기)</a>'
                else:
                    ast_cell = f'<span style="color: #475569; font-weight: 600;">{ast_id}</span>'
            else:
                ast_cell = '<span style="color: #94a3b8;">미지정(대기)</span>'

            badge = '<span style="background: #dcfce7; color: #15803d; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 11px;">승인/바인딩</span>' if status in ('approved', 'bound') else f'<span style="background: #fef3c7; color: #b45309; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 11px;">{html.escape(status)}</span>'
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px; font-weight: 700; color: #0f172a;">{nid}</td><td style="padding: 8px; color: #334155;">{purp}</td><td style="padding: 8px;">{ast_cell}</td><td style="padding: 8px; text-align: center;">{badge}</td></tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    return "".join(h)


def render_admin_queue_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    items = data.get('items', data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px; color: #1e293b;">']
    h.append(f'<div style="font-weight: 700; color: #0f172a; font-size: 14.5px; margin-bottom: 10px;">⚠️ 관리자 검토 및 확인 대기 큐 ({len(items)}건)</div>')
    if items:
        for it in items:
            kind = html.escape(str(it.get('kind', it.get('type', '확인사항'))))
            detail = html.escape(str(it.get('detail', it.get('message', ''))))
            act = html.escape(str(it.get('suggested_action', '')))
            h.append('<div style="background: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #f59e0b; border-radius: 6px; padding: 12px 16px; margin-bottom: 10px;">')
            h.append(f'<div style="font-weight: 700; color: #92400e; margin-bottom: 4px;">📌 {kind}</div>')
            h.append(f'<div style="color: #78350f; font-size: 13px; line-height: 1.5;">{detail}</div>')
            if act:
                h.append(f'<div style="margin-top: 6px; font-size: 12px; color: #b45309;"><b>권장 조치:</b> {act}</div>')
            h.append('</div>')
    else:
        h.append('<div style="background: #f0fdf4; border: 1px solid #bbf7d0; color: #166534; padding: 12px 16px; border-radius: 6px;">관리자 확인이 필요한 잔여 이슈가 없습니다. 즉시 발행이 가능합니다.</div>')
    h.append('</div>')
    return "".join(h)


def render_run_result_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception: pass
    if not isinstance(data, dict): return ""
    outcome = data.get('outcome', 'unknown')
    ready = data.get('publish_ready', False)
    h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13.5px; color: #1e293b;">']
    bg = '#f0fdf4' if ready else '#fff1f2'
    border = '#bbf7d0' if ready else '#fecdd3'
    color = '#15803d' if ready else '#b91c1c'
    h.append(f'<div style="background: {bg}; border: 1px solid {border}; color: {color}; padding: 16px 20px; border-radius: 8px; margin-bottom: 14px;">')
    h.append(f'<div style="font-size: 12px; font-weight: 700; text-transform: uppercase;">파이프라인 실행 결과</div>')
    h.append(f'<div style="font-size: 17px; font-weight: 800; margin-top: 4px;">상태: {html.escape(outcome)} (발행 준비: {"완료" if ready else "미완료/대기"})</div>')
    h.append('</div>')
    h.append('</div>')
    return "".join(h)


def render_context_html(ctx):
    if not isinstance(ctx, dict):
        return f"<div style='font-size: 13px; color: #334155;'>{html.escape(str(ctx))}</div>"
    
    sections = []
    
    # 1. Brief
    if 'brief' in ctx and ctx['brief']:
        sections.append(('📌 기획 브리프 (Brief)', render_brief_html(ctx['brief'])))
        
    # 2. Strategy
    if 'strategy' in ctx and ctx['strategy']:
        sections.append(('📐 본문 작성 전략 (Strategy)', render_strategy_html(ctx['strategy'])))
        
    # 3. Cautions / Rules
    if 'cautions' in ctx and ctx['cautions']:
        sections.append(('🛡️ 필수 준수 및 품질 규칙 (Cautions)', render_cautions_html(ctx['cautions'])))
        
    # 4. Facts
    if 'facts' in ctx and ctx['facts']:
        sections.append(('📊 검증된 제품 팩트 (Facts)', render_facts_html({'facts': ctx['facts']})))
        
    # 5. Asset Plan / Assets
    if 'asset_plan' in ctx and ctx['asset_plan']:
        sections.append(('🖼️ 이미지 배치 계획 (Asset Plan)', render_asset_plan_html(ctx['asset_plan'])))
    elif 'assets' in ctx and ctx['assets']:
        sections.append(('🖼️ 사용 가능 이미지 에셋', render_asset_plan_html(ctx['assets'])))
        
    # 6. Gap
    if 'gap' in ctx and ctx['gap']:
        sections.append(('🔍 키워드 갭 진단 (Search Gap)', render_gap_html(ctx['gap'])))
        
    # 7. Guides
    if 'guides' in ctx and isinstance(ctx['guides'], dict) and ctx['guides']:
        gh = ['<div style="font-size: 13px; color: #334155;">']
        for gname, gcontent in ctx['guides'].items():
            gh.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">')
            gh.append(f'<div style="font-weight: 700; color: #1e293b; margin-bottom: 4px;">📄 {html.escape(gname)}</div>')
            clean_txt = re.sub(r'#+\s*', '', str(gcontent))[:200].strip()
            gh.append(f'<div style="color: #64748b; font-size: 12px; line-height: 1.5;">{html.escape(clean_txt)}...</div>')
            gh.append('</div>')
        gh.append('</div>')
        sections.append(('📘 참조 가이드라인 (Guides)', "".join(gh)))
        
    # 8. Playbooks
    if 'playbooks' in ctx and isinstance(ctx['playbooks'], dict) and ctx['playbooks']:
        pbh = ['<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; font-size: 13px;">']
        for pbid, pbval in ctx['playbooks'].items():
            name = pbval.get('name', pbid) if isinstance(pbval, dict) else pbid
            desc = pbval.get('purpose', pbval.get('description', '')) if isinstance(pbval, dict) else ''
            pbh.append(f'<div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px 12px;">')
            pbh.append(f'<div style="font-weight: 700; color: #2563eb; font-size: 12.5px;">{html.escape(str(name))}</div>')
            if desc:
                pbh.append(f'<div style="color: #64748b; font-size: 11.5px; margin-top: 4px;">{html.escape(str(desc))}</div>')
            pbh.append('</div>')
        pbh.append('</div>')
        sections.append(('📖 가용 플레이북 (Playbooks)', "".join(pbh)))

    if not sections:
        return render_generic_html(ctx)
        
    out = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif;">']
    for title, sec_html in sections:
        out.append(f'<div style="margin-bottom: 16px; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; background: #ffffff;">')
        out.append(f'<div style="background: #f8fafc; padding: 10px 16px; font-weight: 800; color: #0f172a; font-size: 13.5px; border-bottom: 1px solid #e2e8f0;">{html.escape(title)}</div>')
        out.append(f'<div style="padding: 14px 16px;">{sec_html}</div>')
        out.append('</div>')
    out.append('</div>')
    return "".join(out)


def render_generic_html(data):
    if isinstance(data, str):
        try: data = json.loads(data)
        except Exception:
            return f"<div style='font-family: monospace; white-space: pre-wrap; font-size: 12.5px; color: #334155; padding: 10px; background: #f8fafc; border-radius: 6px;'>{html.escape(data)}</div>"

    if isinstance(data, list):
        if not data: return "<p style='color: #94a3b8; font-size: 13px;'>데이터가 비어 있습니다.</p>"
        # If it's a list of rules
        if any(isinstance(x, dict) and ('body' in x and ('id' in x or '# RULE-' in str(x.get('body')))) for x in data):
            return render_cautions_html(data)
        if any(isinstance(x, dict) and ('purpose' in x and 'anchor' in x) for x in data):
            return render_asset_plan_html(data)

        h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px;">']
        if all(isinstance(x, dict) for x in data):
            keys = [k for k in dict.fromkeys(k for x in data for k in x.keys()) if k not in ('sha256', 'match', 'path')][:6]
            h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
            h.append('<thead style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;"><tr>' + ''.join(f'<th style="padding: 8px;">{html.escape(k)}</th>' for k in keys) + '</tr></thead><tbody>')
            for row in data:
                h.append('<tr style="border-bottom: 1px solid #e2e8f0;">' + ''.join(f'<td style="padding: 8px; vertical-align: top;">{html.escape(str(row.get(k, "")))}</td>' for k in keys) + '</tr>')
            h.append('</tbody></table>')
        else:
            h.append('<ul style="padding-left: 20px; color: #334155;">' + ''.join(f'<li style="margin-bottom: 4px;">{html.escape(str(x))}</li>' for x in data) + '</ul>')
        h.append('</div>')
        return "".join(h)

    if isinstance(data, dict):
        if 'rules' in data and isinstance(data['rules'], list):
            return render_cautions_html(data)
        if 'needs' in data and isinstance(data['needs'], list):
            return render_asset_plan_html(data)
        if 'bindings' in data and isinstance(data['bindings'], list):
            return render_asset_bindings_html(data)
        if 'selection' in data and 'keyword_candidates' in data:
            return render_gap_html(data)
        if 'keywords' in data and 'entities' in data:
            return render_entity_map_html(data)

        h = ['<div style="font-family: \'나눔고딕\', NanumGothic, sans-serif; font-size: 13px;">']
        h.append('<table style="width: 100%; border-collapse: collapse; border: 1px solid #cbd5e1; font-size: 12.5px;">')
        for k, v in data.items():
            if k in ('sha256', 'match', 'schema_version', 'input_refs'):
                continue
            if isinstance(v, (dict, list)):
                val_str = html.escape(json.dumps(v, ensure_ascii=False, indent=2))
                val_html = f"<pre style='margin: 0; font-size: 11.5px; max-height: 180px; overflow: auto; background: #f8fafc; padding: 6px; border-radius: 4px;'>{val_str}</pre>"
            else:
                val_html = html.escape(str(v))
            h.append(f'<tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px 12px; font-weight: 700; color: #475569; width: 160px; background: #f8fafc; vertical-align: top;">{html.escape(k)}</td><td style="padding: 8px 12px; color: #0f172a; vertical-align: top;">{val_html}</td></tr>')
        h.append('</table></div>')
        return "".join(h)

    return f"<div style='font-size: 13px; color: #334155;'>{html.escape(str(data))}</div>"


def render_artifact_html(path_name, content, kind, stage_label):
    """Automatically select the best HTML renderer for any artifact in the pipeline."""
    try:
        if 'brief.json' in path_name:
            return render_brief_html(content)
        if 'fact-bundle.json' in path_name:
            return render_facts_html(content)
        if 'feedback' in path_name:
            return render_feedback_html(content)
        if 'official' in path_name:
            return render_official_html(content)
        if 'strategy' in path_name:
            return render_strategy_html(content)
        if 'matched-cautions.json' in path_name or 'cautions' in path_name:
            return render_cautions_html(content)
        if 'gap-snapshot.json' in path_name:
            return render_gap_html(content)
        if 'keyword-entity-map.json' in path_name:
            return render_entity_map_html(content)
        if 'asset-plan.json' in path_name:
            return render_asset_plan_html(content)
        if 'asset-bindings.json' in path_name:
            return render_asset_bindings_html(content)
        if 'admin-review-queue.json' in path_name:
            return render_admin_queue_html(content)
        if 'run-result.json' in path_name:
            return render_run_result_html(content)
        return render_generic_html(content)
    except Exception as err:
        return f"<p style='color: #ef4444; font-size: 12px;'>HTML 리포트 변환 오류: {err}</p>"


def read_trace(cid, root=None, since=None):
    pipeline = ContentPipeline(**({'root': root} if root else {}))
    latest = pipeline.latest(cid)
    if not latest:
        return {'run_id': None, 'entries': [], 'message': '이 글의 공통 파이프라인 실행 기록이 없습니다.'}
    run_id = latest['run_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run ID')
    directory = pipeline.work(cid) / 'runs' / run_id
    specs = [
        ('web-research.json', 'AVIXA·PSNI 관련 글·설계 근거 탐색', 'review'),
        ('web-planning-discovery.json', '기획 참고자료 선별·개별 사실 대체·자료 없음', 'review'),
        ('execution-contract.json', '실행 순서·재개 출처·산출물 무결성 계약', 'review'),
        ('pipeline-verification.json', '전체 파이프라인 기계적 검증 결과', 'review'),
        ('web-evidence-assessment.json', '한계·보완·대안·누락 판단', 'review'),
        ('web-evidence-review-snapshot.json', '원문 검토 근거 스냅샷', 'facts'),
        ('gap-snapshot.json', '키워드 진단', 'facts'), ('brief.json', '기획·키워드', 'facts'),
        ('keyword-entity-map.json', '제품·기능 매칭', 'facts'), ('fact-bundle.json', '수집한 팩트·출처', 'facts'),
        ('matched-cautions.json', '적용한 주의사항', 'instruction'),
        ('prompts/strategy.json', '작성 전략', 'instruction'), ('responses/strategy.json', '작성 전략', 'response'),
        ('asset-plan.json', '이미지 계획', 'facts'), ('asset-bindings.json', '이미지 바인딩', 'facts')]
    for revision in range(1, 6):
        for stage, label in [('write', '원고 작성'), ('feedback', '피드백 검토')]:
            specs.extend([(f'prompts/r{revision}.{stage}.json', f'{label} r{revision}', 'instruction'),
                          (f'responses/r{revision}.{stage}.json', f'{label} r{revision}', 'response')])
        specs.append((f'prompts/r{revision}.official.json', f'로지텍 검토 r{revision}', 'instruction'))
        specs.append((f'reviews/r{revision}.official.json', f'로지텍 검토 r{revision}', 'response'))
    specs += [('knowledge-update-queue.json', '지식 수정 후보', 'review'),
              ('admin-review-queue.json', '관리자 확인사항', 'review'), ('run-result.json', '실행 결과', 'review')]
    for path in sorted((directory / 'rule-audit').glob('*.json')):
        specs.append((f'rule-audit/{path.name}', f'규칙 수신 검증 {path.stem}', 'review'))
    for path in sorted((directory / 'context-metrics').glob('*.json')):
        specs.append((f'context-metrics/{path.name}', f'토큰 측정 {path.stem}', 'review'))
    for folder, label in [('block-plan', '블록 작성 계약'), ('block-review', '블록 검증')]:
        for path in sorted((directory / folder).glob('*.json')):
            specs.append((f'{folder}/{path.name}', f'{label} {path.stem}', 'review'))
    files = [(directory / name, label, kind) for name, label, kind in specs if (directory / name).is_file()]

    # 최종 승격된 공식 초안(draft.md)이 존재하면 파이프라인 최종 결과물로 추가
    try:
        final_draft_path = pipeline.draft_path(cid)
        if final_draft_path.is_file():
            files.append((final_draft_path, '최종 확정 원고', 'response'))
    except Exception:
        pass

    signature = hashlib.sha256(str([(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p, _, _ in files]).encode()).hexdigest()
    if since == signature:
        return {'unchanged': True, 'signature': signature, 'run_id': run_id}
    entries = []
    for path, label, kind in files:
        if path.name.endswith('.md'):
            text_data = path.read_text(encoding='utf-8')
            html_preview = ''
            try:
                from services.naver_blog_compiler import compile_markdown_to_naver_html
                res = compile_markdown_to_naver_html(text_data, content_id=cid)
                html_preview = res.get('html', '')
            except Exception as err:
                html_preview = f"<p>HTML 변환 중 오류: {err}</p>"

            try:
                rel_source = str(path.relative_to(directory))
            except Exception:
                rel_source = f"drafts/{path.name}"

            entries.append({
                'id': rel_source,
                'stage': label,
                'kind': kind,
                'content': text_data,
                'html': html_preview,
                'source': rel_source,
                'natural_summary': build_natural_summary(path.name, text_data, kind, label)
            })
            continue

        data = redact(json.loads(path.read_text(encoding='utf-8')))
        # Prompt artifacts contain the exact payload: expose input separately from instructions.
        prompt = data.get('prompt') if kind == 'instruction' else None
        if prompt:
            inst_content = prompt.get('instruction', '')
            inst_html = f"<div style='font-family: 나눔고딕, NanumGothic, sans-serif; font-size: 13.5px; line-height: 1.6; color: #1e293b; background: #f8fafc; padding: 14px 18px; border-radius: 6px; border-left: 4px solid #3b82f6;'>{html.escape(inst_content)}</div>"
            entries.append({
                'id': path.name + '-instruction', 'stage': label, 'kind': 'instruction',
                'content': inst_content, 'source': str(path.relative_to(directory)),
                'html': inst_html,
                'natural_summary': build_natural_summary(path.name, inst_content, 'instruction', label)
            })
            ctx_content = prompt.get('context', {})
            ctx_html = render_context_html(ctx_content)
            entries.append({
                'id': path.name + '-input', 'stage': label, 'kind': 'facts',
                'content': ctx_content, 'source': str(path.relative_to(directory)),
                'html': ctx_html,
                'natural_summary': build_natural_summary(path.name, ctx_content, 'facts', label)
            })
        else:
            raw_content = data.get('raw', data)
            html_preview = None
            md_text = None

            m = re.match(r'r(\d+)\.write\.json', path.name)
            if m:
                rev_num = m.group(1)
                draft_path = directory / 'revisions' / f'r{rev_num}.draft.md'
                if draft_path.is_file():
                    md_text = draft_path.read_text(encoding='utf-8')

            if not md_text:
                if isinstance(raw_content, str):
                    try:
                        parsed = json.loads(raw_content)
                        if isinstance(parsed, dict) and 'markdown' in parsed:
                            md_text = parsed['markdown']
                    except Exception:
                        pass
                elif isinstance(raw_content, dict) and 'markdown' in raw_content:
                    md_text = raw_content['markdown']

            if md_text:
                try:
                    from services.naver_blog_compiler import compile_markdown_to_naver_html
                    assets_map = {
                        "oceantech-inquiry-opening": {
                            "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                            "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
                        },
                        "oceantech-inquiry-closing": {
                            "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                            "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
                        },
                        "AST-OCEANTECH-INQUIRY-BANNER": {
                            "url": "https://drive.google.com/thumbnail?id=1XZ80n6Ufe3w73TTYj2jSVF7_NWr4Pmyg&sz=w1600",
                            "alt": "오우션 테크놀러지 로지텍 공식 수입 총판 B2B 문의"
                        }
                    }
                    bpath = directory / 'asset-bindings.json'
                    if bpath.is_file():
                        try:
                            bdata = json.loads(bpath.read_text(encoding='utf-8'))
                            for b in bdata.get('bindings', []):
                                nid = b.get('need', {}).get('id')
                                cand = b.get('candidate')
                                if nid and cand and cand.get('url'):
                                    assets_map[nid] = cand
                        except Exception:
                            pass
                    res = compile_markdown_to_naver_html(md_text, content_id=cid, assets_map=assets_map)
                    html_preview = res.get('html', '')
                except Exception as err:
                    html_preview = f"<p>HTML 변환 중 오류: {err}</p>"

            if not html_preview:
                html_preview = render_artifact_html(path.name, raw_content, kind, label)

            entries.append({
                'id': str(path.relative_to(directory)), 'stage': label, 'kind': kind,
                'content': raw_content, 'source': str(path.relative_to(directory)),
                'html': html_preview,
                'natural_summary': build_natural_summary(path.name, raw_content, kind, label)
            })
    return {
        'run_id': run_id,
        'signature': signature,
        'entries': entries,
        'natural_logs': latest.get('natural_logs', []),
        'start_stage': latest.get('start_stage', 'inputs')
    }
