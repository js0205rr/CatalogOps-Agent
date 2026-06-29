from __future__ import annotations

import argparse
import json
from pathlib import Path

from packages.agent_core.single_graph import run_product_review
from packages.batch_analysis.batch_graph import run_batch_review
from packages.catalog.schemas import ProductInput


def cmd_single(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.product_json).read_text(encoding="utf-8"))
    result = run_product_review(ProductInput.model_validate(payload))
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    result = run_batch_review(args.csv)
    print(result.report_markdown)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="catalogops")
    sub = parser.add_subparsers(dest="command", required=True)

    single = sub.add_parser("single", help="review one ProductInput JSON file")
    single.add_argument("--product-json", required=True)
    single.set_defaults(func=cmd_single)

    batch = sub.add_parser("batch", help="review a catalog CSV file")
    batch.add_argument("--csv", required=True)
    batch.set_defaults(func=cmd_batch)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
