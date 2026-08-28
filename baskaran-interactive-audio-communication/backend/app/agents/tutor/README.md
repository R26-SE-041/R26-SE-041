# Tutor Agent Configuration

- `skills.md` defines what the Tutor Agent can and should do.
- `persona.md` defines how the Tutor Agent communicates.
- `memento.md` defines which contextual, session-level information may be remembered.

The backend loads `skills.md` and `persona.md` for each Tutor request and sends them as bounded agent instructions. It builds a separate, temporary memento from the allowed session fields only when a question is a related follow-up. Retrieved RAG context is supplied separately and cannot override the Tutor or system instructions.

These files improve agent behaviour, consistency, and maintainability. They do **not** fine-tune or modify the underlying Gemma model weights.
