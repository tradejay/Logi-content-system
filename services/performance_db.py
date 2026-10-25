"""Compatibility import; implementation moved to services.blog_performance."""
import sys
from services.blog_performance import performance_db as _implementation
sys.modules[__name__] = _implementation
