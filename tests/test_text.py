from __future__ import annotations

from itertools import pairwise

import pytest

from deep_research.tools.text import (
    audit_units,
    chunk_text,
    cited_finding_ids,
    clean_page_markdown,
    count_tokens,
    heading_trail,
    is_uncited_figure,
    lint_citations,
    mark_unit,
    quote_grounding_score,
    renumber_citations,
)

PAGE = """# Stripe Billing

Stripe Billing supports **usage-based pricing** with meters. Usage is aggregated per billing period.

Pricing for Billing starts at 0.7% of billing volume. Enterprise plans are available on request.

Smart Retries use machine learning to pick the best time to retry a failed payment.
"""


# ------------------------------------------------------------------ chunking


def test_chunks_respect_token_limit_and_cover_text() -> None:
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 80 for i in range(20))
    chunks = chunk_text(text, max_tokens=200, overlap_tokens=30)
    assert len(chunks) > 5
    assert all(c.token_count <= 200 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    for i in range(20):
        assert any(f"Paragraph {i}." in c.text for c in chunks)


def test_chunks_carry_overlap_forward() -> None:
    text = "\n\n".join(f"Para {i} " + "alpha " * 60 for i in range(6))
    chunks = chunk_text(text, max_tokens=150, overlap_tokens=20)
    # the start of each later chunk repeats the tail of the previous one
    for prev, cur in pairwise(chunks):
        assert cur.text.split()[0] in prev.text


def test_oversize_single_sentence_is_hard_split() -> None:
    blob = "x" * 20_000
    chunks = chunk_text(blob, max_tokens=300, overlap_tokens=0)
    assert all(c.token_count <= 300 for c in chunks)


def test_overlap_must_be_smaller_than_chunk() -> None:
    with pytest.raises(ValueError):
        chunk_text("hi", max_tokens=10, overlap_tokens=10)


def test_count_tokens_nonzero() -> None:
    assert count_tokens("Stripe Billing") > 0


# ------------------------------------------------------------------ grounding


def test_exact_quote_scores_100_despite_markdown_and_case() -> None:
    quote = "Stripe Billing supports usage-based pricing with meters."
    assert quote_grounding_score(quote, PAGE) == 100.0


def test_curly_quotes_and_whitespace_are_normalised() -> None:
    source = "It\u2019s   priced at \u201c0.7%\u201d of volume \u2014 per month."
    assert quote_grounding_score('It\'s priced at "0.7%" of volume - per month.', source) == 100


def test_fabricated_quote_scores_low() -> None:
    fake = "Stripe Billing includes a built-in CPQ module with AI-generated quotes."
    assert quote_grounding_score(fake, PAGE) < 70


def test_distorted_number_in_short_quote_fails_exact_match() -> None:
    assert quote_grounding_score("starts at 0.7%", PAGE) == 100.0
    assert quote_grounding_score("starts at 0.5%", PAGE) == 0.0


def test_small_extraction_drift_still_grounds() -> None:
    drifted = "Smart Retries use machine learning to pick the best time to retry failed payments"
    assert quote_grounding_score(drifted, PAGE) >= 90


def test_truncated_link_does_not_swallow_following_text() -> None:
    source = (
        "See [our newsletter](https://www.linkedin.com/newsletters/the-monetization-\n\n"
        "Chargebee Billing supports hybrid pricing models without code changes (really)."
    )
    quote = "Chargebee Billing supports hybrid pricing models without code changes"
    assert quote_grounding_score(quote, source) == 100.0


def test_empty_quote_is_ungrounded() -> None:
    assert quote_grounding_score("   ", PAGE) == 0.0


# ------------------------------------------------------------------ citations

F1, F2, F3 = "F-aaaaaaaa", "F-bbbbbbbb", "F-cccccccc"


def test_renumber_orders_by_first_citation_and_merges_same_source() -> None:
    md = f"Meters exist [{F2}]. Pricing is 0.7% [{F1}, {F3}]. Retries use ML [{F2}]."
    result = renumber_citations(md, {F1: "S-1", F2: "S-2", F3: "S-1"})
    assert result.markdown == "Meters exist [1]. Pricing is 0.7% [2]. Retries use ML [1]."
    assert result.references == ["S-2", "S-1"]
    assert result.unknown_ids == []


def test_renumber_drops_unknown_and_malformed_ids() -> None:
    md = f"Claim one [{F1}]. Claim two [F-deadbeef]. Claim three [F-nothex!]."
    result = renumber_citations(md, {F1: "S-1"})
    assert result.markdown == "Claim one [1]. Claim two. Claim three."
    assert result.unknown_ids == ["F-deadbeef"]


def test_cited_finding_ids_in_order() -> None:
    assert cited_finding_ids(f"a [{F1}] b [{F2}; {F3}]") == [F1, F2, F3]


def test_lint_flags_out_of_range_and_orphans() -> None:
    assert lint_citations("A [1]. B [2, 3].", 3) == []
    problems = lint_citations("A [1]. B [4].", 2)
    assert "citation [4] has no matching reference" in problems
    assert "reference [2] is never cited" in problems


# ------------------------------------------------------------------ page cleaning

NAV_PAGE = """# [](https://stripe.com/)

*   Products
*   [Pricing](https://stripe.com/pricing)
*   [Guide me](https://stripe.com/personalize)

[Dashboard](https://dashboard.stripe.com/)[Sign in](https://dashboard.stripe.com/login)

[Skip to content](#main-content)

# Revenue

*   [Billing Recurring revenue](https://stripe.com/billing)
*   [Metronome Usage-based billing](https://stripe.com/billing/usage-based-billing)

![Logo](https://cdn.example.com/logo.png)

# Usage-based pricing 101

Usage-based pricing sets prices based on real consumption of products or services, and in \
January 2025, 85% of SaaS companies had adopted it according to [a survey](https://x.com/s).

| Model | Example |
|---|---|
| Per unit | $0.01 per API call |

*   Short content bullet
*   Another short bullet

Stripe Billing supports meters, tiers and hybrid pricing so businesses can charge for exactly \
what customers use each billing period without custom infrastructure.

# Footer

*   [About](https://stripe.com/about)
*   [Careers](https://stripe.com/jobs)
"""


def test_clean_page_strips_navigation_and_keeps_article() -> None:
    clean = clean_page_markdown(NAV_PAGE)
    assert clean.startswith("# Usage-based pricing 101")
    for noise in ("Sign in", "Guide me", "Recurring revenue", "logo.png", "Careers", "Skip to"):
        assert noise not in clean
    assert "85% of SaaS companies had adopted it according to a survey." in clean
    assert "https://x.com/s" not in clean  # inline links flattened to anchor text
    assert "| Per unit | $0.01 per API call |" in clean
    assert "Short content bullet" in clean  # short plain bullets inside the article survive
    assert clean.rstrip().endswith("without custom infrastructure.")


def test_clean_page_is_idempotent_and_keeps_plain_text() -> None:
    plain = "Just one short line."
    assert clean_page_markdown(plain) == plain
    once = clean_page_markdown(NAV_PAGE)
    assert clean_page_markdown(once) == once


# ------------------------------------------------------------------ heading trail

CHANGELOG = """# Stripe changelog

## 2026-05-27

### Billing

- Adds billing schedules to enable prebilling on subscriptions
- Adds item-level discounts

## 2026-04-22

### Payments

- Adds support for Pix recurring payments
"""


def test_heading_trail_finds_the_date_and_product_above_a_line() -> None:
    trail = heading_trail("Adds billing schedules to enable prebilling on subscriptions", CHANGELOG)
    assert trail == ["Stripe changelog", "2026-05-27", "Billing"]
    # a sibling heading at the same level replaces the previous one
    assert heading_trail("Adds support for Pix recurring payments", CHANGELOG) == [
        "Stripe changelog",
        "2026-04-22",
        "Payments",
    ]


def test_heading_trail_empty_when_quote_absent() -> None:
    assert heading_trail("completely unrelated sentence about llamas", CHANGELOG) == []


# ------------------------------------------------------------------ audit units

SECTION = """## Pricing

Stripe Billing costs 0.7% of billing volume [F-aaaaaaaa]. It offers meters. [F-bbbbbbbb] \
Chargebee is free below $250K [F-cccccccc, F-dddddddd].

- Usage-based pricing with meters [F-bbbbbbbb]
- Launched in 2026

| Vendor | Fee |
|---|---|
| Stripe | 0.7% [F-aaaaaaaa] |
"""


def test_audit_units_split_sentences_items_and_rows() -> None:
    units = audit_units(SECTION)
    assert units == [
        "Stripe Billing costs 0.7% of billing volume [F-aaaaaaaa].",
        "It offers meters. [F-bbbbbbbb]",  # trailing citation reattached to its sentence
        "Chargebee is free below $250K [F-cccccccc, F-dddddddd].",
        "- Usage-based pricing with meters [F-bbbbbbbb]",
        "- Launched in 2026",
        "| Vendor | Fee |",
        "| Stripe | 0.7% [F-aaaaaaaa] |",
    ]


def test_uncited_figures_and_marking() -> None:
    assert is_uncited_figure("- Launched in 2026")
    assert not is_uncited_figure("Costs 0.7% [F-aaaaaaaa].")
    assert not is_uncited_figure("No numbers here.")
    marked = mark_unit(SECTION, "- Launched in 2026")
    assert "- Launched in 2026 †" in marked
