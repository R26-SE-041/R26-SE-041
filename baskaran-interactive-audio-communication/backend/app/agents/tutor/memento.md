# Tutor Agent Session Memento

This file defines the schema and limits for temporary, session-level context. It is not a store for user data.

Allowed fields:

- `language`: the currently selected response language.
- `document_ids`: identifiers of documents relevant to the current retrieval.
- `topic`: a short current topic label when it is known from the workflow.
- `previous_question`: a short, relevant previous question.
- `previous_answer_summary`: a short summary of the previous grounded answer.
- `rag_source_references`: identifiers of the sources used for the current answer.
- `session_id`: an opaque session identifier used only for the temporary session state.

Rules:

- Keep the memento in session memory only, with a short TTL. Do not persist full conversation history indefinitely.
- Use previous-turn context only for a clearly related follow-up; unrelated questions must not inherit old context.
- Do not store passwords, tokens, API keys, authentication credentials, or unnecessary personal information.
- Do not include full private documents in the memento; document text remains in the RAG pipeline.
