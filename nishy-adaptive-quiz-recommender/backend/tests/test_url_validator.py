import unittest
from unittest.mock import Mock, patch

from app.services.url_validator import build_resources, is_youtube_video_url


class BiologyResourceTests(unittest.TestCase):
    def test_rejects_exam_code_as_a_resource_topic(self):
        self.assertEqual(build_resources("AL/2026/09/E-1"), [])

    @patch("app.services.url_validator.find_youtube_video")
    @patch("app.services.url_validator.find_openstax_index_article")
    @patch("app.services.url_validator._ddg_first_url")
    def test_only_looks_up_youtube_and_returns_direct_video(self, search, openstax, youtube):
        youtube.return_value = {
            "label": "English", "title": "Golgi apparatus", "source": "YouTube",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
        }
        self.assertEqual(build_resources("Golgi apparatus"), [youtube.return_value])
        youtube.assert_called_once_with("Golgi apparatus")
        search.assert_not_called()
        openstax.assert_not_called()

    @patch("app.services.url_validator.find_youtube_video", return_value=None)
    def test_unavailable_video_has_no_other_website_fallback(self, youtube):
        self.assertEqual(build_resources("Golgi apparatus"), [])

    def test_video_url_allowlist_blocks_other_sites_and_lookalike_hosts(self):
        for url in (
            "https://youtube.com.evil.example/watch?v=abcdefghijk",
            "https://www.youtube.com/results?search_query=biology",
            "https://openstax.org/books/biology",
            "https://evil.example/youtube.com/watch?v=abcdefghijk",
            "https://user:pass@youtube.com/watch?v=abcdefghijk",
            "https://youtube.com/watch?v=short",
        ):
            with self.subTest(url=url):
                self.assertFalse(is_youtube_video_url(url))
        self.assertTrue(is_youtube_video_url("https://youtu.be/abcdefghijk"))
        self.assertTrue(is_youtube_video_url("https://www.youtube.com/watch?v=abcdefghijk"))

    @patch("app.services.url_validator.httpx.Client")
    def test_does_not_return_a_youtube_search_page_when_scraping_fails(self, client):
        client.return_value.__enter__.return_value.get.return_value.status_code = 200
        client.return_value.__enter__.return_value.get.return_value.text = "no video ids"

        from app.services.url_validator import find_youtube_video

        self.assertIsNone(find_youtube_video("Golgi apparatus"))

    @patch("app.services.url_validator.httpx.Client")
    def test_returns_exact_direct_youtube_watch_link(self, client_cls):
        # Topic deliberately avoids "golgi"/"extracellular matrix"/"vascular
        # plant"/"large tree" — those trigger an unrelated pre-verified
        # known-video override in find_youtube_video that would otherwise
        # shadow the scraped id this test exists to check.
        search = Mock(status_code=200, text='{"videoId":"abcdefghijk"}')
        metadata = Mock(status_code=200)
        metadata.json.return_value = {"title": "Cellular respiration overview and stages"}
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = [search, metadata]

        from app.services.url_validator import find_youtube_video

        resource = find_youtube_video("Cellular respiration")
        self.assertEqual(resource["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(resource["title"], "Cellular respiration overview and stages")


if __name__ == "__main__":
    unittest.main()
