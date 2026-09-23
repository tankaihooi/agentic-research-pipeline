from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from rich.console import Console

from deep_research.models import Agent, AgentEvent, AgentUsage, Stage, Usage
from deep_research.runner import UpdateTracker
from deep_research.ui.dashboard import Dashboard, DashboardState, _split_width
from deep_research.ui.terminal import replay, replay_delays

T0 = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _event(seconds: float, agent: Agent, kind: str, message: str = "", **data: Any) -> AgentEvent:
    return AgentEvent(
        ts=T0 + timedelta(seconds=seconds),
        agent=agent,
        kind=kind,
        message=message or kind,
        data=data,
    )


RUN = [
    _event(
        0,
        Agent.ORCHESTRATOR,
        "run.start",
        "Starting run",
        prompt="Stripe billing competitive analysis",
        run_id="r1",
        depth="standard",
        deadline_s=600,
        max_cost_usd=1.5,
    ),
    _event(1, Agent.PLANNER, "plan.query", "Q1: What shipped?"),
    _event(1, Agent.PLANNER, "plan.query", "Q2: What does it cost?"),
    _event(2, Agent.ORCHESTRATOR, "stage", "stage → researching", stage="researching"),
    _event(3, Agent.SCRAPER, "scrape.read", "[Q1] read stripe.com", tokens=800, raw_tokens=2000),
    _event(
        3, Agent.SCRAPER, "scrape.read", "[Q2] read docs.stripe.com", tokens=400, raw_tokens=600
    ),
    _event(4, Agent.SCRAPER, "scrape.extract", "[Q1] extracted 6", findings=6),
    _event(5, Agent.ORCHESTRATOR, "usage", cost_usd=0.012, llm_calls=4, input_tokens=9000),
    _event(6, Agent.ORCHESTRATOR, "research.done", "Research complete", distilled_tokens=300),
    _event(6, Agent.ORCHESTRATOR, "stage", "stage → verifying", stage="verifying"),
    _event(7, Agent.CRITIC, "critic.reject", "✗ rejected F-1 (grounding): quote not found"),
    _event(
        8,
        Agent.CRITIC,
        "critic.summary",
        "Cross-reference done",
        check="cross_reference",
        verified=3,
        first_party=2,
        single_source=1,
        contradicted=1,
    ),
    _event(9, Agent.CRITIC, "critic.gap", "↻ requesting more evidence · Q2.g1"),
    _event(20, Agent.ORCHESTRATOR, "stage", "stage → writing", stage="writing"),
    _event(21, Agent.WRITER, "writer.outline", "Planning the report"),
    _event(21, Agent.WRITER, "writer.section_plan", "§1 Capabilities"),
    _event(21, Agent.WRITER, "writer.section_plan", "§2 Pricing"),
    _event(25, Agent.WRITER, "writer.drafted", "§1 drafted"),
    _event(26, Agent.AUDITOR, "audit.summary", "Audit round 1", checked=20, flagged=2),
    _event(27, Agent.WRITER, "writer.revise", "Revising §1"),
    _event(28, Agent.AUDITOR, "audit.summary", "Audit round 2", checked=8, flagged=0),
    _event(30, Agent.WRITER, "writer.done", "Report assembled", words=3100, references=24),
    _event(30, Agent.ORCHESTRATOR, "stage", "stage → done", stage="done"),
]


def _state(events: list[AgentEvent]) -> DashboardState:
    state = DashboardState()
    for e in events:
        state.clock = e.ts
        state.apply(e)
    return state


def test_state_folds_events_into_counters() -> None:
    s = _state(RUN)
    assert (s.prompt, s.depth, s.deadline_s) == (
        "Stripe billing competitive analysis",
        "standard",
        600,
    )
    assert s.stage is Stage.DONE and s.finished
    assert (s.questions, s.gap_queries) == (2, 1)
    assert (s.pages_read, s.raw_tokens, s.clean_tokens, s.distilled_tokens) == (2, 2600, 1200, 300)
    assert s.findings == 6
    assert (s.verified, s.single_source, s.contradicted, s.rejected) == (3, 1, 1, 1)
    assert (s.sections_planned, s.sections_drafted, s.revisions) == (2, 1, 1)
    assert s.audit_rounds == [(20, 2), (8, 0)]
    assert (s.words, s.references, s.cost_usd, s.llm_calls) == (3100, 24, 0.012, 4)
    assert s.elapsed_s == 30
    assert all(e.kind != "usage" for e in s.log)  # meters only, not log lines


def test_agent_states_follow_the_stage() -> None:
    s = _state(RUN[:8])  # mid-research
    assert s.agent_state(Agent.SCRAPER) == "active"
    assert s.agent_state(Agent.PLANNER) == "done"
    assert s.agent_state(Agent.WRITER) == "idle"
    finished = _state(RUN)
    assert {finished.agent_state(a) for a in (Agent.PLANNER, Agent.WRITER)} == {"done"}


def test_rewrite_resets_writing_counters() -> None:
    s = _state([*RUN, _event(40, Agent.WRITER, "writer.outline", "Planning again")])
    assert (s.sections_planned, s.sections_drafted, s.audit_rounds) == (0, 0, [])


def test_logs_without_stage_events_still_advance_the_pipeline() -> None:
    legacy = [e for e in RUN if e.kind != "stage"]
    assert _state(legacy[:5]).stage is Stage.RESEARCHING
    assert _state(legacy[:10]).stage is Stage.VERIFYING
    assert _state(legacy).stage is Stage.DONE


def test_dashboard_renders_every_region() -> None:
    console = Console(record=True, width=150, height=40, force_terminal=True, color_system=None)
    console.print(Dashboard(_state(RUN[:13])))
    text = console.export_text()
    for expected in (
        "DEEP RESEARCH",
        "Stripe billing competitive analysis",
        "Verifying",
        "Planner",
        "Auditor",
        "2 questions +1 follow-up",
        "2 pages · 6 findings",
        "3✓ 1◐ 1⚠ 1✗",
        "requesting more evidence",
        "2,600 tok",
        "$ 0.012 / 1.50",
    ):
        assert expected in text, expected
    assert "REPLAY" not in text


def test_replay_is_labelled_in_the_header() -> None:
    state = _state(RUN[:5])
    state.replay_speed = 4
    console = Console(record=True, width=150, height=40, force_terminal=True, color_system=None)
    console.print(Dashboard(state))
    assert "REPLAY 4\u00d7" in console.export_text()


def test_replay_delays_scale_and_cap_pauses() -> None:
    events = [RUN[0], RUN[1], RUN[13]]  # gaps of 1s and 19s
    assert replay_delays(events, speed=2, max_gap_s=5) == [0.0, 0.5, 5.0]


async def test_replay_feeds_every_event_in_order() -> None:
    seen: list[AgentEvent] = []
    await replay(RUN, seen.append, speed=1e6, max_gap_s=0)
    assert seen == RUN


def test_update_tracker_emits_stage_changes_and_cumulative_cost() -> None:
    tracker = UpdateTracker()
    spend = Usage.single(Agent.SCRAPER, AgentUsage(calls=2, cost_usd=0.01))
    first = tracker.events((), {"planner": {"stage": "researching", "usage": spend}})
    assert [e.kind for e in first] == ["stage", "usage"]
    # updates from inside a subgraph are ignored: the parent node's update carries its totals
    assert tracker.events(("research:abc",), {"extract": {"usage": spend}}) == []
    second = tracker.events(
        (), {"research": {"usage": spend}, "join_research": {"stage": "researching"}}
    )
    assert [e.kind for e in second] == ["usage"]  # stage unchanged, so no new stage event
    assert second[0].data["cost_usd"] == 0.02
    assert second[0].data["llm_calls"] == 4


def test_verdict_bar_always_fills_exactly() -> None:
    assert sum(_split_width([23, 19, 5, 5], 18)) == 18
    assert _split_width([1, 0, 0, 0], 18) == [18, 0, 0, 0]
    assert _split_width([0, 0, 0, 0], 18) == [0, 0, 0, 0]


def test_only_the_agent_that_spoke_last_is_active() -> None:
    s = _state(RUN[:21])  # auditor round 2 was the last word
    active = [
        a
        for a in (Agent.PLANNER, Agent.SCRAPER, Agent.CRITIC, Agent.WRITER, Agent.AUDITOR)
        if s.agent_state(a) == "active"
    ]
    assert active == [Agent.AUDITOR]
    assert s.counters(Agent.AUDITOR) == "flagged 2 → 0 of 20"


def test_stage_follows_agent_events_before_the_node_update_lands() -> None:
    audit_started = [*RUN[:18], _event(25.5, Agent.AUDITOR, "audit.start", "Audit round 1…")]
    assert _state(audit_started).stage is Stage.AUDITING  # no stage event yet
    revising = [*RUN[:20]]  # writer.revise after audit round 1
    assert _state(revising).stage is Stage.WRITING
