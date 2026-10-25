"""Compatibility import; implementation moved to services.blog_performance."""
import sys
from services.blog_performance import blog_analyzer as _implementation
sys.modules[__name__] = _implementation
