FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/quiz/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    ANONYMIZED_TELEMETRY=false
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
# EC2 only computes small embeddings. Qwen stays on the existing Modal GPU API.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt \
    && pip check
RUN useradd --create-home --uid 10001 quiz
COPY --chown=quiz:quiz app ./app
COPY --chown=quiz:quiz scripts/migrate.py ./scripts/migrate.py
COPY --chown=quiz:quiz scripts/import_sqlite.py ./scripts/import_sqlite.py
COPY --chown=quiz:quiz migrations ./migrations
RUN mkdir -p /app/db /app/data && chown -R quiz:quiz /app /home/quiz
USER quiz
# Bake the small retrieval model into the image so first upload needs no download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
EXPOSE 8000
# One process owns the SQLite graph checkpoints and background generation tasks.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
