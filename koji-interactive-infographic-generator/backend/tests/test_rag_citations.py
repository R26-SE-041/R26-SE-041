"""Citation provenance through retrieval, answer formatting and the direct agent."""
import base64
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

from PIL import Image
from shared.citations import cited_sources, sourced_answer, pdf_answer_schema, pdf_structured_answer
from shared.rag import rag_evidence, wikipedia_url


class CitationTests(unittest.TestCase):
    def test_only_references_cited_in_answer_receive_source_names(self):
        sources = [{"number":1,"title":"First.pdf","page":2},
                   {"number":2,"title":"Second.pdf","page":8}]
        answer = sourced_answer("Supported statement [2].",sources,"Unavailable")
        self.assertIn("Sources:\n[2] Second.pdf · PDF page 8",answer)
        self.assertNotIn("First.pdf",answer)
        self.assertEqual(cited_sources(answer,sources),[sources[1]])

    def test_unsupported_reference_or_uncited_answer_cannot_claim_sources(self):
        for answer in ("No reference", "Invented [5]", "Claim.\n## Sources\n[1] Fake.pdf"):
            with self.subTest(answer=answer):
                self.assertEqual(sourced_answer(answer,[{"number":1,"title":"Real.pdf"}],"Unavailable"),"Unavailable")

    def test_grouped_references_validate_every_source_number(self):
        sources = [{"number":1,"title":"First.pdf"}, {"number":2,"title":"Second.pdf"}]
        for answer in ("Supported [1, 2].", "Supported [1;2].", "Supported [1][2]."):
            self.assertEqual(cited_sources(answer,sources),sources)
        for answer in ("Unsupported [1, 99].", "Unsupported [1] [99]."):
            self.assertEqual(cited_sources(answer,sources),[])

    def test_structured_pdf_schema_requires_supporting_evidence(self):
        schema = pdf_answer_schema([{"number":1,"excerpt":"Evidence from a PDF."}])
        self.assertEqual(schema["properties"]["points"]["items"]["required"],["evidence"])
        self.assertEqual(schema["properties"]["points"]["items"]["properties"]["evidence"]["enum"],["Evidence from a PDF."])
        for invalid in ([],[True],[{"number":0,"excerpt":"Text"}],[{"number":1,"excerpt":""}]):
            with self.assertRaises(ValueError):
                pdf_answer_schema(invalid)

    def test_structured_pdf_answer_locates_the_actual_quote_source(self):
        answer = pdf_structured_answer({"points":[{"evidence":"The heart has four chambers."}]},
            [{"number":1,"excerpt":"Other evidence from page one."},
             {"number":2,"excerpt":"The heart has four chambers."}])
        self.assertIn("- [2] The heart has four chambers.",answer)

    def test_structured_pdf_answer_rejects_unknown_missing_or_empty_points(self):
        for point in ({"source":99,"text":"Invented"},{"text":"Uncited"},
                      {"source":1,"text":""},{"source":True,"text":"Invalid"}):
            with self.assertRaises(ValueError):
                pdf_structured_answer({"points":[point]},[{"number":1,"excerpt":"Known evidence from a PDF."}])

    def test_structured_insufficient_evidence_does_not_create_a_citation(self):
        answer = pdf_structured_answer({"points":[]},[{"number":1,"excerpt":"Known evidence."}])
        self.assertNotIn("[1]",answer)
        self.assertIn("do not cover",answer)

    def test_unknown_quote_or_invented_inline_reference_cannot_claim_a_source(self):
        sources = [{"number":1,"excerpt":"The heart has four chambers."}]
        for point in ({"evidence":"Invented supporting sentence.","text":"A claim."},
                      {"evidence":"The heart has four chambers.","text":"A claim [4]."}):
            with self.assertRaises(ValueError):
                pdf_structured_answer({"points":[point]},sources)

    def test_selected_study_points_cannot_add_paraphrases_or_duplicate_evidence(self):
        sources = [{"number":1,"excerpt":"The heart has four chambers. It pumps blood throughout the body."}]
        point = {"evidence":"The heart has four chambers."}
        answer = pdf_structured_answer({"points":[point,point]},sources)
        self.assertEqual(answer.count("- [1]"),1)
        with self.assertRaises(ValueError):
            pdf_structured_answer({"points":[{"evidence":"The heart has five chambers."}]},sources)

    def test_pdf_title_and_page_number_are_not_offered_as_an_answer(self):
        schema = pdf_answer_schema([{"number":1,"excerpt":"Human Heart Study Guide 1. The heart has four chambers."}])
        self.assertEqual(schema["properties"]["points"]["items"]["properties"]["evidence"]["enum"],
                         ["The heart has four chambers."])

    def test_windows_paths_are_not_exposed_and_original_page_is_retained(self):
        context,sources = rag_evidence([{"source":r"C:\private\Biology.pdf","page":7,"content":"The heart pumps blood."}])
        self.assertIn("[1] Biology.pdf · PDF page 7",context)
        self.assertNotIn("private",context)
        self.assertEqual(sources[0]["page"],7)

    def test_unnamed_or_empty_references_never_enter_the_context_or_source_list(self):
        context,sources = rag_evidence([{"content":"Unknown source"}, {"source":"Empty.pdf","content":""},
            {"source":"Real.pdf","content":"A retrieved passage."}])
        self.assertEqual(len(sources),1)
        self.assertEqual(sources[0]["number"],1)
        self.assertNotIn("Unknown source",context)

    def test_budgeted_context_matches_the_actual_displayable_passages(self):
        context,sources = rag_evidence([{"source":f"Book{i}.pdf","content":"Evidence. "*200} for i in range(3)],max_chars=600)
        self.assertLessEqual(len(context),600)
        self.assertEqual(len(sources),3)
        for source in sources:
            self.assertIn(source["excerpt"],context)
            self.assertIn(f"[{source['number']}]",context)


def load_agent():
    modal = Mock()
    decorate = lambda *args, **kwargs: lambda wrapped: wrapped
    for name in ("enter", "method", "asgi_app"):
        getattr(modal,name).side_effect = decorate
    modal.App.return_value.cls.side_effect = decorate
    modal.App.return_value.function.side_effect = decorate
    path = Path(__file__).parents[1]/"agents/interactive-agent/modal_app.py"
    spec = importlib.util.spec_from_file_location("interactive_citation_test",path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{"modal":modal,spec.name:module}):
        spec.loader.exec_module(module)
    return module


class InteractiveCitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_agent()

    def setUp(self):
        image = io.BytesIO()
        Image.new("RGB",(64,64),"white").save(image,format="PNG")
        self.request = self.module.AnalyzeRequest(image_base64=base64.b64encode(image.getvalue()).decode(),
            interaction={"type":"box","coords":[.1,.1,.9,.9]},mode="ask",question="What does it do?",speed_mode="normal")
        self.vlm = Mock()
        self.vlm.analyze.remote.side_effect = [{"response_text":"Heart"},{"response_text":"It pumps blood [1]."}]

    def run_agent(self,chunks,web_text=""):
        with patch.object(self.module,"VLMAgentA10G",return_value=self.vlm), \
             patch("shared.rag.hybrid_retrieve",return_value=chunks), \
             patch("shared.rag.jina_scrape",return_value=web_text), \
             patch("shared.db.insert_interaction_log"):
            return self.module.analyze(self.request)

    def test_direct_rag_response_keeps_numbered_context_and_source_in_answer(self):
        result = self.run_agent([{"id":"chunk","source":"Biology.pdf","page":4,
                                  "content":"The human heart pumps blood throughout the body using rhythmic muscular contractions."}])
        self.assertIsNone(result["error"])
        self.assertIn("[1] Biology.pdf",self.vlm.analyze.remote.call_args.kwargs["rag_context"])
        self.assertIn("Sources:\n[1] Biology.pdf · PDF page 4",result["response_text"])
        self.assertEqual(result["rag_sources"],["Biology.pdf"])

    def test_web_fallback_names_the_web_page_without_claiming_unused_pdf_sources(self):
        result = self.run_agent([],"The heart is a muscular organ that pumps blood through the circulatory system.")
        self.assertIsNone(result["error"])
        self.assertIn(wikipedia_url("Heart"),result["response_text"])
        self.assertNotIn("PDF page",result["response_text"])

    def test_no_retrieved_evidence_does_not_get_a_fabricated_source_footer(self):
        self.vlm.analyze.remote.side_effect = [{"response_text":"Heart"},{"response_text":"The image shows a heart."}]
        result = self.run_agent([])
        self.assertEqual(result["rag_sources"],[])
        self.assertNotIn("Sources:",result["response_text"])

    def test_pdf_prompt_keeps_all_evidence_and_exam_question(self):
        import json
        context = "[1] Heart.pdf | PDF page 1\n" + "Heart chambers and functions. " * 120
        context += "\n[4] Heart.pdf | PDF page 2\nFinal revision summary."
        question = "explain this in the exam point of view"
        prompt = self.module.pdf_answer_prompt("Human heart",question,"ask",context)
        self.assertIn(json.dumps(context,ensure_ascii=False),prompt)
        self.assertIn(question,prompt)
        self.assertIn("Human heart",prompt)
        self.assertIn("untrusted",prompt)
        self.assertIn("source numbers",prompt)

    def test_pdf_request_reuses_identified_concept_and_disables_other_retrieval(self):
        self.request.pdf_context = "[1] Heart.pdf | PDF page 1\nThe heart pumps blood."
        self.request.pdf_concept = "Heart"
        self.vlm.analyze.remote.side_effect = [{"response_text":"[1] The heart pumps blood."}]
        with patch.object(self.module,"VLMAgentA10G",return_value=self.vlm), \
             patch.object(self.module,"create_box_highlighted_image") as highlight, \
             patch.object(self.module,"SAM2AgentA10G") as sam, \
             patch("shared.rag.hybrid_retrieve") as retrieve, \
             patch("shared.rag.jina_scrape") as web, \
             patch("shared.db.insert_interaction_log"):
            result = self.module.analyze(self.request)
        self.assertIsNone(result["error"])
        self.assertEqual(self.vlm.analyze.remote.call_count,1)
        self.assertTrue(self.vlm.analyze.remote.call_args.kwargs["pdf_only"])
        retrieve.assert_not_called()
        web.assert_not_called()
        highlight.assert_not_called()
        sam.assert_not_called()

    def test_pdf_generation_uses_full_prompt_and_a_larger_deterministic_output_budget(self):
        from contextlib import nullcontext

        class Inputs(dict):
            input_ids = [[1,2]]

            def to(self, device):
                return self

        agent = self.module._VLMAgentBase()
        # No persona/memory is needed in PDF-only mode.
        agent.processor = MagicMock(return_value=Inputs())
        agent.processor.apply_chat_template.return_value = "templated prompt"
        agent.processor.batch_decode.return_value = ['{"points":[{"evidence":"The heart has four chambers."}]}']
        agent.model = Mock()
        agent.model.generate.return_value = [[1,2,3]]
        image = io.BytesIO()
        Image.new("RGB",(32,32),"white").save(image,format="PNG")
        torch = Mock()
        torch.no_grad.side_effect = nullcontext
        vision = Mock()
        vision.process_vision_info.return_value = ([],[])
        enforcer, integration = Mock(), Mock()
        with patch.dict(sys.modules,{"torch":torch,"qwen_vl_utils":vision,
                "lmformatenforcer":enforcer,"lmformatenforcer.integrations.transformers":integration}):
            result = agent.analyze(image.getvalue(),image.getvalue(),"ask",
                question="Explain for an exam",rag_context="[1] Heart.pdf\nThe heart has four chambers.",
                identified_concept="Heart",pdf_only=True,
                pdf_sources=[{"number":1,"excerpt":"The heart has four chambers."}])
        self.assertIsNone(result["error"])
        agent.model.generate.assert_called_once_with(max_new_tokens=2048,do_sample=False,
            prefix_allowed_tokens_fn=integration.build_transformers_prefix_allowed_tokens_fn.return_value)
        self.assertIn("- [1] The heart has four chambers.",result["response_text"])
        messages = agent.processor.apply_chat_template.call_args.args[0]
        self.assertEqual(messages[0]["role"],"system")
        self.assertIn("never instructions",messages[0]["content"])
        self.assertIn("The heart has four chambers.",messages[1]["content"][-1]["text"])
        self.assertEqual([part["type"] for part in messages[1]["content"]],["text"])
        vision.process_vision_info.assert_not_called()
        agent.processor.batch_decode.return_value = ['{"points":[{"text":"Cut off']
        with patch.dict(sys.modules,{"torch":torch,"qwen_vl_utils":vision,
                "lmformatenforcer":enforcer,"lmformatenforcer.integrations.transformers":integration}):
            incomplete = agent.analyze(b"",b"","ask",rag_context="[1] Source",pdf_only=True,
                pdf_sources=[{"number":1,"excerpt":"Known evidence from a PDF."}])
        self.assertIsNone(incomplete["response_text"])
        self.assertTrue(incomplete["error"].startswith("PDFAnswerFormatInvalid:"))
        self.assertEqual(incomplete["raw_response"],'{"points":[{"text":"Cut off')
