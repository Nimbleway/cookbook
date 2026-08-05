"""Build or update the index from the corpus on disk.

Separate from research on purpose: researching is slow and billable, indexing is
fast and cheap, and conflating them means a re-index costs agent runs. Run this
after prewarm.py, after refresh.py, or after recover_runs.py.

    ./.venv/bin/python build_index.py
    ./.venv/bin/python build_index.py --samples   # build from the shipped samples

Only this script and the query path need an embedding model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")
sys.path.insert(0, str(HERE))

from desk import ingest  # noqa: E402
from desk.models import configure_models  # noqa: E402


def _indexed_ids(storage: Path) -> set[str]:
    """Document ids currently in the docstore."""
    path = storage / "docstore.json"
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return set((data.get("docstore/ref_doc_info") or {}).keys())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", action="store_true",
                        help="force building from data/samples/")
    parser.add_argument("--runs", action="store_true",
                        help="force building from data/runs/")
    parser.add_argument("--storage", default=None, help="override the storage dir")
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is not set — embeddings need it.", file=sys.stderr)
        print("The corpus and every agent run work without it; only the index does not.",
              file=sys.stderr)
        return 2

    configure_models()

    # Default to whatever the app will read (USE_LIVE decides), because an index built
    # from one directory while the app reads another contradicts itself in front of the
    # user — the sidebar calls a fact fresh while the retrieval guard withholds it.
    if args.samples:
        source = ingest.SAMPLES_DIR
    elif args.runs:
        source = ingest.RUNS_DIR
    else:
        source = ingest.active_dir()
    records = ingest.load_records(source)
    if not records:
        print(f"no records in {source} — run prewarm.py first", file=sys.stderr)
        return 2

    documents = ingest.to_documents(records)
    storage = Path(args.storage) if args.storage else ingest.STORAGE_DIR
    existed = (storage / "docstore.json").exists()

    print(f"{len(documents)} document(s) from {source.name}/")
    print(f"{'updating' if existed else 'creating'} index at {storage.name}/")

    before = _indexed_ids(storage)
    index, _ = ingest.build_index(documents, storage_dir=storage)
    after = _indexed_ids(storage)

    # Reported from the docstore rather than from refresh_ref_docs' return value:
    # that came back all-False on a run which had just inserted two new documents,
    # so trusting it printed "0 embedded" while the corpus had visibly grown.
    added = sorted(after - before)
    if added:
        print(f"done — {len(added)} document(s) added:")
        for doc_id in added:
            print(f"    + {doc_id}")
        print(f"  {len(after) - len(added)} already present (unchanged content is not "
              "re-embedded)")
    else:
        print(f"done — {len(after)} document(s) in the index, none added")

    cov = ingest.coverage(records)
    print(f"coverage: {cov['rate_docs']} base rate(s) over "
          f"{len(cov['hts_codes'])} code(s), {cov['overlay_docs']} lane overlay(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
