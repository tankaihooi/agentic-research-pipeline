# Demo video: storyboard and recording guide

A 75-90 second time-lapse for the top of the README and LinkedIn. Every frame comes from a real
run: the dashboard replays the run's recorded `events.jsonl` at 8×, so nothing is staged or
re-run.

## Setup

- Terminal at **140×36** (the dashboard's design size), dark theme, 15-16 pt monospace font.
- Screen recorder: QuickTime (File → New Screen Recording, select the terminal window) or Loom.
- Rehearse once with `--speed 8 --hold 4`, then record.

```bash
uv run research replay examples/stripe-billing --speed 8 --hold 5
uv run research show examples/stripe-billing
```

## Shots

| Time | On screen | Voice-over / caption |
|---|---|---|
| 0:00-0:06 | Type `research run "Give me a competitive analysis of Stripe's new billing features"` (hit enter, cut) | "One prompt. Five agents. About four minutes of research, sped up 8×." |
| 0:06-0:12 | Replay starts: Planner row active, 5 research questions appear in the log | "The Planner splits the request into questions, one per company, aimed at official sources." |
| 0:12-0:28 | Scraper: parallel `navigating …` lines; token funnel bars fill (raw → cleaned → distilled) | "Scrapers run in parallel. Hundreds of thousands of tokens of web pages are distilled into short, quote-backed findings, so no prompt ever holds the raw web." |
| 0:28-0:46 | Critic: red `✗ rejected … (entailment): overstates its quote` lines, orange contradictions, verdict bar fills | "The Critic checks every quote against its source and every claim against its quote, and cross-references other sources. Anything unsupported is dropped with a reason." |
| 0:46-0:52 | `↻ requesting more evidence` (gap loop), scrapers restart | "Where the evidence is one-sided, it sends the scrapers back for independent sources." |
| 0:52-1:02 | Writer drafts sections in parallel; Auditor `⚑` flags, `Revising §n` | "The Writer drafts every section in parallel from its own findings only. An Auditor checks every sentence against what it cites." |
| 1:02-1:14 | `research show`: scroll the executive summary, one section with `[n]` citations, Methodology & limitations, References | "The result: a multi-page, cited briefing whose methodology section is computed from the run, not written by the model." |
| 1:14-1:24 | LangSmith trace tree (public link), then `evals/results/RESULTS.md` table | "Every agent step is traced. Against planted fabrications, the Critic catches 97%." |
| 1:24-1:28 | End card: repo URL | |

## Honesty notes for the caption

- Say "8× replay of a real run". The replay is exact, only faster.
- Quote headline numbers from `evals/results/RESULTS.md` with their caveats (synthetic plants,
  model-made reference labels).
