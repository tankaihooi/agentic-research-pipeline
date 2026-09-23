# Evaluation results

Fixtures: `eu-ai-act`, `stripe-billing`, `vector-dbs`

## Critic: planted fabrications

**Caught 114/116 (98%) planted fabrications; wrongly rejected 3/113 (3%) reference-supported real findings.**

Across 3 independent repeats: plants caught 97% mean (range 97%-98%), false rejections 3% mean (range 3%-4%). Tables below are repeat 1.

| Plant type | Caught |
|---|---|
| fabricated_quote | 30/30 (100%) |
| unsupported_claim | 30/30 (100%) |
| distorted_number | 29/30 (97%) |
| wrong_entity | 25/26 (96%) |

| Checks enabled | Plants caught |
|---|---|
| grounding (cumulative) | 30/116 (26%) |
| entailment (cumulative) | 114/116 (98%) |
| cross-reference (cumulative) | 114/116 (98%) |

Real findings sampled: 120 · of the ones the reference judge called unsupported, the Critic rejected 5/7 (71%) · rejection precision 5/8 (62%).

## Ablation: the same evidence, with and without the Critic

Every real finding plus the valid plants go to the Writer. The plant funnel counts plants that reached the Writer → were picked by the outline → were cited in first drafts → were still cited after the auditor's revision round.

| Fixture | Condition | Plant funnel | Unsupported statements | Not fully supported | Statements |
|---|---|---|---|---|---|
| eu-ai-act | critic-off | 36 → 0 → 0 → 0 | 0% | 3% | 70 |
| eu-ai-act | critic-on | 1 → 0 → 0 → 0 | 0% | 1% | 78 |
| stripe-billing | critic-off | 40 → 3 → 3 → 3 | 2% | 17% | 105 |
| stripe-billing | critic-on | 0 → 0 → 0 → 0 | 0% | 12% | 97 |
| vector-dbs | critic-off | 40 → 1 → 1 → 1 | 1% | 4% | 118 |
| vector-dbs | critic-on | 0 → 0 → 0 → 0 | 0% | 2% | 115 |
| **all** | **critic-off** | **116 → 4 → 4 → 4** | **1%** | **9%** | **293** |
| **all** | **critic-on** | **1 → 0 → 0 → 0** | **0%** | **5%** | **290** |

## Runs: context compression and cost

| Fixture | Sources | Findings | Raw → clean → distilled → to Writer (tokens) | Compression | Cost | Time |
|---|---|---|---|---|---|---|
| eu-ai-act | 35 | 237 | 647,894 → 566,826 → 17,113 → 16,367 | 37.9x | $0.28 | 248s |
| stripe-billing | 35 | 214 | 234,302 → 134,544 → 10,961 → 10,056 | 21.4x | $0.25 | 206s |
| vector-dbs | 33 | 289 | 270,104 → 185,231 → 19,188 → 18,111 | 14.1x | $0.36 | 364s |

## How to read these numbers

- **Plants are synthetic.** Two kinds are string edits (a changed number or date, a swapped
  company name) and two are written by the strong model. Swapping company names works poorly on
  regulatory text, where there are no rival companies: two of the misses are "GPAI" → "EU"
  swaps that are arguably still true.
- **Reference labels are model labels, not human ones.** The strong model at high reasoning
  judged each item against the source; its rationales are in `evals/fixtures/*/labels.json`
  for review. Plants it did not confirm as false are excluded (4 of 120).
- **The ablation judge is the strong model too.** It reads the source text around each cited
  quote, not the findings, so a fabricated finding cannot vouch for itself.
- **Samples are small:** 116 plants, 120 real findings and about 290 statements per condition.
  Read single-digit differences as directional.
- **Where plants are stopped matters.** With the Critic off, the outline happened to pick only
  4 of 116 plants, and every one it picked reached the final report: the sentence auditor
  checks statements against their findings, so it cannot catch a fabricated finding. The Critic
  is the layer that stops them (1 of 116 reached the Writer, 0 were cited).
