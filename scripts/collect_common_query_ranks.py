"""Compatibility entry; implementation lives in services/blog_performance/insights."""
import sys
from services.blog_performance.insights import collect_common_query_ranks as _implementation
if __name__ == "__main__":
    _implementation.main()
else:
    sys.modules[__name__] = _implementation
