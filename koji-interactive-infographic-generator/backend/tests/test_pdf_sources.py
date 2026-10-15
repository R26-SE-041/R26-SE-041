"""PDF source isolation, extraction failures and durable question provenance. No GPU calls."""
import base64
import os
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from studio.documents import Documents, MAX_PDF_BYTES, checked_pdf_answer, evidence_context, extract_chunks, filename_for_upload
from studio.main import app, require_user
from studio.pipeline import Pipeline
from studio.schemas import AnalysisRequest


class ExtractionTests(TestCase):
    def test_real_text_pdf_preserves_source_pages(self):
        writer=PdfWriter()
        for text in ("Heart overview", "Left ventricle pumps blood at high pressure"):
            page=writer.add_blank_page(width=300,height=200)
            font=DictionaryObject({NameObject("/Type"):NameObject("/Font"),NameObject("/Subtype"):NameObject("/Type1"),NameObject("/BaseFont"):NameObject("/Helvetica")})
            page[NameObject("/Resources")]=DictionaryObject({NameObject("/Font"):DictionaryObject({NameObject("/F1"):writer._add_object(font)})})
            stream=DecodedStreamObject(); stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode())
            page[NameObject("/Contents")]=writer._add_object(stream)
        output=BytesIO(); writer.write(output)
        chunks,pages,skipped=extract_chunks(output.getvalue())
        self.assertEqual((pages,skipped),(2,0))
        self.assertEqual(chunks[1]["page"],2)
        self.assertIn("high pressure",chunks[1]["content"])

    def test_page_numbers_survive_chunking_and_empty_pages_are_reported(self):
        with patch("pypdf.PdfReader") as reader:
            reader.return_value.is_encrypted = False
            reader.return_value.pages = [Mock(extract_text=Mock(return_value="")),
                Mock(extract_text=Mock(return_value="Left ventricle pumps blood. " * 90))]
            chunks, pages, skipped = extract_chunks(b"%PDF-1.7 test")
        self.assertEqual((pages, skipped), (2, 1))
        self.assertGreater(len(chunks), 1)
        self.assertEqual({c["page"] for c in chunks}, {2})
        self.assertTrue(all(len(c["content"]) <= 900 for c in chunks))

    def test_blank_scanned_and_encrypted_pdfs_give_actionable_errors(self):
        writer = PdfWriter(); writer.add_blank_page(width=200, height=200)
        output = BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError,"OCR"):
            extract_chunks(output.getvalue())
        writer.encrypt("secret"); output = BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError,"Password-protected"):
            extract_chunks(output.getvalue())
        with self.assertRaisesRegex(ValueError,"valid PDF"):
            extract_chunks(b"not a PDF")

    def test_selection_contract_deduplicates_and_rejects_non_uuid_ids(self):
        document = uuid4()
        data = dict(id="q",mode="ask",question="Why?",interaction={"type":"point","coords":[.5,.5]})
        self.assertEqual(AnalysisRequest(**data,document_ids=[document,document]).document_ids,[document])
        with self.assertRaises(ValueError):
            AnalysisRequest(**data,document_ids=["somebody-elses-file"])
        self.assertEqual(filename_for_upload("../notes.pdf"),"notes.pdf")

    def test_retrieval_without_sources_does_not_load_the_embedding_model(self):
        with patch("studio.documents.embed_texts") as embed:
            self.assertEqual(Documents().retrieve("owner",[],"question"),[])
            embed.assert_not_called()

    def test_evidence_retains_original_document_page_and_passage(self):
        context, sources = evidence_context([{"document_id":"doc","filename":"Notes.pdf","page":7,"content":"Evidence text."}])
        self.assertIn("[1] Notes.pdf | PDF page 7", context)
        self.assertEqual(sources[0]["excerpt"],"Evidence text.")

    def test_missing_or_invented_citations_are_not_presented_as_sourced_answers(self):
        sources=[{"number":1,"filename":"Notes.pdf","page":7}]
        self.assertEqual(checked_pdf_answer("High pressure [1].",sources),"High pressure [1].\n\nSources:\n[1] Notes.pdf · PDF page 7")
        for answer in ("Uncited explanation.","Invented reference [42]."):
            self.assertIn("valid references",checked_pdf_answer(answer,sources))

    def test_source_footer_uses_only_cited_metadata_and_replaces_model_bibliography(self):
        sources=[{"number":1,"filename":"Biology.pdf","page":9},
                 {"number":2,"filename":"Unused.pdf","page":3}]
        answer=checked_pdf_answer("It pumps blood [1].\n\nSources:\n[1] Invented website",sources)
        self.assertIn("[1] Biology.pdf · PDF page 9",answer)
        self.assertNotIn("Unused.pdf",answer)
        self.assertNotIn("Invented",answer)
        self.assertEqual(checked_pdf_answer(answer,sources),answer)

    def test_bibliography_only_does_not_count_as_citing_the_answer(self):
        self.assertIn("valid references",checked_pdf_answer("Uncited answer.\n\nSources:\n[1] Notes.pdf",[
            {"number":1,"filename":"Notes.pdf","page":7}]))


class PdfApiTests(TestCase):
    def setUp(self):
        self.owner = str(uuid4())
        app.dependency_overrides[require_user] = lambda: self.owner
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_upload_is_authenticated_and_rejects_wrong_content_before_storage(self):
        with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
            repo.get_chat.return_value = {"id":"chat"}
            route = "/studio/documents?filename=notes.pdf"
            self.assertEqual(self.client.post(route,content=b"fake",headers={"Content-Type":"text/plain"}).status_code,415)
            self.assertEqual(self.client.post(route,content=b"fake",headers={"Content-Type":"application/pdf"}).status_code,422)
            storage.assert_not_called()
            app.dependency_overrides.clear()
            self.assertEqual(self.client.post(route,content=b"%PDF-1.7",headers={"Content-Type":"application/pdf"}).status_code,401)

    def test_upload_size_is_bounded_before_storage(self):
        with patch("studio.main.repo") as repo, patch("studio.main.Storage") as storage:
            repo.get_chat.return_value = {"id":"chat"}
            response = self.client.post("/studio/documents?filename=notes.pdf",
                content=b"%PDF-"+b"x"*MAX_PDF_BYTES,headers={"Content-Type":"application/pdf"})
            self.assertEqual(response.status_code,413)
            storage.assert_not_called()

    def test_workspace_library_does_not_require_an_image_or_chat(self):
        with patch("studio.main.documents") as documents, patch("studio.main.repo") as repo:
            documents.list.return_value=[]
            response=self.client.get("/studio/documents")
            self.assertEqual(response.status_code,200)
            documents.list.assert_called_once_with(self.owner)
            repo.get_chat.assert_not_called()

    def test_selected_foreign_pdf_prevents_question_job_creation(self):
        with patch("studio.main.repo") as repo, patch("studio.main.documents") as documents, patch.dict(os.environ,{"INTERACTIVE_AGENT_URL":"https://models.example"}):
            repo.get_history.return_value={"id":"image","metadata":{"chatId":"chat"}}
            documents.selected.side_effect=LookupError("PDF not found")
            response=self.client.post("/studio/jobs",json={"request_id":str(uuid4()),"kind":"analysis","generation_id":str(uuid4()),
                "analysis":{"id":"q","mode":"ask","question":"Why?","interaction":{"type":"point","coords":[.5,.5]},"document_ids":[str(uuid4())]}})
            self.assertEqual(response.status_code,404)
            repo.create_job.assert_not_called()
            self.assertEqual(documents.selected.call_args.args[0],self.owner)

    def test_pdf_url_uses_owner_and_never_signs_missing_documents(self):
        identifier=str(uuid4())
        with patch("studio.main.documents") as documents, patch("studio.main.Storage") as storage:
            documents.get.return_value=None
            response=self.client.get(f"/studio/documents/{identifier}/url")
            self.assertEqual(response.status_code,404)
            documents.get.assert_called_once_with(self.owner,identifier)
            storage.assert_not_called()

    def test_failed_registration_cleans_up_uploaded_object(self):
        with patch("studio.main.repo") as repo,patch("studio.main.documents") as documents,patch("studio.main.Storage") as storage:
            repo.get_chat.return_value={"id":"chat"}
            storage.return_value.upload.return_value="owner/documents/upload.pdf"
            documents.register.side_effect=OverflowError("Finish an active job")
            response=self.client.post("/studio/documents?filename=notes.pdf",content=b"%PDF-1.7",headers={"Content-Type":"application/pdf"})
            self.assertEqual(response.status_code,429)
            storage.return_value.remove.assert_called_once_with(["owner/documents/upload.pdf"])


class PdfPipelineTests(TestCase):
    def setUp(self):
        self.owner=str(uuid4()); self.doc=str(uuid4()); self.generation=str(uuid4())
        self.repo,self.storage=Mock(),Mock()
        self.repo.get_history.return_value={"id":self.generation,"image_path":"owner/image.png","metadata":{"chatId":"chat"}}
        self.repo.heartbeat.return_value=True
        self.storage.download.return_value="image"
        self.pipeline=Pipeline(self.repo,self.storage)
        self.pipeline.invoke=Mock(side_effect=[{"identified_concept":"Left ventricle"},{"response_text":"It pumps blood [1]."}])
        self.job={"id":str(uuid4()),"user_id":self.owner,"kind":"analysis","state":{},"payload":{
            "generation_id":self.generation,"speed_mode":"pro","analysis":{"id":"q","mode":"ask","question":"Why is its wall thick?",
                "interaction":{"type":"point","coords":[.4,.6]},"document_ids":[self.doc]}}}

    def test_pdf_query_combines_actual_question_and_selected_concept(self):
        with patch("studio.documents.Documents") as documents:
            documents.return_value.retrieve.return_value=[{"document_id":self.doc,"page":9,"filename":"Notes.pdf","content":"The ventricle pumps blood at high pressure."}]
            self.pipeline.process_source(self.job)
            args=documents.return_value.retrieve.call_args.args
            self.assertEqual(args[:2],(self.owner,[self.doc]))
            self.assertIn("Left ventricle",args[2]); self.assertIn("Why is its wall thick?",args[2])
            payload=self.pipeline.invoke.call_args.args[3]
            self.assertFalse(payload["enable_rag"])
            self.assertIn("PDF page 9",payload["pdf_context"])
            saved=self.repo.append_interaction.call_args.args[2]
            self.assertEqual(saved["documentIds"],[self.doc]); self.assertEqual(saved["grounding"],"pdf")
            self.assertEqual(saved["sources"][0]["page"],9)
            self.assertIn("Sources:\n[1] Notes.pdf · PDF page 9",saved["answer"])

    def test_no_evidence_abstains_without_a_general_knowledge_answer(self):
        with patch("studio.documents.Documents") as documents:
            documents.return_value.retrieve.return_value=[]
            self.pipeline.process_source(self.job)
            self.assertEqual(self.pipeline.invoke.call_count,1)
            saved=self.repo.append_interaction.call_args.args[2]
            self.assertEqual(saved["grounding"],"no_match")
            self.assertEqual(saved["sources"],[])
            self.assertIn("selected PDFs",saved["answer"])

    def test_unselected_question_does_not_search_any_pdf(self):
        self.job["payload"]["analysis"]["document_ids"]=[]
        self.pipeline.invoke=Mock(return_value={"response_text":"Image answer"})
        with patch("studio.documents.Documents") as documents:
            self.pipeline.process_source(self.job)
            documents.assert_not_called()
            self.assertFalse(self.pipeline.invoke.call_args.args[3]["enable_rag"])
            self.assertEqual(self.repo.append_interaction.call_args.args[2]["grounding"],"image")

    def test_missing_image_concept_does_not_retrieve_random_pdf_evidence(self):
        self.pipeline.invoke=Mock(return_value={"response_text":""})
        with patch("studio.documents.Documents") as documents:
            with self.assertRaisesRegex(RuntimeError,"could not be identified"):
                self.pipeline.process_source(self.job)
            documents.return_value.retrieve.assert_not_called()
