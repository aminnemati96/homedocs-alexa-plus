"""Load documents into Qdrant: split into passages, embed with Bedrock, upsert.

Safe to re-run: each document's old passages are replaced.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

from homedocs_mcp import config
from homedocs_mcp.store import load_documents


def main() -> int:
    parser = argparse.ArgumentParser(description="Index household documents into Qdrant.")
    parser.add_argument(
        "path", nargs="?", type=Path, default=config.DATA_PATH,
        help="documents JSON file (default: HOMEDOCS_DATA or the sample file)",
    )
    args = parser.parse_args()

    searcher = config.make_vector_searcher()
    try:
        searcher.ensure_collection()
        # User-added documents are indexed when saved; re-indexing them here
        # rebuilds everything after a Qdrant reset.
        for doc in load_documents(args.path) + load_documents(config.USER_DATA_PATH):
            count = searcher.index(doc)
            print(f"{doc.id}: {count} passages")
    except (ClientError, BotoCoreError) as e:
        print(f"AWS error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
