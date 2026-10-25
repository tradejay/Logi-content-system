from unittest.mock import patch

from services.blog_performance.insights.steps import check_worker_dispatch_preflight


def test_preflight_never_substitutes_real_project_root(tmp_path):
    with patch('services.worker_preflight.run', return_value={'workers': []}) as probe:
        allowed, issues, pending = check_worker_dispatch_preflight('planner', root=tmp_path)
    assert not allowed
    assert issues
    assert pending == []
    assert probe.call_args.kwargs['root'] == tmp_path
