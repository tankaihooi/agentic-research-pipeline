# Stripe Pricing, Decoded: The 4–7% Reality Behind the 2.9% Headline

Stripe's advertised 2.9% + $0.30 rate applies to US domestic card transactions with no add-ons. For global SaaS, effective rates run 4–7%. Here's the complete f

Updated 16 min read

Stripe is the right payment processor for most SaaS founders, and the one most founders are overpaying on. The advertised 2.9% + $0.30 rate applies

[…]

# Stripe Pricing, Decoded: The 4–7% Reality Behind the 2.9% Headline
## Core Pricing: What You Actually Pay
s ($0.02–$0.07 per screened transaction), or Instant Payouts (1.5%).

The international surcharge applies based on the card-issuing country, not the customer's billing address. A UK customer using a UK-issued card and paying in USD triggers the +1.5% surcharge. A UK customer switching to SEPA does not.

**The flat per-transaction fee hits micro-transactions hardest.** A $10 transaction carries a 5.9% effective rate after the $0.30 charge. A $500 transaction drops to 2.96%. If your product has any entry-level pricing tier in the $5–$15 range, the transaction fee is eating a disproportionate share of that revenue.

**The MRR reality check.** At $10,000 MRR with a typical global SaaS customer mix, Freemius calculates effective Stripe rates of 7.79–12.27%, nearly three times the advertised 2.9%. At $50,000 MRR, a 506-upvote thread in r/SaaS from March 2026 crystallized what many founders calculate for the first time in a dashboard: approximately $17,400 per year in Stripe fees.

One cost that's easy to miss: Stripe has not reversed the processing fee on refunded transactions since April 2020. When you issue a refund, the original 2.9% + $0.30 does not come back. For products with any non-trivial refund rate, this is a real line item.

## Stripe Billing: The 0.7% Most Founders Forget

Stripe Billing is the subscription and invoice management layer. For SaaS founders running recurring billing, it's the second-most relevant part of the pricing picture after base transaction costs.

The standard rate is **0.7% of total billing volume** on a pay-as-you-go basis. This consolidated from a two-tier structure (Starter at 0.5%, Scale at 0.8%) in July 2024. The 0.7% applies to subscription revenue processed both on and off Stripe, a cut stacked on top of the per-transaction processing fee.

For 0.7%, you get Smart Retries (ML-optimized failed payment recovery), automated dunning sequences, a customer portal, revenue recognition, credit grants for promotional and prepaid balances, and Stripe's Meters API for usage-based billing. For most subscription businesses under $100K MRR, the 0.7% is the most straightforward path to proven retry logic and subscription management without building in-house.

Monthly subscription plans are available as volume-tiered annual contracts; see stripe.com/billing/pricing for current rates, since Stripe updated this area in 2026. A custom domain for your billing portal is available at an additional $10/month.

**The gateway-only trade-off.** On r/SaaS, a recurring architectural recommendation involves using Stripe purely as a payment rail, building billing and subscription logic in-house, and avoiding the 0.7% Billing fee entirely. The appeal is real: at $500K ARR, 0.7% is $3,500/year saved.

Multiple engineers push back. Subscription logic accumulates hidden complexity: 3DS compliance, webhook reliability, payment method update flows, double-billing edge cases. One commenter documented five years of full-time engineering work still yielding ongoing maintenance anxiety.

At most SaaS scales, 0.7% is cheaper than the engineering cost.

## Custom Pricing and Negotiation: Earlier Than You Think

Stripe publishes one rate: 2.9% + $0.30. Volume discounts exist. Stripe does not make this obvious.

The commonly cited threshold for enterprise and IC+ (interchange-plus) pricing is $5M+ per year in processing volume. This comes from third-party analysis and community reporting; Stripe does not publish an official threshold. The community experience tells a different story: the practical starting point for a volume discount conversation is approximately $10,000–$20,000 MRR, not $100,000 per month.

On r/SaaS, practitioners document specific outcomes. One contributor reported a 30-basis-point rate reduction after $8 million in cumulative processing over five years, triggered at the $100,000/month MRR checkpoint.

[…]

# Stripe Pricing, Decoded: The 4–7% Reality Behind the 2.9% Headline
## International Payments and Regional Rate Asymmetry
|
| --- | --- |
| US business, US domestic card online | 2.9% + $0.30 |
| EU business, EEA card | 1.5% + €0.25 |
| UK business, EEA card | 1.5% + £0.20 |
| EU business, SEPA Direct Debit | 0.8%, capped at €5.00 |
| US business, international card | 4.4% + $0.30 |

An EU-incorporated SaaS with predominantly European customers processes those transactions at roughly half the US standard rate. Stripe does not prominently advertise this asymmetry in its standard pricing documentation.

For US-incorporated businesses processing internationally, both surcharges stack independently. A UK customer paying in USD triggers the +1.5% international card surcharge and the +1.0% currency conversion fee: +2.5% on top of the base 2.9%. The currency conversion fee applies when settling in a currency different from the customer's card currency; these are two separate charges that combine.

Stripe's Adaptive Pricing Engine (May 2026) automates local currency presentation, exchange rate disclosure, and payment method localization at checkout. It charges the customer a disclosed 4% conversion fee and settles the merchant in base currency. For large product catalogs where managing per-currency SKUs was previously impractical, this solves a real operational problem: the 4% customer-facing charge is transparent but real.

## 2026 Upgrades: AI Billing, Token Pricing, and What Changed

The part of Stripe's pricing picture that most existing reviews miss entirely is what changed in the last 12 months.

**Token billing for AI products (March 2026).** Stripe now lets AI developers meter, bill, and mark up LLM inference costs with two lines of code. Jeff Weinstein, Stripe's head of product, described the mechanic:

> .@stripe is building a way for developers to completely automate billing for tokens: 1/ pick model (e.g. openai o3, claude sonnet 4, gemini 1.5 flash, etc) 2/ set margin (e.g. charge +10% over inference) 3/ add two lines of code to your app want to try it? jweinstein@stripe.com

Jeff Weinstein · @jeff\_weinstein··View on X

This removes a custom engineering problem that every AI founder was previously solving independently. A company charging customers for Claude Sonnet usage had to build metering, billing, and markup logic separately. Stripe now handles all three; ElevenLabs expanded its billing to token-based pay-as-you-go as an early production showcase.

**Metronome acquisition (December 2025, approximately $1 billion).** Stripe's native Billing cannot handle AI-scale usage pricing: ramped contracts, pooled credit balances, parent-child account hierarchies, and metering above 1,000 events per second. Metronome (which powers billing for OpenAI, Anthropic, NVIDIA, and Databricks) was acquired to close this gap. Metronome integration pricing is contact-sales; the capability now sits inside Stripe's platform.

**Dispute fee restructure (June 2025).** The change received limited coverage but it is material. The new structure: $15 per dispute received (non-refundable), +$15 to submit evidence (refunded if you win), and 30% of recovered funds if you use Stripe's Smart Disputes AI tool.

The previous structure was simpler and lower. For any business with non-trivial chargeback exposure, this restructure has real cost implications that compound at scale.

**Agentic Commerce Protocol (September 2025, co-developed with OpenAI).** Stripe is the first payments platform embedded in ChatGPT's Instant Checkout. Machine-to-machine transactions (AI agents purchasing on behalf of users) will route through Stripe infrastructure. This positions Stripe as the payment layer for the next generation of software interactions, not just human checkout flows.

## Developer Experience and Reliability

Stripe's primary competitive advantage is its product quality. The pricing is competitive but not exceptional; the developer experience is the reason founders stay long after the fee calculations make them curious about alternatives.

The r/SaaS consensus on reliability: "Stripe just works. Every single time." Failed payment migrations are consistently framed as more expensive than years of processing fees. The community also documents what direct processor integration looks like in comparison: 10–20% rolling reserves, complex compliance requirements, brittle integration patterns.

The public review picture

[…]

# Stripe Pricing, Decoded: The 4–7% Reality Behind the 2.9% Headline
## Stripe Pricing
0.5%) totals 4.1% before international fees. That's roughly comparable to Paddle's all-in Merchant of Record rate of 4–5%, without Paddle's full tax compliance included.

## Who Should Use Stripe?

**Stripe is ideal for:**

* SaaS founders building developer-led products who want API-first payment infrastructure without negotiating setup contracts or onboarding calls
* Early-stage companies (pre-$10K MRR) where the pay-as-you-go model, zero minimums, and immediate activation outweigh the value of fee optimization
* AI founders building token-based or usage-metered billing who need Stripe's 2026 LLM billing primitives and Metronome integration
* Businesses with complex global payment method requirements: local wallets, SEPA, bank transfers, and 100+ payment methods across many countries

**Stripe is NOT ideal for:**

* Founders who need complete tax compliance from the first EU sale: Stripe Tax collects but does not remit; Paddle or Lemon Squeezy are better fits if EU VAT obligations arrive with your first customer
* High-risk product categories where Stripe's automated risk engine creates account stability exposure with limited escalation options
* Enterprise businesses above $5M+/year in processing that haven't negotiated IC+ pricing; at that volume, Adyen's interchange-plus economics likely outperform Stripe standard, and the conversation is overdue

## Stripe Alternatives Worth Considering

If Stripe isn't the right fit, these three cover the most common decision points:

* **Paddle**: Best for founders who want complete tax compliance from day one. All-in Merchant of Record pricing at approximately 4–5%, covering tax calculation, collection, filing, and remittance globally. The 1.1% premium over Stripe's base rate buys you the entire compliance stack.
* **Adyen**: Best for high-volume enterprises ($5M+/year) seeking interchange-plus economics. More complex onboarding; IC+ savings at enterprise scale justify the setup cost.
* **Lemon Squeezy**: Best for indie developers and digital product sellers who want a straightforward MoR setup. Simpler UX than Paddle for solo operators; similar all-in pricing model.

## Final Verdict: Right Default, Wrong Assumption on the Rate

Stripe is the right payment processor for most SaaS founders. Its API is the category standard; no self-serve competitor matches its global payment method coverage.

The pay-as-you-go model removes the barrier to starting. For AI product billing, Stripe's 2026 token billing and Metronome integration are the only self-serve options that handle LLM inference billing and enterprise usage-metering in the same platform.

The assumption that costs you money is the one most founders carry too long: that 2.9% + $0.30 is what you pay. For a SaaS with global customers, the real number runs 4–7% depending on your customer mix. At $50K MRR, that gap is approximately $17,400 per year.

The fee is predictable. Whether you're paying the right fee depends on whether you've asked.

At $10,000 MRR, call Stripe. Request a rate review. Enable ACH for US B2B customers.

If you have meaningful European revenue, evaluate a UK or EU entity for those transactions. None of this requires switching processor