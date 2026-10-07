"""(Re)build the search index: split documents into passages, embed with Bedrock, store.

Works for both setups, using the same settings as the server:
- local: sample + user JSON files, indexed into Qdrant
- AWS:   sample documents are seeded into DynamoDB, then everything in the
         table is indexed into S3 Vectors

Safe to re-run: passages are replaced, not duplicated.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from homedocs_mcp import config
from homedocs_mcp.store import load_documents


def main() -> int:
    parser = argparse.ArgumentParser(description="Index household documents for search.")
    parser.add_argument(
        "path", nargs="?", type=Path, default=config.DATA_PATH,
        help="sample documents JSON file (default: HOMEDOCS_DATA or the bundled sample file)",
    )
    args = parser.parse_args()

    try:
        store = config.make_store()
        searcher = config.make_searcher(store)
        seed = load_documents(args.path)
        if hasattr(store, "put"):  # DynamoDB: make sure the sample documents are in the table
            for doc in seed:
                store.put(doc)
        docs = {d.id: d for d in seed} | {d.id: d for d in store.list_all()}
        for doc in docs.values():
            count = searcher.index(doc)
            print(f"{doc.id}: {count} passages")
    except (ClientError, BotoCoreError) as e:
        print(f"AWS error: {e}", file=sys.stderr)
        return 1
    print(f"Indexed {len(docs)} documents ({config.STORE_MODE} store, {config.SEARCH_MODE} search).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
