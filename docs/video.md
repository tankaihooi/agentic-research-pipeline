# Demo video: how it was recorded

The video at the top of the README is a single terminal recording. The dashboard replays the
Stripe run's recorded `examples/stripe-billing/events.jsonl` at 4×, with waits over 3 s
trimmed. The same events drove the dashboard during the live run, so nothing is staged or
re-run. The header shows a `REPLAY 4×` badge throughout.

## Recording it again

Run the script in Terminal.app or iTerm2. An editor's terminal panel can't be resized to the
140×36 the dashboard is designed for. Use a dark theme.

```bash
scripts/record_demo.sh              # or: scripts/record_demo.sh examples/vector-databases
```

The script sizes the window, then waits for Enter at three points:

1. **Before typing.** Set the font with ⌘+ / ⌘− (15 pt fits a 1440-point-wide screen). Start a
   screen recording with ⌘⇧5 → Record Selected Portion, then press Enter. The script types the
   prompt and the replay runs by itself, taking about 55 seconds.
2. **On the run summary** (per-agent tokens and cost). Press Enter to move on.
3. **In the report pager.** Hold ↓ to scroll. Type `/Methodology` and press Enter to jump to
   that section, and press `q` to finish.

To add a recording to the README, drag the MP4 into the README editor on github.com. GitHub
uploads it and inserts a `github.com/user-attachments/...` link, which plays inline. The upload
limit for videos on a free account is 10 MB.

## What happens when

Times from the start of the replay, for the Stripe run:

| Replay time | On screen |
|---|---|
| 0:00-0:03 | Planner: the prompt becomes 5 research questions, one per company |
| 0:03-0:11 | Scrapers in parallel: `navigating …`, then pages read, cleaned and distilled into quote-backed findings. The token funnel fills. |
| 0:11-0:17 | Critic: every quote checked against its page, every claim against its quote. The first red `✗ rejected … (entailment)` lines appear. |
| 0:17-0:26 | `↻ requesting more evidence` ×4: the evidence is one-sided, so the scrapers go back for independent sources |
| 0:26-0:32 | Critic, second pass: more rejections, and orange `⚠ contradicted` lines where sources disagree |
| 0:32-0:41 | Writer: outline, then 7 sections drafted in parallel, each from its own verified findings |
| 0:41-0:51 | Auditor: `⚑` flags statements that go beyond what they cite, 4 sections are revised, and a second audit round runs. The report is assembled. |
| after | Run summary (tokens and cost per agent), then the report with its `[n]` citations and generated Methodology & limitations section |
