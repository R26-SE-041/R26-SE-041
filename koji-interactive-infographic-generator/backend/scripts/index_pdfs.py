"""Index educational PDFs into the Supabase knowledge store."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from shared.rag import index_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--subject", default=None)
    args = parser.parse_args()

    total = 0
    for pdf in args.pdfs:
        if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
            parser.error(f"Not a readable PDF: {pdf}")
        count = index_pdf(str(pdf.resolve()), subject=args.subject)
        total += count
        print(f"Indexed {count} chunks from {pdf}")
    print(f"Indexed {total} chunks total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

