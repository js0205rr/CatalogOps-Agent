# CatalogOps-Agent

[English](README.md) | 中文

CatalogOps-Agent 是一个以规则优先、证据驱动的商品目录治理系统，面向电商商品上架前审核场景。它结合了 LangGraph 多智能体编排、类目预测、必填属性检查、标题校验与策略检索，输出可解释的审核结论。

本 MVP 主要面向文本和 CSV 商品目录数据。它不审核图片，不执行模型生成代码，并保留 mock 模式，便于在本地和 Notebook 中进行可重复、确定性的实验。LLM 调用是可选的，并由配置控制。

每一个上架决策都必须对应证据。如果证据不足，问题会被降级为不确定或人工复核路径，而不是被直接当作最终自动结论。

## 当前基线

正式评测已覆盖 Ecommerce Text Classification 的四个一级领域：`Books`、`Clothing & Accessories`、`Electronics` 和 `Household`。完整基准使用 `dataset/processed/ecommerce_text_classification`。

最新全量 mock 模式基线：

| 指标 | 全量数据集 |
| --- | ---: |
| 行数 | 27,548 |
| 类目准确率 | 89.32% |
| 问题宏平均 F1 | 0.7728 |
| 类目不匹配 precision / recall / F1 | 0.6961 / 0.9502 / 0.8036 |
| 属性缺失 precision / recall / F1 | 0.9688 / 0.8663 / 0.9147 |
| 标题问题 precision / recall / F1 | 0.2667 / 1.0000 / 0.4211 |
| 任意问题 precision / recall / F1 | 0.9780 / 0.9272 / 0.9519 |
| 证据覆盖率 | 100.00% |
| 策略上下文命中率 | 100.00% |
| 全量复核行数 | 21,958 |
| 运行时间 | 964.327s |
| 估算 LLM 调用 / token 成本 | 0 / $0.00 |

更多 400 行、5,000 行和全量数据集对比请参见 `docs/EVALUATION.md`。

## 项目结构

- `apps/api`：FastAPI 服务、REST 接口、WebSocket trace。
- `apps/web`：React 操作工作台。
- `packages/agent_core`：单商品 LangGraph 审核工作流。
- `packages/catalog`：Pydantic 领域模型。
- `packages/rag_policy`：策略检索、导入、本地 mock 检索器和 RAG 工具。
- `packages/batch_analysis`：批量 CSV 分析、选择性复核和报告生成。
- `packages/observability`：trace 辅助工具。
- `packages/evaluation`：评测导出与指标。
- `packages/mocks`：mock 模式配置与可选 LLM 封装。
- `data`：示例商品、类目树、策略文档和评测数据。
- `scripts`：本地 CLI 工具。
- `tests`：冒烟测试和工作流测试。
- `docs`：规范、架构和演示脚本。

## API

- `GET /health`
- `POST /api/reviews/single`
- `POST /api/batch/upload`
- `POST /api/batch/{batch_id}/run`
- `GET /api/batch/{batch_id}/report`
- `POST /api/documents/upload`
- `POST /api/documents/ingest`
- `GET /api/documents`
- `POST /api/chat/policy`
- `POST /api/policy/category`
- `POST /api/policy/attributes`
- `POST /api/policy/title`
- `WebSocket /api/runs/{run_id}/events`

默认启用 mock 模式：`CATALOGOPS_MOCK_LLM=true`，因此基础商品审核、批量审核、策略检索和冒烟测试都不需要 API Key、Milvus 或 PostgreSQL。

### 策略文档导入

```bash
python scripts/ingest_policy_docs.py
```

`USE_MOCK=true` 会在本地写入确定性的策略索引，不依赖 Milvus 或 embedding 服务。
将 `USE_MOCK=false`、`MILVUS_URI` 和 `POLICY_EMBEDDING_PROVIDER=minilm` 设置后，可使用本地 MiniLM 模型将策略分片导入 Milvus。

### 策略检索评测

```bash
python scripts/evaluate_policy_rag_retrieval.py
```

未设置 `MILVUS_URI` 时，脚本会评估本地检索 / reranker 变体并跳过 Milvus 变体。设置 `MILVUS_URI` 后，脚本会导入策略文档，并比较 Milvus dense retrieval 与 `none`、`lexical`、`semantic` 三种 reranker 模式。

### 商品治理正式评测

```bash
python scripts/evaluate_catalogops_formal.py --sample-size 5000 --output-dir dataset/processed/evaluation_5000 --skip-raw-batch-report
python scripts/evaluate_catalogops_formal.py --sample-size 999999 --output-dir dataset/processed/evaluation_full --skip-raw-batch-report
```

`--skip-raw-batch-report` 会保留 summary、markdown report 和 prediction CSV，同时避免生成体积很大的 raw batch JSON 文件。
