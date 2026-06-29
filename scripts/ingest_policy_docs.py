from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.rag_policy.config import get_policy_rag_settings
from packages.rag_policy.ingestion.indexer import PolicyDocumentIndexer


def main() -> None:
    settings = get_policy_rag_settings()
    parser = argparse.ArgumentParser(
        description="Ingest CatalogOps policy Markdown documents"
    )
    parser.add_argument(
        "--path",
        default=str(settings.policy_dir),
        help="Policy document directory",
    )
    args = parser.parse_args()

    result = PolicyDocumentIndexer(settings).index_directory(args.path)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
