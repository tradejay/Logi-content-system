# 블로그 성과·자체 점수 작업 코드

현재 제품 검색 패널의 활성 평가는 `product-search-competitiveness-v1`이다. 검색 성과(0~100), 관측 범위·신뢰도, 보조 운영 지표를 분리한다. 이전 40/25/20/15 종합점수는 과거 비교·진단용으로만 남긴다. 기존 일반 블로그 진단/경쟁사 매트릭스 API는 레거시이며 새 제품 평가와 같은 점수가 아니다.

| 구분 | 코드 | 담당 |
| --- | --- | --- |
| 수집·기존 자체 평가 | blog_analyzer.py | 방문자, RSS, 검색 순위, 검색광고, 데이터랩 및 기존 점수 계산 |
| 경쟁사 비교 | competitor_engine.py | 경쟁군 수집, 상대 점수, SoV |
| 가중치 검증 | competitor_calibration.py | 동일 측정 조건의 미래 순위 검증, 자동 적용 없음 |
| 일일 추적 | daily_tracker.py | 수집 → 계산 → 기록 |
| 이력 저장 | performance_db.py | SQLite 성과 이력 |
| 주간 조회·보고 | weekly_report.py | 저장 이력 기반 요약 |

## 실행·연결
- 웹 진입: 프로젝트 루트 app.py (포트 5000).
- 일일 추적: python -m services.blog_performance.daily_tracker --blog-id oceantech01
- 주간 보고: python -m services.blog_performance.weekly_report --help
- 가중치 검증: python -m scripts.calibrate_competitor_weights
- 기존 services.* 모듈은 호환 연결만 남겼다. 평가 코드의 수정 위치는 이 폴더다.
- DB는 data/performance_history.db, data/competitor_bench.db에 유지한다. 설정도 기존 config 경로를 유지한다.

## 실제 자료와 목업 구분
- 방문자 120명 대체 및 가상 5일 변동 이력을 제거했다. 수집 실패는 점수 없음이다.
- 자동완성은 관련 검색어만 제공한다. 검색량·CTR·클릭수·경쟁도를 생성하지 않는다.
- 데이터랩 실패 또는 인증 부재 시 빈 결과와 unavailable을 반환한다. 가상 파형은 생성하지 않는다.
- 공식 API의 '< 10' 같은 구간 표기를 임의의 5로 변환하지 않는다.
- 기존 DB 이력은 실측 여부를 확정할 수 없어 보존했다. 일괄 삭제하거나 새 관측으로 재분류하지 않았다.
- 평가 알고리즘의 기존 추정값·등급·결측 처리 개선은 사용자 지침 이후 별도로 한다. C-Rank 내부 점수로 간주하지 않는다.

## 상대 비교 지표 정책

공감·댓글·이웃/구독자 반응과 증가량은 현재 평가에서 제외한다. 제품·질문별 확보 수와 실제 수정일·정보 최신성은 별도 기준 전까지 보류한다. 적용 범위·남은 코드 결함과 검증 한계는 [성과 파이프라인 가이드](../../worker-control/BLOG-PERFORMANCE.md)의 2026-10-21 절을 따른다. 새 산식·배점·가중치는 아직 정하지 않았다.

정확성 보완: 정확한 글 URL 매칭, 결측 보존, 불완전/출처 불명 비교 차단, 표본 메타데이터와 검색량 구간값 보존을 적용했다. 완전 비교에는 본문 수집도 필요하다. 세부 적용 내역은 위 파이프라인 가이드를 따른다.

## 제품별 검색 원자료 수집

`python -m services.blog_performance.collect_product_search`는 product-search-catalog.json의 승인된 27제품·54검색어에 대해 실제 네이버 검색 API 상위 최대100개와 검색광고 월간 검색량을 조회한다. 결과는 data/blog_performance/product-search/UTC실행시각 아래 원본 JSON, 검색어·게시글·제품·블로그별 CSV로 보관한다. 점수 계산·기존 DB/경쟁사 설정 변경·본문 수집은 하지 않는다. 검색어별 원자료와 제품 내 URL 중복 집계를 구분하고, 제품 혼입은 추후 검토 대상으로 남긴다. 기존 Gemini API 격리와 별개인 네이버 데이터 API만 사용한다.

## 활성 제품 검색 평가 v1 (2026-10-21)

- 실행: `python -m services.blog_performance.product_competitiveness` (최근 저장 자료만 재계산, API 호출 없음).
- 조회: 기존 app.py 서버의 `GET /api/competitors/product-scores`; `?blog_id=oceantech01`로 제품별 상세 조회.
- 산식: 검색어별 블로그 최고 순위의 역수 → 제품별 별칭 평균 → 전체 제품 동일 비중 평균 × 100.
- 검색 결과가 정상 수집된 경우에만 관측 범위 내 미노출을 0으로 처리한다. 일부 검색 실패 시 전체 점수 보류.
- 다수 글·중복 URL 추가 가산 없음. 검색량, 발행량, 글자 수, 이미지 수, 제목 주제 비율을 가산하지 않는다.
- 관측 신뢰도는 수집 성공률·키워드/제품/글 표본 수·관측 횟수와 의미 검토 상태로 표시한다. 정확도 확률로 환산하지 않는다.
- 현재 제품 의미 혼입 미검토·단일 시점이다. 잠재 C-Rank·과거 등급·지속성을 추정하지 않는다.
- 제품별 수치와 전체 패널 수치를 구별한다. 특정 브랜드만 다루는 블로그가 전체 27제품 평균에서 낮아지는 것은 범위 차이일 수 있다.
- 새 검색 수집/추가 자료 수집 완료 시 이 프로필을 자동 재계산한다. enrichment가 보관하는 옛 종합점수는 legacy diagnostic이다.

## 검색어별 순위·브랜드 편중

동일 재계산에서 query-blog-ranks.csv(미노출/실패 포함 전체 블로그×검색어), query-rankings.md(검색어별 상위10곳+오우션), brand-exposure.csv를 생성한다. 회사 식별·여러 블로그 합치기는 하지 않으며 blog_id 단위다. 브랜드 강도는 제품별 별칭 역순위 평균을 브랜드 내 제품 수로 평균하여 제품 수 차이를 보정한다. 강도 합계 대비 비중은 검색 노출 편중이며 판매·취급·실제 충성도 증거가 아니다. API는 ?query_id=Q001 또는 ?blog_id=oceantech01로 상세 조회한다.
