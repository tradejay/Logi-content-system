#!/usr/bin/env python3
"""
CLI tool for running Naver Blog Content Pipeline from any stage with custom instructions.

Usage Examples:
  # 1. 전체 처음부터 실행
  python scripts/pipeline_cli.py CNT-2026W39-001

  # 2. 특정 단계부터 재실행 (기존 전략/에셋 승계)
  python scripts/pipeline_cli.py CNT-2026W39-001 --stage write

  # 3. 추가 피드백/지시사항을 포함하여 특정 단계부터 재실행
  python scripts/pipeline_cli.py CNT-2026W39-001 --stage feedback --feedback "피드백 검토 r3: 랠리 마이크 팟 허브 배선 제약 명시"

  # 4. 사용 가능한 단계 목록:
  #   - inputs    : 팩트/출처/주의사항 재점검부터
  #   - strategy  : 기획 전략 수립부터
  #   - assets    : 이미지 에셋 계획/바인딩부터
  #   - write     : 본문 원고 작성부터 (기존 전략 유지)
  #   - feedback  : 품질 검토/교정 루프부터 (기존 초안 유지)
  #   - official  : 로지텍 공식 AI Kapa RAG 검증만 실행
"""
import sys
import argparse
from pathlib import Path

# Set up project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

from services.content_pipeline import ContentPipeline

STAGES = ['inputs', 'strategy', 'assets', 'write', 'feedback', 'official']

STAGE_LABELS = {
    'inputs': '기획 및 팩트 점검 (처음부터)',
    'strategy': '기획 전략 수립',
    'assets': '이미지 에셋 계획 및 바인딩',
    'write': '본문 원고 작성 (기존 전략 승계)',
    'feedback': '품질 검토 및 교정 루프 (초안 유지)',
    'official': '로지텍 공식 AI 검증'
}


def main():
    parser = argparse.ArgumentParser(
        description="네이버 블로그 오우션테크놀러지 파이프라인 단계별 수동 재실행 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
지원되는 실행 단계 (--stage):
  inputs   : 기획 및 팩트 점검부터 (처음부터 전체 실행)
  strategy : 기획 전략 수립부터
  assets   : 이미지 에셋 계획 및 바인딩부터
  write    : 원고 작성부터 (기존 전략 및 에셋 계획 유지)
  feedback : 품질 검토 및 교정 루프부터 (초안 유지)
  official : 로지텍 공식 Kapa RAG 교차 검증만 단독 실행
        """
    )
    parser.add_argument("content_id", help="대상 콘텐츠 ID (예: CNT-2026W39-001)")
    parser.add_argument("-s", "--stage", choices=STAGES, default=None,
                        help="시작할 파이프라인 단계 (미지정 시 inputs부터 전체 실행)")
    parser.add_argument("-f", "--feedback", default="",
                        help="AI 모델에 전달할 추가 사용자 요청사항 / 피드백 문구")
    parser.add_argument("-r", "--max-revisions", type=int, default=3, choices=range(1, 6),
                        help="검토할 원고 버전 수 (1~5, 기본값: 3, 최초 검토 1회 + 최대 추가 재작성 2회)")
    parser.add_argument("-p", "--preview", action="store_true",
                        help="완료 후 생성된 네이버 블로그 미리보기 링크 및 요약 출력")

    args = parser.parse_args()
    cid = args.content_id
    stage = args.stage
    feedback = args.feedback
    max_rev = args.max_revisions

    stage_desc = STAGE_LABELS.get(stage, stage or 'inputs')
    print("=" * 65)
    print(f"🚀 네이버 블로그 파이프라인 실행 시작")
    print(f" • 대상 콘텐츠 ID : {cid}")
    print(f" • 시작 단계      : {stage_desc}")
    if feedback:
        print(f" • 추가 지시사항  : \"{feedback}\"")
    print(f" • 최대 버전 수   : {max_rev}개 (최초 1회 + 최대 {max_rev - 1}회 추가 재작성)")
    print("=" * 65)

    def on_progress(content_id, current_stage, detail, entry=None):
        title = entry.get('title', current_stage) if isinstance(entry, dict) else current_stage
        msg = entry.get('message', detail) if isinstance(entry, dict) else detail
        status = entry.get('status', 'INFO') if isinstance(entry, dict) else 'INFO'
        icon = "✅" if status == "SUCCESS" else ("⚠️" if status == "WARN" else "▶")
        print(f"{icon} [{current_stage.upper():<8}] {title}: {msg}")

    try:
        pipeline = ContentPipeline(root=PROJECT_ROOT, progress=on_progress)
        result = pipeline.run(
            cid=cid,
            max_revisions=max_rev,
            user_feedback=feedback,
            start_stage=stage
        )

        outcome = result.get('outcome', 'UNKNOWN')
        run_id = result.get('run_id', '')
        draft_file = result.get('draft_file', '')
        admin_checks = result.get('admin_checks', [])

        print("\n" + "=" * 65)
        print(f"🏁 파이프라인 실행 완료")
        print(f" • 최종 결과 (Outcome) : {outcome}")
        print(f" • 실행 Run ID          : {run_id}")
        if draft_file:
            print(f" • 원고 파일 저장 위치 : {draft_file}")
        if admin_checks:
            print(f" • 관리자 확인 대기    : {len(admin_checks)}건")
            for idx, chk in enumerate(admin_checks[:3], 1):
                print(f"    {idx}. {chk.get('kind')}: {chk.get('detail', chk.get('id', ''))}")
        
        print(f"\n🔗 브라우저 확인 링크:")
        print(f" • Workbench : http://localhost:5000/content-ops/workbench/{cid}")
        print(f" • 미리보기  : http://localhost:5000/api/content-system/blog-preview/{cid}")
        print("=" * 65)

        if outcome not in ['COMPLETED_READY', 'COMPLETED_REVIEW_PENDING']:
            print(f"\n⚠️ 파이프라인이 완료 상태에 도달하지 못했습니다 (상태: {outcome}). 종료 코드 1 반환.")
            sys.exit(1)
        sys.exit(0)

    except Exception as err:
        print(f"\n❌ 파이프라인 실행 중 오류 발생: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
