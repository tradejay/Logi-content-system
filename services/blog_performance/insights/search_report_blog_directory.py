"""User supplied display names; never change blog identity or ranking."""
import html
import json
from pathlib import Path

DIRECTORY = json.loads((Path(__file__).resolve().parents[3] / 'data/blog_performance/blog-directory.json').read_text(encoding='utf-8'))['blogs']


def blog_link(blog):
    entry = DIRECTORY.get(blog, {})
    name = entry.get('name', blog)
    marker = ' <b title="사용자 지정 오우션 관련 업체">V</b>' if entry.get('ocean_related') else ''
    url = 'https://' + blog if blog.endswith('.tistory.com') else 'https://blog.naver.com/' + blog
    own = ' data-ocean-own="true"' if blog in {'oceantech01', 'bluebeartech'} else ''
    return '<a' + own + ' href="' + html.escape(url, quote=True) + '" target="_blank" rel="noopener">' + html.escape(name) + '</a>' + marker
