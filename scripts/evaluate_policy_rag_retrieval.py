from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.rag_policy.config import PolicyRAGSettings, get_policy_rag_settings
from packages.rag_policy.evaluation.dataset import load_evaluation_dataset
from packages.rag_policy.evaluation.evaluator import PolicyRAGEvaluator
from packages.rag_policy.ingestion.indexer import PolicyDocumentIndexer
from packages.rag_policy.service import PolicyRAGService


VARIANTS = {
    "local_none": {"use_mock": True, "reranker_mode": "none"},
    "local_lexical": {"use_mock": True, "reranker_mode": "lexical"},
    "local_semantic": {"use_mock": True, "reranker_mode": "semantic"},
    "milvus_none": {"use_mock": False, "reranker_mode": "none"},
    "milvus_lexical": {"use_mock": False, "reranker_mode": "lexical"},
    "milvus_semantic": {"use_mock": False, "reranker_mode": "semantic"},
}


def _settings_for_variant(
    base: PolicyRAGSettings,
    variant: str,
    args: argparse.Namespace,
) -> PolicyRAGSettings:
    overrides = VARIANTS[variant]
    return replace(
        base,
        use_mock=overrides["use_mock"],
        policy_dir=Path(args.policy_dir),
        milvus_uri=args.milvus_uri,
        milvus_collection=args.milvus_collection,
        embedding_provider=args.embedding_provider,
        embedding_model=args.openai_embedding_model,
        embedding_model_path=Path(args.embedding_model_path),
        candidate_top_n=args.candidate_top_n,
        rerank_top_m=args.rerank_top_m,
        reranker_mode=overrides["reranker_mode"],
        rrf_k=args.rrf_k,
    )


def _evaluate_variant(
    name: str,
    settings: PolicyRAGSettings,
    dataset_path: Path,
    ingest: bool,
) -> dict:
    if not settings.use_mock:
        if not settings.milvus_uri:
            return {"variant": name, "status": "skipped", "reason": "MILVUS_URI is empty"}
        if ingest:
            ingestion = PolicyDocumentIndexer(settings).index_directory(settings.policy_dir)
        else:
            ingestion = None
    else:
        ingestion = None

    dataset = load_evaluation_dataset(dataset_path)
    service = PolicyRAGService(settings)
    report = PolicyRAGEvaluator(service).evaluate(dataset)
    payload = report.model_dump(mode="json")
    payload.update(
        {
            "variant": name,
            "status": "ok",
            "settings": {
                "use_mock": settings.use_mock,
                "milvus_collection": settings.milvus_collection,
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
                "embedding_model_path": str(settings.embedding_model_path),
                "candidate_top_n": settings.candidate_top_n,
                "reranker_mode": settings.reranker_mode,
                "rrf_k": settings.rrf_k,
            },
            "ingestion": ingestion.model_dump(mode="json") if ingestion else None,
        }
    )
    return payload


def main() -> None:
    base = get_policy_rag_settings()
    parser = argparse.ArgumentParser(
        description="Evaluate CatalogOps policy retrieval with local and Milvus backends."
    )
    parser.add_argument(
        "--dataset",
        default=str(ROOT / "data" / "eval" / "ecommerce_policy_eval.json"),
        help="Evaluation JSON/JSONL with question and expected_doc_ids fields.",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "data" / "eval" / "policy_rag_retrieval_eval.json"),
        help="Where to write the retrieval report JSON.",
    )
    parser.add_argument("--policy-dir", default=str(base.policy_dir))
    parser.add_argument("--milvus-uri", default=base.milvus_uri)
    parser.add_argument("--milvus-collection", default=base.milvus_collection)
    parser.add_argument(
        "--embedding-provider",
        default="minilm",
        choices=["openai", "minilm", "local_minilm"],
    )
    parser.add_argument("--openai-embedding-model", default=base.embedding_model)
    parser.add_argument("--embedding-model-path", default=str(base.embedding_model_path))
    parser.add_argument("--candidate-top-n", type=int, default=base.candidate_top_n)
    parser.add_argument("--rerank-top-m", type=int, default=base.rerank_top_m)
    parser.add_argument("--rrf-k", type=int, default=base.rrf_k)
    parser.add_argument(
        "--variants",
        default="local_none,local_lexical,local_semantic,milvus_none,milvus_lexical,milvus_semantic",
        help=f"Comma-separated variants. Available: {', '.join(VARIANTS)}",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Do not ingest policy docs before Milvus variants.",
    )
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    output_path = Path(args.output)
    requested = [item.strip() for item in args.variants.split(",") if item.strip()]
    unknown = [item for item in requested if item not in VARIANTS]
    if unknown:
        raise SystemExit(f"Unknown variants: {', '.join(unknown)}")

    results = []
    for variant in requested:
        settings = _settings_for_variant(base, variant, args)
        results.append(
            _evaluate_variant(
                variant,
                settings,
                dataset_path,
                ingest=not args.no_ingest,
            )
        )

    payload = {
        "dataset": str(dataset_path),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
