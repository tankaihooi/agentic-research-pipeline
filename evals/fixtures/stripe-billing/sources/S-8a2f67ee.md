# Stripe Usage-Based Billing: How It Works + Code [2026]

Ben has built fintech products and scaled technology teams from an early stage through to unicorn. He was previously VP Engineering at TrueLayer and SVP Engineering at Checkout.com.

Stripe is the default payment processor for most startups. When those startups need to charge customers based on actual usage rather than flat monthly fees, St

[…]

# Stripe Usage-Based Billing: How It Works + Code [2026]
## The object chain: meter, product, price, customer, subscription
### Step 2: create a Product
represents your service in Stripe's catalog.

```
// POST /v1/products const product = await stripe.products.create({ name: "AI Image Generation", }); // → product.id — required for price creation
```

### Step 3: create a metered Price

The price defines the rate and links the product to the meter.

```
// POST /v1/prices const price = await stripe.prices.create({ product: product.id, currency: "usd", billing_scheme: "per_unit", unit_amount_decimal: "5", // $0.05 per image recurring: { interval: "month", usage_type: "metered", meter: meter.id, }, }); // → price.id — required at subscription creation
```

### Step 4: create a Customer

Register the customer with a default payment method.

```
// POST /v1/customers const customer = await stripe.customers.create({ name: "Jane Doe", email: "jane@acme.com", invoice_settings: { default_payment_method: paymentMethodId }, });
```

### Step 5: create a Subscription

Links the customer to the metered price. The subscription is the active billing relationship.

```
// POST /v1/subscriptions const sub = await stripe.subscriptions.create({ customer: customer.id, items: [{ price: price.id }], payment_behavior: "default_incomplete", expand: ["latest_invoice.payment_intent"], }); // Must confirm the payment intent before sub is active
```

> 5 API calls, 5 object IDs to store. The chain is strictly ordered; each step depends on the previous.

## How meter events work

Each time a customer generates an image, report a meter event to Stripe. Stripe aggregates these over the billing period and includes them in the end-of-cycle invoice.

```
// After image generation completes: await stripe.billing.meterEvents.create({ event_name: "image_generated", payload: { stripe_customer_id: customer.id, value: "1", // one image }, timestamp: Math.floor(Date.now() / 1000), }); // Usage queued. Customer NOT charged yet. // $0.05 collected at end of billing period.
```

> Usage accumulates until the billing cycle ends. There is no immediate charge.

For an AI product generating thousands of images per customer per day, this means you are fronting compute costs until Stripe collects at period end. Stripe processes meter events asynchronously. There is no synchronous confirmation that a specific event was accepted and will appear on the invoice.

---

## The webhook infrastructure you need

Stripe's deferred billing model means invoices are generated and payments collected asynchronously. If you're building any kind of usage display, balance tracking, or access control on top of Stripe, you need a webhook listener to keep your application state in sync.

For example, if you want to show customers their billing status, suspend access after a failed payment, or update an internal usage dashboard when an invoice finalises, you must handle these events server-side:

```
app.post("/stripe/webhook", express.raw({ type: "*/*" }), async (req, res) => { const event = stripe.webhooks.constructEvent( req.body, req.headers["stripe-signature"], WEBHOOK_SECRET ); switch (event.type) { case "invoice.payment_succeeded": await updateCustomerBillingStatus(event.data.object.customer, "paid"); break; case "invoice.payment_failed": await suspendCustomerAccess(event.data.object.customer); break; case "customer.subscription.updated": await syncSubscriptionState(event.data.object); break; } res.json({ received: true }); });
```

> Minimum 3 event types to handle. Any custom billing UI or access control logic depends on these webhooks staying reliable.

This webhook handler is not optional if you're building usage visibility or access gating. It is infrastructure you build, deploy, monitor, and maintain. If it goes down, your application's billing state drifts from Stripe's. Common issues with Stripe metered billing often trace back to webhook reliability.

---

## What Stripe's customer portal covers (and what it doesn't)

Stripe provides a hosted Customer Portal out of the box, but it is invoice-focused. It shows billing history, lets customers download invoices, and manages payment methods.

```
const session = await stripe.billingPortal.sessions.create({ customer: customer.id, return_url: "https://app.com/account", }); // redirect to session.url
```

**What you get for free:**

* Invoice history and PDF download
* Payment method management
* Subscription cancellation

**What you must build yourself for a pay-as-you-go product:**

* Live usage counter (images generated this period)
* Current period cost estimate
* Usage history and breakdown

To build usage visibility you'll need to query `stripe.billing.meters.listEventSummaries()`, combine the data with subscription and pricing information, and render your own UI component. For teams implementing consumption-based pricing, this custom frontend work adds weeks to the timeline.

---

## How pricing changes work in Stripe

Price objects in Stripe are immutable. Changing your rate from $0.05 to $0.08 per image requires creating a new Price object and migrating every active subscription to it. There is no "update price" operation.

```
// 1. Create new price at $0.08 const newPrice = await stripe.prices.create({ product: product.id, currency: "usd", unit_amount_decimal: "8", recurring: { interval: "month", usage_type: "metered", meter: meter.id }, }); // 2. Migrate each active subscription await stripe.subscriptions.update(sub.id, { items: [{ id: sub.items.data[0].id, price: newPrice.id }], }); // Repeat for every active subscriber
```

> For large customer bases this is a bulk migration job, not a config change.

---

## Key trade-offs with Stripe's metered billing approach

Stripe Billing is a comprehensive revenue platform. Its metered billing works well for many SaaS products. But certain architectural decisions create trade-offs worth understanding, especially for AI products with real-time costs.

**Deferred billing creates financial exposure.** Usage happens now; payment happens later. For AI products where every API call incurs infrastructure cost (GPU time, model inference, storage), you absorb that cost until the invoice cycle ends. If a customer racks up $10,000 in usage and the end-of-month invoice fails, you have already spent the money.

**No real-time balance enforcement.** Stripe meters usage but does not gate it. There is no built-in mechanism to check "does this customer have enough balance to generate this image?" before the action happens. You build that logic yourself or accept the risk.

**Webhook dependency for billing UI and access control.** If you build any custom usage display, balance tracking, or access gating, you need reliable webhook infrastructure to keep your application in sync with Stripe. Payment success, failure, and subscription changes all flow through webhooks.

**Immutable pricing requires migration.** Every pricing change means creating new Price objects and migrating subscriptions individually. This is a common pattern in billing systems, but it adds operational overhead when you're iterating on pricing frequently, especially at the early stages when finding the right billing model matters most.

**Customer portal gaps.** The hosted portal handles invoices, not usage. If your customers expect a experience like OpenAI's billing page (live usage tracking, current period costs, usage breakdowns), you build it from scratch.

These are not bugs. They are consequences of an invoice-native architecture applied to real-time use cases. For teams whose products incur costs per action and need balance control before usage happens, the question becomes whether to build these missing layers on top of Stripe or use infrastructure designed around real-time billing from the start.

---

## How Credyt handles the same job

Credyt is real-time billing infrastructure built around wallets. Customers prepay into a balance; every usage event debits that balance immediately. There are no invoices, no billing cycles, and no end-of-period reconciliation. Here