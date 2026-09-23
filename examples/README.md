# Example runs

Three real `standard`-depth runs, exported with `scripts/export_example.py`:

| Folder | Prompt |
|---|---|
| `stripe-billing/` | Give me a competitive analysis of Stripe's new billing features |
| `vector-databases/` | Compare the leading vector databases for production RAG in 2026: Pinecone, Qdrant, Weaviate and pgvector, covering features, performance claims and pricing |
| `eu-ai-act-gpai/` | What obligations does the EU AI Act place on providers of general-purpose AI models, and what is the compliance timeline through 2027? |

Each folder contains:

- `report.md`: the briefing. `[n]` citations resolve to the References list. A † marks a
  statement the auditor still flagged after its revision round.
- `events.jsonl`: every agent event, so `research replay examples/<name> --speed 8` re-renders
  the run exactly.
- `metrics.json`: per-agent tokens and cost, the token funnel, Critic verdict counts, audit
  rounds.
- `sources.json` and `sub_queries.json`: the pages read and the research questions.
- `run.json`: prompt, depth, and the public LangSmith trace where one is shared (the Stripe run).

The reports reflect the web as it was on the run date. Treat single-source and contradicted
claims as leads to confirm.
