"""Citation provenance through retrieval, answer formatting and the direct agent."""
import base64
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from PIL import Image
from shared.citations import cited_sources, sourced_answer
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
