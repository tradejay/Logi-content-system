"""Create a compact, code-owned routing brief from actual batch outputs."""
import argparse
from datetime import datetime, timezone
from services.ide_worker_bridge import ROOT, load, save, local


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    args = parser.parse_args()
    directory = local(ROOT, args.directory)
    state = load(directory / 'execution.json')
    articles = []
    for article in state.get('articles', []):
        cid = article['content_id']
        path = directory / 'articles' / cid / 'asset-candidates.json'
        assets = load(path) if path.exists() else {}
        articles.append({'content_id': cid, 'stage': article['stage'], 'blocked_reason': article.get('reason'),
                         'pending_task': article.get('pending', {}).get('task_id'),
                         'official_pending': article.get('official_pending', False),
                         'asset_candidate_count': len(assets.get('candidates', [])),
                         'unresolved_assets': assets.get('unresolved_items', []),
                         'asset_needs': article['plan'].get('asset_needs', []),
                         'review_issues': article.get('issues', [])})
    brief = {'batch_id': state['batch_id'], 'snapshot_at': datetime.now(timezone.utc).isoformat(),
             'articles': articles, 'allowed_workers': ['planner', 'writer', 'review', 'assets'],
             'constraints': ['진행 중 작업에 중복 배정 금지', 'Gemini API 호출/복원 금지', '이미지 승인·Fact 확정·원고 승인·발행은 별도', '설정 화면·제품 실물은 추측 생성 금지']}
    destination = directory / 'management-brief.json'
    save(destination, brief)
    print(destination.relative_to(ROOT).as_posix())


if __name__ == '__main__':
    main()
