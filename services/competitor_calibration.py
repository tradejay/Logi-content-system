"""Compatibility import; implementation moved to services.blog_performance."""
import sys
from services.blog_performance import competitor_calibration as _implementation
sys.modules[__name__] = _implementation
