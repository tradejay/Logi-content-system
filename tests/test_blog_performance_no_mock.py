import ast
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from services.blog_performance import blog_analyzer


class NoMockTests(unittest.TestCase):
    def test_old_import_is_same_module_and_paths_stay_at_project_root(self):
        from services import blog_analyzer as legacy
        self.assertIs(legacy, blog_analyzer)
        self.assertEqual(Path(blog_analyzer.BASE_DIR), Path(__file__).resolve().parents[1])

    def test_autocomplete_never_invents_metrics(self):
        response = Mock(status_code=200)
        response.json.return_value = {'items': [[['회의실 카메라']]]}
        with patch.object(blog_analyzer.requests, 'get', return_value=response):
            rows = blog_analyzer.get_searchad_keywords('회의실')
        self.assertEqual(len(rows), 2)
        for row in rows:
            for key in ('monthly_pc', 'monthly_mobile', 'monthly_total', 'monthly_ave_pc_ctr', 'comp_idx'):
                self.assertIsNone(row[key])

    def test_datalab_without_credentials_never_generates_curve(self):
        with patch.object(blog_analyzer.requests, 'post') as request:
            result = blog_analyzer.get_datalab_trend(['회의실'])
        request.assert_not_called()
        self.assertEqual(result['results'], [])
        self.assertEqual(result['measurement_status'], 'unavailable')

    def test_web_missing_visitors_never_calculates_even_with_manual_value(self):
        from flask import Flask, request, jsonify
        source = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text(encoding='utf-8'))
        route = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'analyze_blog')
        route.decorator_list = []
        namespace = {'request': request, 'jsonify': jsonify, 'blog_analyzer': blog_analyzer}
        exec(compile(ast.Module(body=[route], type_ignores=[]), 'app.py', 'exec'), namespace)
        web = Flask(__name__)
        web.add_url_rule('/api/analyze-blog', view_func=namespace['analyze_blog'], methods=['POST'])
        with patch.object(blog_analyzer, 'get_daily_visitors', return_value=None), \
             patch.object(blog_analyzer, 'get_blog_rss_info', return_value={'posts': [{'title': '글'}]}), \
             patch.object(blog_analyzer, 'calculate_blog_index') as calculate:
            response = web.test_client().post('/api/analyze-blog', json={'blog_id': 'test', 'manual_visitors': 120})
        self.assertEqual(response.get_json()['status'], 'unavailable')
        self.assertIsNone(response.get_json()['index'])
        self.assertEqual(response.get_json()['visitor_history'], [])
        calculate.assert_not_called()
