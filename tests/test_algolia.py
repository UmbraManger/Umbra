import unittest
from unittest import mock

import algolia

PAGE = ('<script>{"applicationID": "TESTAPP01", "apiKey": "Zm9vYmFyYmF6"}'
        '</script>')


class FakeResponse:
    text = PAGE
    status_code = 200
    def raise_for_status(self): pass


def _patch(**kw):
    return mock.patch.object(algolia.requests, 'get', **kw)


class AlgoliaCredsTests(unittest.TestCase):
    def setUp(self):
        algolia._creds_cache.clear()

    def tearDown(self):
        algolia._creds_cache.clear()

    def test_success_is_cached(self):
        with _patch(return_value=FakeResponse()) as get:
            creds = algolia.get_algolia_creds('https://x.test')
            self.assertEqual(creds, {'appId': 'TESTAPP01', 'apiKey': 'Zm9vYmFyYmF6'})
            algolia.get_algolia_creds('https://x.test')
            self.assertEqual(get.call_count, 1)     # served from cache

    def test_failure_retries_within_one_call(self):
        flaky = [ConnectionError('connect timeout'), FakeResponse()]
        with _patch(side_effect=flaky) as get:
            creds = algolia.get_algolia_creds('https://x.test')
            self.assertIsNotNone(creds)
            self.assertEqual(get.call_count, 2)

    def test_failure_is_not_cached(self):
        with _patch(side_effect=ConnectionError('connect timeout')) as get:
            self.assertIsNone(algolia.get_algolia_creds('https://x.test'))
            self.assertIsNone(algolia.get_algolia_creds('https://x.test'))
            self.assertEqual(get.call_count, 4)     # 2 attempts per call, no negative cache

    def test_successful_lookup_returns_hits(self):
        with _patch(return_value=FakeResponse()):
            creds = algolia.get_algolia_creds('https://x.test')
        self.assertIn('appId', creds)


if __name__ == '__main__':
    unittest.main()
