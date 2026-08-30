import unittest
from unittest.mock import Mock, patch

from app.services.llm_service import (
    MAX_NEW_TOKENS,
    MODAL_ENDPOINT_URL,
    QwenModalService,
)


class ModalApiContractTests(unittest.TestCase):
    def test_accepts_complete_json_object_before_extra_closing_brace(self):
        raw = (
            '{"questions":[{"plan_index":1,"question":"Which sugar?",'
            '"options":{"1":"Glucose","2":"Starch","3":"Protein",'
            '"4":"Lipid","5":"Water"},"correct_answer":"1",'
            '"model_answer":"Glucose is a monosaccharide."}]}}'
        )

        result = QwenModalService._extract_json(raw)

        self.assertEqual(result["questions"][0]["correct_answer"], "1")

    def test_repairs_bare_object_keys_from_small_model_json(self):
        raw = (
            '{"questions":[{"plan_index":1,"question":"Which sugar?",'
            'options:{1:"Glucose",2:"Starch",3:"Protein",4:"Lipid",5:"Water"},'
            'correct_answer:"1",model_answer:"Glucose"}]}'
        )

        result = QwenModalService._extract_json(raw)

        self.assertEqual(result["questions"][0]["options"]["1"], "Glucose")

    @patch("app.services.llm_service.httpx.post")
    def test_uses_nishy_endpoint_request_and_response_contract(self, post: Mock):
        response = Mock(status_code=200)
        response.json.return_value = {"response": "generated text"}
        response.raise_for_status.return_value = None
        post.return_value = response

        result = QwenModalService().call("Biology prompt")

        self.assertEqual(result, "generated text")
        args, kwargs = post.call_args
        self.assertEqual(args[0], MODAL_ENDPOINT_URL)
        self.assertEqual(
            kwargs["json"],
            {"prompt": "Biology prompt", "max_new_tokens": MAX_NEW_TOKENS},
        )
        self.assertEqual(MAX_NEW_TOKENS, 180)
        self.assertNotIn("temperature", kwargs["json"])
        self.assertNotIn("max_tokens", kwargs["json"])

    @patch("app.services.llm_service.httpx.post")
    def test_rejects_the_old_text_response_field(self, post: Mock):
        response = Mock(status_code=200)
        response.json.return_value = {"text": "old contract"}
        response.raise_for_status.return_value = None
        post.return_value = response

        with self.assertRaisesRegex(RuntimeError, "'response'"):
            QwenModalService().call("Biology prompt")


if __name__ == "__main__":
    unittest.main()
