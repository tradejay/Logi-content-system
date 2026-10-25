"""
weekly_report.py
================
주간 성과 분석 리포트 자동 생성기.

기능:
1. 지난 7일간 수집된 순위 데이터를 분석
2. 글별 성과 요약 (TOP10/TOP20 비율, 추세)
3. 블로그 지수 변동 추이
4. 피드백 루프: 다음 주 콘텐츠 기획 권고
5. 마크다운 리포트 생성 (06_analytics/weekly/)

사용법:
  python -m services.weekly_report
  python -m services.weekly_report --days 14
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta

# Windows 콘솔 인코딩 문제 방지
import io
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.blog_performance.performance_db import (
    get_tracked_contents, get_rank_history, get_blog_index_history,
    get_rank_trend, get_content_performance_summary, get_db_stats,
    get_latest_ranks
)

ANALYTICS_DIR = os.path.join(BASE_DIR, "content-system", "06_analytics")
WEEKLY_DIR = os.path.join(ANALYTICS_DIR, "weekly")
FEEDBACK_DIR = os.path.join(ANALYTICS_DIR, "keyword-feedback")


def generate_report(days=7, blog_id=""):
    """주간 성과 분석 리포트 생성."""
    now = datetime.now()
    week_str = now.strftime("%Y-W%W")
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    contents = get_tracked_contents(active_only=True)
    db_stats = get_db_stats()

    lines = []
    lines.append(f"# 📊 주간 블로그 성과 분석 리포트")
    lines.append(f"")
    lines.append(f"- **리포트 기간**: {since} ~ {now.strftime('%Y-%m-%d')}")
    lines.append(f"- **생성 시각**: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- **블로그 ID**: {blog_id or '(미설정)'}")
    lines.append(f"- **추적 콘텐츠**: {len(contents)}편")
    lines.append(f"- **누적 순위 기록**: {db_stats.get('total_rank_records', 0)}건")
    lines.append(f"- **추적 기간**: {db_stats.get('tracking_days', 0)}일")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ─── 1. 글별 성과 요약 ───
    lines.append("## 1. 콘텐츠별 성과 요약")
    lines.append("")
    lines.append("| 콘텐츠 ID | 대표 키워드 | 최신 순위 | TOP10 | TOP20 | 추세 |")
    lines.append("|:---|:---|:---:|:---:|:---:|:---|")

    content_feedbacks = []

    for content in contents:
        cid = content["content_id"]
        primary_kw = content.get("primary_keyword", "")
        summary = get_content_performance_summary(cid)
        trend = get_rank_trend(cid, primary_kw, days=days)

        # 최신 순위
        latest_rank = "미노출"
        for d in summary.get("details", []):
            if d.get("keyword") == primary_kw and d.get("rank"):
                latest_rank = f"#{d['rank']}"
                break

        # 추세 아이콘
        trend_label = trend.get("trend", "insufficient_data")
        trend_map = {
            "rising_fast": "🚀 급상승",
            "rising": "📈 상승",
            "stable": "➡️ 안정",
            "falling": "📉 하락",
            "falling_fast": "🔻 급하락",
            "not_indexed": "⚠️ 미노출",
            "insufficient_data": "📊 데이터 수집 중"
        }
        trend_str = trend_map.get(trend_label, trend_label)

        top10 = summary.get("keywords_in_top10", 0)
        top20 = summary.get("keywords_in_top20", 0)

        lines.append(
            f"| {cid} | {primary_kw} | {latest_rank} | "
            f"{top10}개 | {top20}개 | {trend_str} |"
        )

        # 피드백 수집
        if trend_label in ("falling", "falling_fast", "not_indexed"):
            content_feedbacks.append({
                "content_id": cid,
                "keyword": primary_kw,
                "issue": trend_str,
                "trend": trend
            })

    lines.append("")

    # ─── 2. 키워드 순위 상세 ───
    lines.append("## 2. 키워드 순위 상세 추적")
    lines.append("")

    for content in contents:
        cid = content["content_id"]
        title = content.get("title", "")[:50]
        primary_kw = content.get("primary_keyword", "")
        supporting = content.get("supporting_keywords", [])
        layman = content.get("layman_terms", [])

        lines.append(f"### {cid}: {title}")
        lines.append("")
        lines.append("| 키워드 | 유형 | 최신 순위 | 7일 추세 | 최고 순위 |")
        lines.append("|:---|:---|:---:|:---|:---:|")

        all_kws = [(primary_kw, "primary")]
        all_kws += [(kw, "supporting") for kw in supporting[:3]]
        all_kws += [(kw, "layman") for kw in layman[:2]]

        for kw, kw_type in all_kws:
            if not kw:
                continue
            trend = get_rank_trend(cid, kw, days=days)
            history = get_rank_history(cid, kw, days=days)

            latest = "미노출"
            best = "-"
            trend_str = "데이터 부족"

            if trend.get("latest_rank"):
                latest = f"#{trend['latest_rank']}"
            if trend.get("best_rank"):
                best = f"#{trend['best_rank']}"
            if trend.get("change") is not None:
                change = trend["change"]
                if change < 0:
                    trend_str = f"↑ {abs(change):.0f}칸 상승"
                elif change > 0:
                    trend_str = f"↓ {change:.0f}칸 하락"
                else:
                    trend_str = "변동 없음"

            type_label = {"primary": "🎯 대표", "supporting": "📌 보조", "layman": "💬 일상어"}.get(kw_type, kw_type)
            lines.append(f"| {kw} | {type_label} | {latest} | {trend_str} | {best} |")

        lines.append("")

    # ─── 3. 블로그 지수 변동 ───
    if blog_id:
        lines.append("## 3. 블로그 지수 변동 추이")
        lines.append("")

        index_history = get_blog_index_history(blog_id, days=days)
        if index_history:
            lines.append("| 날짜 | 총점 | 등급 | 방문자 | 활동 | 콘텐츠 | 노출 |")
            lines.append("|:---|:---:|:---|:---:|:---:|:---:|:---:|")

            for idx in index_history:
                lines.append(
                    f"| {idx['recorded_at']} | **{idx['total_score']}** | "
                    f"{idx['grade']} | {idx['traffic_score']} | "
                    f"{idx['activity_score']} | {idx['content_score']} | "
                    f"{idx['exposure_score']} |"
                )

            if len(index_history) >= 2:
                first = index_history[0]["total_score"]
                last = index_history[-1]["total_score"]
                diff = last - first
                emoji = "📈" if diff > 0 else ("📉" if diff < 0 else "➡️")
                lines.append(f"\n> {emoji} **기간 내 변동**: {first}점 → {last}점 ({diff:+d}점)")
        else:
            lines.append("> ℹ️ 아직 블로그 지수 기록이 없습니다. Daily Tracker를 실행해주세요.")

        lines.append("")

    # ─── 4. 피드백 루프 ───
    lines.append("## 4. 다음 주 콘텐츠 기획 권고 (Feedback Loop)")
    lines.append("")

    if content_feedbacks:
        for fb in content_feedbacks:
            cid = fb["content_id"]
            kw = fb["keyword"]
            issue = fb["issue"]
            trend = fb.get("trend", {})

            lines.append(f"### ⚠️ {cid} — {kw}")
            lines.append(f"- **현재 상태**: {issue}")

            if trend.get("latest_rank"):
                lines.append(f"- **최신 순위**: #{trend['latest_rank']}")
            if trend.get("change") is not None:
                lines.append(f"- **추세 변동**: {trend['change']:+.1f} ({trend.get('avg_first_half', '?')}위 → {trend.get('avg_second_half', '?')}위)")

            lines.append(f"- **권고 조치**:")
            if trend.get("trend") == "not_indexed":
                lines.append(f"  1. 제목에 '{kw}' 키워드를 맨 앞에 배치")
                lines.append(f"  2. 본문에 경쟁 낮은 롱테일 키워드 3~5개 추가")
                lines.append(f"  3. 이미지 ALT 태그에 '{kw}' 포함")
            elif trend.get("trend") in ("falling", "falling_fast"):
                lines.append(f"  1. 본문에 최신 정보 업데이트 (최근 3개월 내 데이터)")
                lines.append(f"  2. 비교표/인포그래픽 추가하여 체류시간 증가")
                lines.append(f"  3. 유사 주제 파생 글 작성하여 내부링크 허브 강화")

            lines.append("")
    else:
        lines.append("> ✅ 모든 콘텐츠가 안정적이거나 상승 추세입니다. 현재 전략을 유지하세요.")
        lines.append("")

    # ─── 5. 전체 KPI 대시보드 ───
    lines.append("## 5. 전체 KPI 대시보드")
    lines.append("")

    all_ranks = get_latest_ranks()
    total_kw = len(all_ranks)
    top10_count = sum(1 for r in all_ranks if r.get("rank") and r["rank"] <= 10)
    top20_count = sum(1 for r in all_ranks if r.get("rank") and r["rank"] <= 20)
    not_indexed = sum(1 for r in all_ranks if r.get("rank") is None)

    lines.append("| KPI | 현재값 | 목표 |")
    lines.append("|:---|:---:|:---:|")
    lines.append(f"| 추적 키워드 수 | {total_kw}개 | — |")
    lines.append(f"| TOP 10 키워드 | {top10_count}개 ({(top10_count/max(1,total_kw)*100):.0f}%) | 50%+ |")
    lines.append(f"| TOP 20 키워드 | {top20_count}개 ({(top20_count/max(1,total_kw)*100):.0f}%) | 80%+ |")
    lines.append(f"| 미노출 키워드 | {not_indexed}개 ({(not_indexed/max(1,total_kw)*100):.0f}%) | 10% 미만 |")
    lines.append("")

    lines.append("---")
    lines.append(f"*이 리포트는 `services/weekly_report.py`에 의해 자동 생성되었습니다.*")

    # 파일 저장
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    filename = f"{week_str}-performance-report.md"
    filepath = os.path.join(WEEKLY_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ 주간 리포트 생성 완료: {filepath}")
    return filepath


def generate_feedback_yaml(days=7):
    """다음 주 Brief 조정에 반영할 피드백 YAML 생성."""
    import yaml

    contents = get_tracked_contents(active_only=True)
    now = datetime.now()
    week_str = now.strftime("%Y-W%W")

    feedback = {
        "feedback_week": week_str,
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "content_feedback": []
    }

    for content in contents:
        cid = content["content_id"]
        primary_kw = content.get("primary_keyword", "")
        if not primary_kw:
            continue

        trend = get_rank_trend(cid, primary_kw, days=days)
        summary = get_content_performance_summary(cid)

        entry = {
            "content_id": cid,
            "primary_keyword": primary_kw,
            "canonical_topic": content.get("canonical_topic", ""),
            "latest_rank": trend.get("latest_rank"),
            "trend": trend.get("trend", "insufficient_data"),
            "rank_change": trend.get("change"),
            "top10_keywords": summary.get("keywords_in_top10", 0),
            "top20_keywords": summary.get("keywords_in_top20", 0),
            "not_indexed_keywords": summary.get("keywords_not_indexed", 0),
            "actions": []
        }

        # 자동 권고 생성
        t = trend.get("trend", "")
        if t == "not_indexed":
            entry["actions"].append("REWRITE_TITLE: 대표 키워드를 제목 맨 앞에 배치")
            entry["actions"].append("ADD_LONGTAIL: 경쟁 낮은 롱테일 키워드 3~5개 본문 추가")
        elif t in ("falling", "falling_fast"):
            entry["actions"].append("UPDATE_CONTENT: 최신 정보로 본문 업데이트")
            entry["actions"].append("ADD_COMPARISON: 비교표 또는 인포그래픽 추가")
            entry["actions"].append("DERIVE_CONTENT: 유사 주제 파생 콘텐츠 기획")
        elif t in ("rising", "rising_fast"):
            entry["actions"].append("MAINTAIN: 현재 전략 유지")
            entry["actions"].append("DERIVE_CONTENT: 유사 키워드로 파생 콘텐츠 확장")
        elif t == "stable":
            if trend.get("latest_rank") and trend["latest_rank"] > 20:
                entry["actions"].append("IMPROVE_DEPTH: 본문 깊이 강화 (체류시간 증가)")
            else:
                entry["actions"].append("MAINTAIN: 현재 전략 유지")

        feedback["content_feedback"].append(entry)

    # 저장
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    filename = f"{week_str}-auto-feedback.yaml"
    filepath = os.path.join(FEEDBACK_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(feedback, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"✅ 피드백 YAML 생성 완료: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="주간 성과 분석 리포트 생성기")
    parser.add_argument("--days", type=int, default=7, help="분석 기간 (기본: 7일)")
    parser.add_argument("--blog-id", default="", help="블로그 ID")
    parser.add_argument("--no-feedback", action="store_true", help="피드백 YAML 생성 건너뛰기")

    args = parser.parse_args()

    print("=" * 50)
    print(" 주간 성과 분석 리포트 생성기")
    print("=" * 50)

    report_path = generate_report(days=args.days, blog_id=args.blog_id)

    if not args.no_feedback:
        feedback_path = generate_feedback_yaml(days=args.days)

    print("\n🎯 완료!")


if __name__ == "__main__":
    main()
