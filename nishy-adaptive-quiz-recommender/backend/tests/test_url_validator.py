import unittest
from unittest.mock import Mock, patch

from app.services.url_validator import build_resources


class BiologyResourceTests(unittest.TestCase):
    def test_rejects_exam_code_as_a_resource_topic(self):
        self.assertEqual(build_resources("AL/2026/09/E-1"), [])

    @patch("app.services.url_validator.find_youtube_video")
    @patch("app.services.url_validator.find_openstax_index_article")
    @patch("app.services.url_validator.nie_biology_resource")
    @patch("app.services.url_validator._ddg_first_url")
    def test_uses_only_biology_relevant_trusted_queries(self, search, nie, openstax, youtube):
        search.side_effect = [
            "https://www.khanacademy.org/science/biology/cell-structure",
        ]
        nie.return_value = {
            "label": "English", "title": "NIE Biology", "source": "Sri Lanka NIE",
            "url": "https://www.nie.lk/pdffiles/other/eGr12OM%20BioResoBook.pdf",
        }
        openstax.return_value = {
            "label": "English", "title": "OpenStax Biology", "source": "OpenStax Biology",
            "url": "https://openstax.org/books/biology-2e/pages/4-4-the-endomembrane-system",
        }
        youtube.return_value = {
            "label": "English",
            "title": "Sri Lankan GCE A Level Biology Golgi apparatus Tutorial — YouTube",
            "url": "https://www.youtube.com/watch?v=abcdefghijk",
            "source": "YouTube",
        }

        resources = build_resources("Golgi apparatus")

        self.assertEqual([resource["source"] for resource in resources], [
            "YouTube", "OpenStax Biology", "Khan Academy"
        ])
        queries = " ".join(call.kwargs["query"] for call in search.call_args_list)
        self.assertIn("biology", queries.casefold())
        self.assertIn("Golgi apparatus", queries)
        self.assertNotIn("GeeksforGeeks", str(resources))

    @patch("app.services.url_validator.httpx.Client")
    def test_does_not_return_a_youtube_search_page_when_scraping_fails(self, client):
        client.return_value.__enter__.return_value.get.return_value.status_code = 200
        client.return_value.__enter__.return_value.get.return_value.text = "no video ids"

        from app.services.url_validator import find_youtube_video

        self.assertIsNone(find_youtube_video("Golgi apparatus"))

    @patch("app.services.url_validator.httpx.Client")
    def test_returns_exact_direct_youtube_watch_link(self, client_cls):
        search = Mock(status_code=200, text='{"videoId":"abcdefghijk"}')
        metadata = Mock(status_code=200)
        metadata.json.return_value = {"title": "Golgi apparatus structure and function"}
        client = client_cls.return_value.__enter__.return_value
        client.get.side_effect = [search, metadata]

        from app.services.url_validator import find_youtube_video

        resource = find_youtube_video("Golgi apparatus")
        self.assertEqual(resource["url"], "https://www.youtube.com/watch?v=abcdefghijk")
        self.assertEqual(resource["title"], "Golgi apparatus structure and function")


if __name__ == "__main__":
    unittest.main()
