# Stripe Billing in 2025–2026: New Capabilities, Availability, and Competitive Trade-offs

*Research briefing · 23 September 2026 · 29 cited sources · 122 verified findings · depth: standard*

## Executive summary

- Stripe expanded native usage billing with dimensional pricing, hybrid plans, and near-real-time credit drawdown, but billing credits were described as public preview and advanced Metronome capabilities should not be assumed to be native to Billing [1, 2, 3].
- Stripe added subscription and invoicing flexibility, but Scripts remained a preview and Trial Offers require a preview API version, flexible billing mode, and subscriptions created directly through the Subscriptions API rather than Checkout [1, 4, 5].
- Stripe’s multi-processor integration became generally available in October 2025, but that does not establish that third-party-processor dunning left preview; its reported recovery dollars are not a like-for-like effectiveness measure against competitors [1, 6, 7, 8, 9].
- Chargebee offers usage pricing and subscription self-service, with third-party accounts describing detailed metering and prepaid-credit controls; buyers should test event-volume performance and verify plan-specific fees and separately priced products [7, 10, 11].
- Recurly emphasizes retention and subscription operations, including churn-oriented engagement tools, while its suitability for complex metering remains a third-party judgment rather than an established advantage [8, 12, 13, 14].
- Paddle bundles subscription management and global tax compliance as merchant of record at 5% plus $0.50 per checkout transaction, but the depth of its usage metering is unclear [15, 16].
- Compare total operating costs rather than headline rates: Stripe Billing’s reported 0.7% fee excludes payment processing and separately priced Metronome usage, while Paddle’s fee includes merchant-of-record tax responsibilities and published Stripe Billing rates differ [15, 17, 18].

## Stripe’s usage-based billing advances—and where Metronome fits

Stripe’s documented 2025 releases expanded what teams can configure in Billing itself [1]. In January, Stripe added Dashboard CSV uploads for recording customer usage [1]. In September, it launched dimensional pricing, which bills against multiple attributes of usage data from a single meter, and hybrid plans combining license fees, usage-based rate cards, and credit grants [1]. Stripe also launched credits that draw down in near real time that month [1]. More broadly, Stripe says Billing supports usage-based, tiered, and flat-fee-plus-overage pricing [6].

A launch announcement does not establish that every related capability is generally available. According to withorb.com’s 2026 review, Stripe’s documentation labeled billing credits **public preview**, despite the September 2025 announcement of near-real-time credit drawdown [1, 2]. The same review described the Meter Usage Analytics API as **public preview**, offering aggregated customer-level usage data and alerts for threshold-based workflows [2]. It also reported documented lookback workflows, subscription backdating, and credit notes for usage repricing [2].

Metronome is a related but distinct part of the picture. According to withorb.com, Stripe completed its acquisition of Metronome on January 14, 2026, then announced customer-facing integrations at Stripe Sessions on April 29, 2026, covering commits, multidimensional pricing, bespoke contracts, and Metronome management in the Stripe Dashboard [2]. According to stigg.io, Metronome supports enterprise contracts, prepaid commitments, and high-cardinality usage scenarios; ustechautomations.com says existing Billing Meters integrations remain supported while advanced needs involving credits, commitments, or high-volume ingestion are directed toward Metronome [3, 11]. Those third-party descriptions should not be read as proof that each Metronome capability is native to Stripe Billing [3, 11].

Operational boundaries still matter. According to stigg.io, Stripe’s Meters API aggregates events by sum, count, or last value, but does not itself control in-product feature access, enforce real-time product usage limits, or manage a catalog of plans, features, and limits [3]. Stripe itself describes ingesting, deduplicating, and rating millions of events without latency or billing errors as an infrastructure challenge, and says pure usage pricing makes revenue more volatile than fixed recurring subscriptions [6]. Sources also disagree on the product boundary: erpresearch.com calls Stripe Billing’s metered pricing “powered by Metronome,” whereas the other accounts distinguish Billing Meters from Metronome and describe advanced usage needs as a Metronome conversation [3, 11, 17].

## Stripe subscription management: flexibility, previews, and API constraints

Stripe’s May 2025 changelog says Billing can put different subscription frequencies, such as annual and monthly fees, on one invoice [1]. At Sessions 2025, Stripe also said users could set up mixed-interval subscriptions, consolidate subscriptions on an invoice, unallocate payments, and arrange partial payments; those broader workflow statements come from the Sessions announcement [4]. Stripe previewed Scripts for customizing Billing logic and said Workflows could build, test, and execute multistep processes across Stripe products using customer data, Stripe APIs, and conditional logic [4]. Scripts should therefore be treated as a preview, not as a released customization capability [4].

The dated changelog entries identify more specific subscription and invoice changes:

- On March 25, 2026, Stripe added a *retention policy* subscription-cancellation reason, while Invoicing added decimal quantities for invoice items and nested invoice items [19, 20].
- On May 27, 2026, Billing added schedules for prebilling, discount properties and metadata for pending subscription updates, and invoice-item discount-eligibility options on the Subscriptions and Preview Invoice APIs [19, 20].
- On June 24, 2026, subscription-mode Checkout Sessions gained billing-cycle-anchor configuration, and the Subscriptions API gained invoice descriptions, footers, and custom fields [19].
- On July 29, 2026, Stripe added a trial property to subscription-schedule phases and item-level discounts to pending updates; an August 26 entry announced a higher subscription-item limit without stating its new size here [19, 20].

Native and trial workflows need separate availability checks: Stripe’s August 2025 BillingSDK for in-app iOS subscription purchases and management, customer-portal billing details, and entitlement-gated features was explicitly a **preview** [1]. Trial Offers likewise require the `2026-03-25.preview` API version in the request header and flexible billing mode; existing classic-mode subscriptions can be updated to flexible mode [5]. Buyers should test their intended integration path because Trial Offers are supported for subscriptions created directly through the Subscriptions API, not Checkout, where Stripe points to legacy `trial_end` trials instead; Trial Offers also cannot be combined with `trial_end` [5].

Trial Offers apply only to recurring items, so non-recurring items cannot receive paid trials or discounted trial pricing [5]. A metered price can be attached for discounted usage-based trial billing if its `usage_type` is `metered` and an existing meter tracks usage [5]. Stripe says trial length cannot be changed after subscription creation or have extensions or reductions scheduled, while Trial Offers revenue is unavailable in Billing Analytics and paid-trial revenue is treated as regular subscription revenue because paid trials have `active` status [5]. The later addition of a trial property to schedule phases does not, by itself, establish that those Trial Offers restrictions have changed [5, 20]. For lifecycle testing, according to withorb.com, Billing supports sandbox simulations and test clocks covering plan changes, customer balances, invoice items, and renewals [2].

## Revenue recovery and processor flexibility: capabilities versus outcomes

Stripe Billing’s cross-processor support expanded in stages in 2025: failed-payment handling and dunning for integrations with third-party processors entered preview in June, while multi-payment-processor integration became generally available in October [1]. The generally available integration supports tracking refunds and immediate cancellations and includes off-Stripe volume in Revenue Recognition reporting [1]. The October announcement does not, by itself, establish that the third-party-processor dunning capability had left preview [1]. According to erpresearch.com, mixing other payment gateways with Stripe Billing limits some features, so buyers should verify which recovery workflows work with their intended processor mix [17]. †

For failed payments, erpresearch.com describes Stripe Billing’s Smart Retries as using machine-learning-driven retry timing [17]. Stackscalehq.com also lists automated retry schedules and webhook-based recovery workflows for Stripe Billing [12]. Stripe says its recovery tools helped users recover more than $6.5 billion in 2024 and more than US$8.2 billion in 2025; withorb.com separately reports Stripe’s $8.2 billion figure for 2025 [2, 6, 21]. Stripe attributes its figures to recovery tools, while withorb.com attributes its 2025 figure to Billing; none is a recovery rate or establishes that Smart Retries, dunning, or cross-processor support individually produced a particular outcome [1, 2, 6, 17, 21].

Competitors document different recovery controls and customer touchpoints:

- Chargebee says it offers more than 23 recovery tactics, including card updates and intelligent retry logic, alongside targeted collection workflows based on customer value, history, and payment patterns [7]. It says automated actions can range from reminders to personalized payment plans [7].
- Recurly says its Retention agent guides teams through dunning configuration, account updater setup, and churn-reduction prompts [8]. Recurly also describes card updates within a Recurly Engage prompt after a failed payment, but labels that feature *coming soon*, rather than available [8].
- As of January 9, 2025, Paddle Billing automatically retried failed payments on automatically collected subscriptions for all platform users, including those without Paddle Retain enabled [9]. Paddle added automated abandoned-checkout recovery emails with optional discounts as of May 2, 2025, and says sellers can enable recovery emails in Checkout Settings at no cost [9, 22].

The practical comparison is therefore between documented retry, collection, and checkout workflows—not between demonstrated recovery rates: Stripe’s reported dollars do not provide a like-for-like effectiveness measure against Chargebee, Recurly, or Paddle [6, 7, 8, 9].

## Chargebee: usage depth, self-service, and a different fee structure

Chargebee presents a documented alternative for teams that want usage pricing alongside subscription administration. Chargebee says its platform supports tiered, volume, stairstep, usage-based, flat-fee, and custom pricing models [7]. It also says customers can self-serve upgrades, modifications, and other subscription-management tasks [7]. A comparison by stackscalehq.com says Chargebee offers lifecycle-management tools directly in its interface, whereas Stripe Billing often relies on API-based configuration for similar workflows; that comparison is one publisher’s assessment, not a demonstrated implementation rule [12].

The more detailed usage-metering picture comes largely from third-party descriptions. According to stigg.io, Chargebee accepts raw or pre-aggregated events through S3, data warehouses, flat files, or a direct API, with near-real-time aggregation, event-level failure tracking, and idempotency checks [10]. Stigg.io also describes configurable prepaid credit packs, rollover and expiration, metering against balances, burn-rate alerts, and automatic overage billing [10]. Those descriptions provide concrete capabilities to test in a pilot, rather than proof that a particular event workload will perform as required [10]. Stigg.io specifically advises usage-only businesses to confirm that Chargebee’s metering engine handles their event volume, noting that its usage capabilities were built on a subscription-first platform [10]. Churntools.com calls Chargebee’s native metering and bill calculation stronger than Stripe Billing’s for complex usage models, but that relative-strength claim comes from a single comparison [23].

Pricing descriptions need equally careful scoping. Stigg.io lists Chargebee Flow as starting at 0.80% of monthly billing value, with no platform fee and 100 million usage events per month [10]. Ustechautomations.com reports access to more than 40 payment gateways and cautions that CPQ and revenue-recognition products sit on separate plans, so the 0.80% rate is not the price of the full revenue stack [11]. Chargebee itself says its plans include a base fee and an overage when revenue exceeds a specified limit; that general description should not be treated as a substitute for checking the terms of a particular plan [10, 24].

Other published figures describe different tiers: getlago.com lists Starter as free until $250,000 in cumulative billing, then 0.75% of billing volume; coldiq.com lists the same cumulative threshold and puts Performance at $599 per month, plus a 0.75% overage above a $100,000 monthly billing cap [14, 25]. A buyer should therefore validate the current tier, included event volume, overage basis, and separately priced products against its expected mix of subscriptions and usage before comparing headline rates [10, 11, 14, 24, 25].

## Recurly: retention-oriented subscription operations

According to StackscaleHQ’s comparison, Recurly supports many of the same billing structures as its peers but typically emphasizes recurring billing stability and retention tools rather than extensive API-based customization [12]. That comparison also characterizes Recurly as focused on retention optimization, payment recovery, and workflows around customer lifecycle events [12]. PeerSpot describes Recurly as supporting flexible pricing models and using dunning to manage failed payments [26]. These are third-party characterizations, not evidence of a measured retention advantage over Stripe [12].

Recurly’s Spring 2026 release highlights describe a broader engagement layer [8]. Recurly says updated propensity modeling uses behavioral and engagement data to identify subscribers likely to churn and automatically create at-risk audiences; it also says dynamic paywalls can respond to article views, scroll depth, and repeat visits [8]. Recurly says its Shopify subscription bundles let shoppers customize selections at checkout and change them before renewal [8]. The release announcement describes these capabilities, but does not by itself establish their availability to every Recurly customer [8].

For day-to-day subscription operations, StackscaleHQ says Recurly supports upgrades, billing-interval changes, and reactivations, while its cancellation workflows may collect feedback, offer discounts, or allow pauses [12]. The same site describes failed-payment workflows that retry charges, notify customers, request updated billing information, and retry after an update [12]. Recurly separately says its Justt.ai integration automates chargeback dispute handling and syncs outcomes with invoices, credits, and subscription records in real time; that is a dispute-management claim, not a demonstrated improvement in failed-payment recovery [8].

Recurly is not described as subscription-only: StackscaleHQ says it supports usage-based pricing and quantity-based billing [12]. The limits of that capability are characterized by other third parties rather than established here: Usagebox calls its usage add-on suitable for light metering and describes Recurly as mature in dunning, proration, and subscription analytics, but says its simple counters lack AI context capture [13]. Lago likewise characterizes usage-based billing as not a Recurly core strength [14]. Taken together, those accounts position Recurly’s documented 2026 announcements around engagement and subscription operations, while the case for choosing it over Stripe for complex metering remains a third-party judgment [8, 13, 14]. †

## Paddle: subscription features within a merchant-of-record model

Paddle positions Billing as an all-in-one merchant-of-record offering for companies selling software and other digital products globally, with subscription management, fraud detection and tax compliance included in a stated fee of 5% + 50¢ per transaction [15]. Paddle’s model includes calculating, collecting and remitting VAT, GST and sales tax for digital goods and SaaS; it also automatically sends customers a credit note when a transaction is refunded or credited [9, 16]. This makes tax responsibility and the bundled fee central to a comparison with Stripe, rather than subscription features alone [15, 16].

Paddle documents a substantial subscription toolkit: multiple plans and billing intervals, free trials, discounts and coupons, mid-cycle proration, plan changes, and pausing and resuming subscriptions [16, 27]. Its customer portal lets buyers manage subscriptions, payments and account information [9]. Sellers can add recurring or one-time items to a subscription without first adding them to the product catalog, specify that a billing-frequency change should not trigger proration or billing, and update a subscription even when a pause or cancellation is already scheduled [9]. As of June 11, 2026, Paddle also documents paid trials that charge a reduced amount before renewal at the full subscription price [9].

**Metering is documented, but its depth is less clear.** A 2026 review says Paddle supports charging based on customer usage and labels its usage-based billing “limited” in a comparison table; it does not detail the scope of Paddle’s metering tools [16].

Paddle’s 2025–2026 announcements also require a distinction between available features and rollout plans [9, 22]:

- Paddle launched automatic tax display by buyer location, switching between tax-inclusive and tax-exclusive prices according to the buyer’s country [22].
- Cardless trials were live only in Developer Preview for customers in Paddle’s Early Access program [22]. †
- Paddle said cancellation flows configurable in the Billing dashboard, with pause, downgrade, discount and support-contact options, were planned for early 2026; separately, its developer changelog documents dynamic cancellation flows in the customer portal as of January 9, 2026 [9, 22].
- Paddle said an in-dashboard tool for migrating subscribers from Paddle Classic to Paddle Billing was planned for general access in early 2026, while migration was already possible using its developer documentation [22].
- Paddle reported BLIK and MB Way live for Billing customers in Europe and Pix available in Brazil, while UPI was rolling out to an early-access cohort in India; its changelog separately documents KakaoPay and Naver Pay for subscriptions as of November 19, 2025 [9, 22].

## At-a-glance commercial comparison and buying implications

**The headline rates do not buy the same thing:** Stripe Billing’s fee is separate from payment processing, while Paddle’s checkout fee covers a merchant-of-record model that includes subscription management and tax compliance [15, 17, 18]. Compare the total cost of the operating model, not just the percentages [17, 18].

| Option | Published commercial terms and scope |
|---|---|
| **Stripe Billing** | Its pay-as-you-go fee is 0.7% of billing volume **on top of** standard Stripe payment-processing fees; according to withorb.com, qualifying volume includes billing processed on and off Stripe but excludes one-off invoices [2, 17]. Lago describes a public Stripe Payments example of 2.9% plus $0.30 per processed transaction [28]. Usage-based billing through Metronome is priced separately, and erpresearch.com reports annual plans billed monthly with volume discounts [17]. |
| **Recurly** | According to getlago.com, Starter costs $249 per month plus 0.9% of billing volume, with the first $40,000 per month included free [14]. Stackscalehq.com says Recurly also commonly uses customized pricing, often tied to subscriber volume or billing complexity; businesses may need to request a quote to compare platform costs [12]. |
| **Paddle** | Paddle states that pay-as-you-go pricing is 5% plus $0.50 per checkout transaction, with custom pricing for larger companies; the rate is also reported by UniBee and Lago [14, 15, 16]. Paddle is a merchant of record rather than a payment service provider, and its price includes subscription management and tax compliance [15, 18]. |

**Check the Stripe quote before modeling it.** Paddle’s comparison page lists Stripe recurring-payment rates of 0.5% on Standard and 0.8% on Scale, alongside 2.9% plus $0.30 in standard transaction fees, whereas the Stripe Billing rate reported above is 0.7% [15, 17]. Those published descriptions differ, so a buyer should confirm which plan and rate apply rather than combining them in one estimate [15, 17].

For a business already charging through Stripe with a simple usage meter, Stripe Billing is described by ustechautomations.com as a default choice; the commercial test is its applicable Billing rate **plus** processing charges and any separately priced Metronome usage [11, 17]. Recurly warrants a quote where its Starter terms may not describe the intended deal [12, 14]. Paddle’s higher headline checkout fee should be assessed against the tax-compliance responsibility it assumes: under standard Stripe, the seller remains responsible for tax registration, collection and remittance, while Paddle handles global tax compliance as merchant of record [18, 29]. Paddle also requires a business review before activation, which can slow initial setup [18].

## Methodology & limitations

- **Research questions:** 5 planned, plus 4 follow-up searches the Critic requested (1 gap loop; research stopped because: coverage met).
- **Sources read:** 35 pages, 14 of them on the official sites of the companies covered.
- **Verification:** 258 extracted findings were checked. Each quote was matched against its source text, each claim against its quote, and third-party claims against the other sources.
  - 122 verified (88 stated by the vendor about itself), 106 single-source (attributed in the text), 3 contradicted by another source (noted in the text).
  - 27 rejected and excluded: 0 quotes not found in their source, 27 claims their quote did not support, 0 failed cross-referencing. Most common reasons: overstates its quote (21); unsupported (6).
- **Sentence audit:** 98 statements were checked against the findings they cite; 6 were flagged and revised. 3 still flagged after revision are marked †.
- **Limits:** web sources as retrieved on the date above; vendor pages describe their own products favourably, and pricing changes often. Treat single-source and contradicted claims as leads to confirm.

## References

1. [Stripe Blog: Changelog](https://stripe.com/blog/changelog): stripe.com · vendor source · accessed 2026-09-23
2. [Stripe Billing reviews 2026](https://www.withorb.com/blog/stripe-billing-reviews): withorb.com · accessed 2026-09-23
3. [Stripe Usage-Based Billing: What Stripe Handles (and Doesn’t)](https://www.stigg.io/blog-posts/stripe-usage-based-billing): stigg.io · accessed 2026-09-23
4. [Our top product updates from Sessions 2025](https://stripe.com/blog/top-product-updates-sessions-2025): stripe.com · vendor source · accessed 2026-09-23
5. [Configure trial offers on subscriptions | Stripe Documentation](https://docs.stripe.com/billing/subscriptions/trials): docs.stripe.com · vendor source · accessed 2026-09-23
6. [What Is Usage-Based Pricing? | Stripe](https://stripe.com/au/resources/more/usage-based-pricing-101-what-it-is-and-strategies-to-implement-it): stripe.com · vendor source · accessed 2026-09-23
7. [Chargebee: Billing & Monetization for SaaS and AI Companies](https://chargebee.com?ref=logotyp.us): chargebee.com · vendor source · accessed 2026-09-23
8. [What's New: Recurly Spring Release 2026 Highlights](https://recurly.com/blog/recurly-spring-release-2026-highlights): recurly.com · vendor source · accessed 2026-09-23
9. [Developer changelog | Paddle Developer Docs](https://developer.paddle.com/changelog): developer.paddle.com · vendor source · accessed 2026-09-23
10. [Usage-Based Billing Software: 6 Top Picks for 2026](https://www.stigg.io/blog-posts/usage-based-billing-software): stigg.io · accessed 2026-09-23
11. [Compare 7 Usage-Based Billing Software Tools 2026](https://ustechautomations.com/resources/blog/best-usagebased-billing-software-2026): ustechautomations.com · accessed 2026-09-23
12. [Chargebee vs Recurly vs Stripe Billing (2026): Pricing & Features](https://stackscalehq.com/chargebee-vs-recurly-vs-stripe-billing): stackscalehq.com · accessed 2026-09-23
13. [Usage-Based Billing APIs Compared (2026): Stripe, ...](https://usagebox.com/articles/usage-billing-apis-comparison-2025): usagebox.com · accessed 2026-09-23
14. [Top 7 Stripe Billing Alternatives for Usage-Based Billing (2026) | Lago](https://getlago.com/blog/top-7-alternatives-to-stripe-billing-for-usage-based-billing): getlago.com · accessed 2026-09-23
15. [FastSpring vs Stripe | Choosing the best platform in 2026](https://www.paddle.com/alternatives/fastspring-vs-stripe): paddle.com · vendor source · accessed 2026-09-23
16. [Paddle Review 2026: Features, Pricing, Pros & Cons | UniBee](https://unibee.dev/blog/paddle-review-features-pricing-pros-cons): unibee.dev · accessed 2026-09-23
17. [Stripe Billing Review (2026): Pricing, Integrations & Alternatives | ERP Research](https://www.erpresearch.com/erp-add-ons/billing-subscriptions/stripe-billing): erpresearch.com · accessed 2026-09-23
18. [Paddle vs Stripe vs Lemon Squeezy (2026): Best Merchant of Record for SaaS | Artisan Strategies](https://www.artisangrowthstrategies.com/blog/paddle-vs-stripe-vs-lemon-squeezy-2026): artisangrowthstrategies.com · accessed 2026-09-23
19. [Changelog - Stripe Documentation](https://docs.stripe.com/changelog): docs.stripe.com · vendor source · accessed 2026-09-23
20. [Log des modifications | Documentation Stripe](https://docs.stripe.com/changelog?locale=fr-FR): docs.stripe.com · vendor source · accessed 2026-09-23
21. [Pay-as-You-Go And Usage-Based Pricing Examples | Stripe](https://stripe.com/us/resources/more/pay-as-you-go-and-usage-based-pricing-examples): stripe.com · vendor source · accessed 2026-09-23
22. [Paddle Forward: Fall 2025 product updates](https://www.paddle.com/blog/paddle-forward-november-2025-product-updates): paddle.com · vendor source · accessed 2026-09-23
23. [Stripe Billing vs Chargebee in 2026 (Real Test)](https://churntools.com/blog/stripe-billing-vs-chargebee): churntools.com · accessed 2026-09-23
24. [Subscription Pricing Strategies: 2026 Models & Guide - Chargebee](https://www.chargebee.com/blog/subscription-pricing-strategies): chargebee.com · vendor source · accessed 2026-09-23
25. [Best Usage-Based Billing Software in 2026](https://coldiq.com/blog/best-usage-based-billing-software-in-2026): coldiq.com · accessed 2026-09-23
26. [Compare Recurly vs Stripe Billing](https://www.peerspot.com/products/comparisons/recurly_vs_stripe-billing): peerspot.com · accessed 2026-09-23
27. [Paddle Review 2026: Pros, Cons & Pricing Explained - DEV Community](https://dev.to/onsen/paddle-review-2026-pros-cons-pricing-explained-4cgk): dev.to · accessed 2026-09-23
28. [Does Stripe use Stripe Billing to bill its customers? | Lago](https://getlago.com/blog/is-stripe-using-stripe): getlago.com · accessed 2026-09-23
29. [Lemon Squeezy vs Stripe vs Paddle: Merchant of Record 2026](https://getstacksmart.com/blog/stripe-vs-lemon-squeezy-vs-paddle-solopreneur): getstacksmart.com · accessed 2026-09-23