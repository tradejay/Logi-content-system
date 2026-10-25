"""Compatibility import; implementation moved to services.blog_performance."""
import sys
from services.blog_performance import competitor_engine as _implementation
if __name__ == "__main__":
    raise SystemExit(_implementation._main())
else:
    sys.modules[__name__] = _implementation
