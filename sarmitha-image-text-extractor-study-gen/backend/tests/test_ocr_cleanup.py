import unittest

from app.services.ocr_cleanup import clean_ocr_lines, clean_sinhala_text


class OcrCleanupTests(unittest.TestCase):
    def test_removes_latin_letters_and_digits_from_sinhala_line(self):
        self.assertEqual(clean_sinhala_text("abc 123 සිංහල 99 xyz"), "සිංහල")

    def test_keeps_sinhala_and_normal_punctuation(self):
        self.assertEqual(clean_sinhala_text("සිංහල, වාක්‍යය."), "සිංහල, වාක්‍යය.")

    def test_rejects_non_sinhala_noise(self):
        self.assertEqual(clean_sinhala_text("A7B 123 !!!"), "")

    def test_rejects_single_character_hallucination(self):
        self.assertEqual(clean_sinhala_text("123 ක xyz"), "")

    def test_removes_punctuation_left_by_a_leading_page_number(self):
        self.assertEqual(clean_sinhala_text("3) මානව වෘත්තීය"), "මානව වෘත්තීය")

    def test_line_metadata_is_preserved(self):
        lines = [{"text": "12 සිංහල abc", "confidence": 0.7, "crop_b64": "x"}]
        self.assertEqual(
            clean_ocr_lines(lines),
            [{"text": "සිංහල", "confidence": 0.7, "crop_b64": "x"}],
        )

    def test_consecutive_duplicate_lines_are_removed(self):
        lines = [
            {"text": "සෛල", "confidence": 0.7, "crop_b64": "a"},
            {"text": "සෛල", "confidence": 0.6, "crop_b64": "b"},
            {"text": "රසායනික", "confidence": 0.8, "crop_b64": "c"},
        ]
        self.assertEqual(
            [line["text"] for line in clean_ocr_lines(lines)],
            ["සෛල", "රසායනික"],
        )


if __name__ == "__main__":
    unittest.main()
