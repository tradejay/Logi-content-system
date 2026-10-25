"""
daily_tracker.py
================
매일 자동 실행되는 블로그 성과 추적기.

기능:
1. 등록된 모든 콘텐츠의 타겟 키워드 순위 수집
2. 블로그 전체 지수 계산 및 기록
3. 키워드 검색량 스냅샷 (주 1회)
4. 결과를 performance_db.py의 SQLite에 저장
5. 추세 분석 및 피드백 액션 생성

사용법:
  python -m services.daily_tracker --blog-id <블로그ID>
  python -m services.daily_tracker --blog-id oceantecblog --dry-run
  python -m services.daily_tracker --blog-id oceantecblog --register-only
"""
import os
import sys
import time
import json
import argparse
from datetime import datetime

# 프로젝트 루트를 path에 추가
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.blog_performance import blog_analyzer
from services.blog_performance.performance_db import (
    init_db, auto_register_from_registry,
    get_tracked_contents, record_rank, record_blog_index,
    record_keyword_volume, record_feedback,
    get_rank_trend, get_content_performance_summary,
    get_db_stats
)

# Windows 콘솔 인코딩 문제 방지
import io
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


def track_keyword_ranks(blog_id, dry_run=False):
    """모든 추적 대상 콘텐츠의 키워드 순위를 수집하고 DB에 저장."""
    cfg = blog_analyzer.load_config()
    client_id = cfg.get("naver_client_id", "").strip()
    client_secret = cfg.get("naver_client_secret", "").strip()

    contents = get_tracked_contents(active_only=True)
    contents = [c for c in contents if c.get('blog_id') == blog_id and c.get('published_url') and c.get('published_date')]
    if not contents:
        log("추적 대상 콘텐츠가 없습니다. --register-only로 먼저 등록하세요.", "WARN")
        return []

    log(f"━━━ 키워드 순위 추적 시작 ({len(contents)}개 콘텐츠) ━━━")
    all_results = []

    for content in contents:
        cid = content["content_id"]
        title = content.get("title", "")[:40]
        primary_kw = content.get("primary_keyword", "")
        supporting = content.get("supporting_keywords", [])
        layman = content.get("layman_terms", [])

        # 추적할 키워드 목록 구성 (primary + supporting 상위 3개 + layman 상위 2개)
        keywords_to_track = []
        if primary_kw:
            keywords_to_track.append(("primary", primary_kw))
        for kw in supporting[:3]:
            keywords_to_track.append(("supporting", kw))
        for kw in layman[:2]:
            keywords_to_track.append(("layman", kw))

        log(f"\n📄 {cid} | {title}")
        log(f"   추적 키워드 {len(keywords_to_track)}개: {', '.join(kw for _, kw in keywords_to_track)}")

        content_results = []
        for kw_type, keyword in keywords_to_track:
            if dry_run:
                log(f"   [DRY-RUN] {keyword} ({kw_type}) — 실제 조회 생략")
                content_results.append({
                    "keyword": keyword, "type": kw_type,
                    "rank": None, "dry_run": True
                })
                continue

            try:
                # API 호출 간 딜레이 (rate limiting 방지)
                time.sleep(1.5)

                result = blog_analyzer.check_keyword_rank(
                    keyword, blog_id, client_id, client_secret, target_url=content["published_url"]
                )

                rank = result.get("rank")
                source = result.get("source", "scraping")
                total = result.get("total_searched", 0)
                post_title = result.get("target_title")
                post_link = result.get("target_link")

                if result.get("error"):
                    raise RuntimeError("검색 수집 실패")
                if rank is not None and blog_analyzer.post_identity(post_link) != blog_analyzer.post_identity(content["published_url"]):
                    raise RuntimeError("검색 결과가 발행 URL과 일치하지 않습니다.")
                # DB에 기록
                record_rank(
                    content_id=cid,
                    keyword=keyword,
                    rank=rank,
                    keyword_type=kw_type,
                    total_searched=total,
                    source=source,
                    post_title=post_title,
                    post_link=post_link
                )

                rank_str = f"#{rank}" if rank else "미노출"
                emoji = "🟢" if rank and rank <= 10 else ("🟡" if rank and rank <= 20 else "🔴")
                log(f"   {emoji} {keyword} ({kw_type}): {rank_str} [{source}]")

                content_results.append({
                    "keyword": keyword, "type": kw_type,
                    "rank": rank, "source": source
                })

            except Exception as e:
                log(f"   ❌ {keyword} 조회 실패: {e}", "ERROR")
                content_results.append({
                    "keyword": keyword, "type": kw_type,
                    "rank": None, "error": str(e)
                })

        all_results.append({
            "content_id": cid,
            "results": content_results
        })

    return all_results


def track_blog_index(blog_id, dry_run=False):
    """블로그 전체 지수를 계산하고 DB에 기록."""
    log(f"\n━━━ 블로그 지수 계산 (blog_id: {blog_id}) ━━━")

    if dry_run:
        log("[DRY-RUN] 블로그 지수 계산 생략")
        return None

    try:
        visitors = blog_analyzer.get_daily_visitors(blog_id)
        rss_info = blog_analyzer.get_blog_rss_info(blog_id)

        if not visitors:
            log("방문자 데이터 없음 — 추정 지수를 계산·저장하지 않습니다.", "WARN")
            return None

        if not rss_info:
            log("RSS 데이터 없음 — 추정 지수를 계산·저장하지 않습니다.", "WARN")
            return None

        index = blog_analyzer.calculate_blog_index(visitors, rss_info)
        record_blog_index(blog_id, index)

        log(f"   📊 총점: {index['total_score']}점 | 등급: {index['grade']}")
        log(f"   방문자: {index['traffic_score']}점 | 활동: {index['activity_score']}점")
        log(f"   콘텐츠: {index['content_score']}점 | 노출: {index['exposure_score']}점")

        return index
    except Exception as e:
        log(f"블로그 지수 계산 실패: {e}", "ERROR")
        return None


def analyze_trends_and_feedback(dry_run=False):
    """추세 분석 및 피드백 액션 생성."""
    log(f"\n━━━ 추세 분석 & 피드백 생성 ━━━")

    contents = get_tracked_contents(active_only=True)
    feedback_count = 0

    for content in contents:
        cid = content["content_id"]
        primary_kw = content.get("primary_keyword", "")
        if not primary_kw:
            continue

        trend = get_rank_trend(cid, primary_kw, days=14)

        if trend["trend"] == "insufficient_data":
            log(f"   ℹ️ {cid}: 데이터 부족 ({trend['data_points']}건) — 3일 이상 수집 후 분석 가능")
            continue

        if trend["trend"] == "not_indexed":
            # 아예 노출이 안 되는 경우
            recommendation = (
                f"'{primary_kw}' 키워드로 전혀 노출되지 않습니다. "
                f"제목에 핵심 키워드를 전진 배치하고, "
                f"경쟁이 낮은 롱테일 키워드 3~5개를 본문에 추가하세요."
            )
            if not dry_run:
                record_feedback(cid, "NOT_INDEXED",
                                recommendation=recommendation)
            log(f"   🔴 {cid}: 미노출 — 키워드 전진 배치 권고")
            feedback_count += 1

        elif trend["trend"] in ("falling", "falling_fast"):
            recommendation = (
                f"'{primary_kw}' 순위 하락 추세 "
                f"({trend['avg_first_half']}위 → {trend['avg_second_half']}위, "
                f"변동: +{trend['change']}). "
                f"제목 후킹 강화, 본문 가독성 개선, 최신 정보 업데이트를 추천합니다."
            )
            if not dry_run:
                record_feedback(cid, "FALLING_RANK",
                                current_rank=trend.get("latest_rank"),
                                rank_change=int(trend["change"]),
                                recommendation=recommendation)
            emoji = "🔴" if trend["trend"] == "falling_fast" else "🟡"
            log(f"   {emoji} {cid}: 순위 하락 ({trend['change']:+.1f}) — 콘텐츠 개선 권고")
            feedback_count += 1

        elif trend["trend"] in ("rising", "rising_fast"):
            recommendation = (
                f"'{primary_kw}' 순위 상승 추세 "
                f"({trend['avg_first_half']}위 → {trend['avg_second_half']}위). "
                f"현재 전략을 유지하고, 유사 키워드로 파생 콘텐츠 기획을 추천합니다."
            )
            if not dry_run:
                record_feedback(cid, "RISING_RANK",
                                current_rank=trend.get("latest_rank"),
                                rank_change=int(trend["change"]),
                                recommendation=recommendation)
            emoji = "🟢" if trend["trend"] == "rising_fast" else "🔵"
            log(f"   {emoji} {cid}: 순위 상승 ({trend['change']:+.1f}) — 파생 콘텐츠 기획 권고")
            feedback_count += 1

        elif trend["trend"] == "stable":
            latest = trend.get("latest_rank")
            if latest and latest > 20:
                recommendation = (
                    f"'{primary_kw}' 순위 안정적이나 {latest}위로 TOP20 밖입니다. "
                    f"글 길이를 늘리거나 구조화된 비교표를 추가하여 체류시간을 늘려보세요."
                )
                if not dry_run:
                    record_feedback(cid, "STABLE_LOW",
                                    current_rank=latest,
                                    recommendation=recommendation)
                log(f"   🟡 {cid}: 안정적이나 {latest}위 — TOP20 진입 전략 필요")
                feedback_count += 1
            else:
                log(f"   🟢 {cid}: 안정적 ({trend.get('latest_rank', '?')}위) — 현재 전략 유지")

    log(f"\n   피드백 액션 {feedback_count}건 생성 완료")
    return feedback_count


def generate_daily_summary(blog_id, rank_results, blog_index):
    """일일 추적 요약 출력."""
    log("\n" + "=" * 60)
    log("📋 일일 성과 추적 요약")
    log("=" * 60)
    log(f"   날짜: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    log(f"   블로그: {blog_id}")

    if blog_index:
        log(f"   블로그 지수: {blog_index['total_score']}점 ({blog_index['grade']})")

    total_kw = 0
    top10 = 0
    top20 = 0
    not_indexed = 0

    for content in rank_results:
        for r in content.get("results", []):
            total_kw += 1
            rank = r.get("rank")
            if rank is None:
                not_indexed += 1
            elif rank <= 10:
                top10 += 1
            elif rank <= 20:
                top20 += 1

    log(f"\n   추적 키워드: {total_kw}개")
    log(f"   🟢 TOP 10: {top10}개")
    log(f"   🟡 TOP 20: {top20}개")
    log(f"   🔴 미노출: {not_indexed}개")

    if total_kw > 0:
        top10_rate = top10 / total_kw * 100
        log(f"   TOP10 비율: {top10_rate:.0f}%")

    db_stats = get_db_stats()
    log(f"\n   📦 DB 누적: 순위 기록 {db_stats['total_rank_records']}건 | "
        f"지수 기록 {db_stats['total_index_records']}건 | "
        f"추적 기간 {db_stats['tracking_days']}일")

    log("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="블로그 성과 일일 자동 추적기"
    )
    parser.add_argument(
        "--blog-id", required=True,
        help="네이버 블로그 ID (예: oceantecblog)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="실제 API 호출 없이 시뮬레이션만 실행"
    )
    parser.add_argument(
        "--register-only", action="store_true",
        help="CONTENT_REGISTRY에서 추적 대상만 등록하고 종료"
    )
    parser.add_argument(
        "--skip-index", action="store_true",
        help="블로그 지수 계산 건너뛰기"
    )
    parser.add_argument(
        "--skip-feedback", action="store_true",
        help="추세 분석 및 피드백 생성 건너뛰기"
    )

    args = parser.parse_args()
    blog_id = args.blog_id.strip()

    log("==========================================================")
    log("  Naver Blog Performance Daily Tracker")
    log("==========================================================")
    log(f"   Blog ID: {blog_id}")
    log(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        log("   [!] DRY-RUN mode (no actual API calls)")

    # Step 0: DB 초기화
    init_db()

    # Step 1: 콘텐츠 자동 등록
    log("\n━━━ Step 1: 콘텐츠 자동 등록 ━━━")
    registered = auto_register_from_registry(blog_id)
    log(f"   등록/갱신: {len(registered)}개 콘텐츠")

    if args.register_only:
        log("\n[DONE] 등록 완료 (--register-only 모드)")
        return

    # Step 2: 키워드 순위 추적
    log("\n━━━ Step 2: 키워드 순위 추적 ━━━")
    rank_results = track_keyword_ranks(blog_id, dry_run=args.dry_run)

    # Step 3: 블로그 지수 계산
    blog_index = None
    if not args.skip_index:
        blog_index = track_blog_index(blog_id, dry_run=args.dry_run)
    else:
        log("\n[SKIP] 블로그 지수 계산 생략 (--skip-index)")

    # Step 4: 추세 분석 및 피드백
    if not args.skip_feedback:
        analyze_trends_and_feedback(dry_run=args.dry_run)
    else:
        log("\n[SKIP] 추세 분석 생략 (--skip-feedback)")

    # Step 5: 요약
    generate_daily_summary(blog_id, rank_results, blog_index)

    log("\n✅ 일일 추적 완료")


if __name__ == "__main__":
    main()
