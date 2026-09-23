"""Render one dashboard frame from a recorded run to SVG (README screenshots).

    uv run python scripts/render_frame.py <run_id> --after critic.contradict

The frame is taken a few events after the last event of kind `--after`, so it shows real activity
from that run rather than a mock-up.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rich.console import Console

from deep_research.config import PRESETS, get_settings
from deep_research.events import EventLog
from deep_research.runner import RunInfo
from deep_research.ui.dashboard import Dashboard, DashboardState


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("--after", default="critic.contradict", help="event kind to anchor on")
    parser.add_argument("--extra", type=int, default=3, help="events to include after the anchor")
    parser.add_argument("--out", type=Path, default=Path("docs/dashboard.svg"))
    parser.add_argument("--width", type=int, default=140)
    parser.add_argument("--height", type=int, default=36)
    args = parser.parse_args()

    run_dir = get_settings().runs_dir / args.run_id
    info = RunInfo.load(run_dir)
    events = EventLog.read(run_dir / "events.jsonl")
    anchors = [i for i, e in enumerate(events) if e.kind == args.after]
    upto = (anchors[-1] + 1 + args.extra) if anchors else len(events)

    state = DashboardState(
        prompt=info.prompt,
        run_id=info.run_id,
        depth=info.depth.value,
        deadline_s=PRESETS[info.depth].deadline_s,
        max_cost_usd=PRESETS[info.depth].max_cost_usd,
    )
    for event in events[:upto]:
        state.clock = event.ts
        state.apply(event)

    console = Console(
        record=True,
        width=args.width,
        height=args.height,
        force_terminal=True,
        color_system="truecolor",
        file=open("/dev/null", "w"),  # noqa: SIM115 - recording only
    )
    console.print(Dashboard(state))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(args.out), title="research · live dashboard")
    print(f"wrote {args.out} ({upto}/{len(events)} events)")


if __name__ == "__main__":
    main()
