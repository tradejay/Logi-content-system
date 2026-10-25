import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from services.pipeline_provider import ModelProvider,parse_object
from services.web_research import collect
from services.article_assets import generate_image


class QuarantineTests(unittest.TestCase):
    def test_all_transport_entry_points_fail_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            provider=ModelProvider(Path(directory))
            with patch('requests.post',side_effect=AssertionError('Network must not be reached')) as post:
                calls=[lambda:provider.credentials(),lambda:provider.count_tokens('write','',{}),
                       lambda:provider.complete('write','',{}),lambda:provider._count_tokens_once('write','',{}),
                       lambda:provider._complete_once('write','',{}),lambda:collect(Path(directory),'query'),
                       lambda:generate_image(Path(directory),{})]
                for call in calls:
                    with self.assertRaisesRegex(RuntimeError,'quarantined'):call()
                post.assert_not_called()

    def test_shared_json_parser_remains_available(self):
        self.assertEqual(parse_object('{"passed":true}'),{'passed':True})


if __name__=='__main__':unittest.main()
