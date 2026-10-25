"""Compatibility import; implementation moved to services.blog_performance."""
import sys
from services.blog_performance import weekly_report as _implementation
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
else:
    sys.modules[__name__] = _implementation
