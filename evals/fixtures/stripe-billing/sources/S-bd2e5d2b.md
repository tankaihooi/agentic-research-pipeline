For AI agents: visit https://docs.recurly.com/recurly-subscriptions/llms.txt for an index of all pages formatted in Markdown and endpoints in OpenAPI. Append .md to any documentation page URL to get its markdown version.

---

Product Docs

# Pricing & plans 101: Plans

Learn how to configure and structure subscription plans in Recurly. Understand key plan fields, permanent billing intervals, subscription terms, unique plan codes, and the business case for balancing monthly vs. annual billing.

**Upcoming:** Bring your pricing questions to Global Office Hours. Register now →

 Acquire · Pricing & Plans 101

# Plans

Plans are the foundation of every subscription you offer. This page covers what a plan is, how to structure one, and the decisions that matter most before you start building.

  Navigation Menu

 Navigate Home  Path Overview   Plans  2 Add-ons 3 Currency 4 Pricing models 5 Trials 6 Tracking success 7 Review & resources

## What is a plan?

A plan is the template for a subscription. Every subscriber signs up to a plan — it defines what they get, how much they pay, and when they're billed. You configure plans once; Recurly applies those settings to every subscription created from that plan automatically.

#### Billing interval

How often the subscriber is charged — weekly, monthly, quarterly, annually, or a custom interval. Cannot be changed after the plan is created.

#### Subscription term

The commitment length. A term can span multiple billing periods (e.g., an annual plan billed monthly). Adjustable per subscription at creation.

#### End-of-term behavior

Whether subscriptions auto-renew or expire at the end of each term. Set at the plan level; override per subscription if needed.

#### Pricing model

Fixed, ramp, or usage-based. Determines how the amount charged is calculated each billing period. Covered in detail on the Pricing models page.

**Billing interval is permanent**

Once a plan is created, you cannot change its billing interval — doing so would disrupt active subscriptions. If you need a different interval, create a new plan. Plan your billing intervals before you start building.

## Key plan fields

When you create a plan at **Configuration → Plans**, these are the settings that shape every subscription created from it.

| Field | What it controls | Change after creation? |
| --- | --- | --- |
| Plan name | Display name shown to subscribers and in the Admin Console. Updates site-wide — existing subscriptions show the new name. | Yes |
| Plan code | Unique identifier used in API calls and integrations. Case-sensitive. | No |
| Billing interval | How frequently the subscriber is charged (weekly, monthly, annually, custom). | No |
| Subscription term | The full commitment length. Can span multiple billing periods. | No (create new plan) |
| Setup fee | A one-time charge collected when the subscription is created. | Yes (new subscribers only) |
| Trial period | Duration of a free or reduced-price trial before first charge. | Yes (new subscribers only) |
| End-of-term | Auto-renew or expire at term end. | Yes |

**Versioned vs. global changes**

Price, billing interval, and setup fees are versioned — changes apply to new subscribers only. Existing subscribers keep what they signed up for. Plan name updates apply globally and appear immediately across all active subscriptions.

## Monthly vs. annual — the business case

Most subscription businesses offer both billing intervals. The data supports making annual plans a priority: subscribers on annual plans generate 50–60% more revenue per year and churn significantly less. Based on 2026 industry benchmarks, 78% of subscription businesses offer both monthly and annual options.

| Factor | Monthly plan | Annual plan |
| --- | --- | --- |
| Revenue per subscriber | Lower — 12 discrete charges | 50–60% higher annually |
| Churn risk | Higher — 12 renewal decision points | Lower — 1 renewal per year |
| Cash flow | Predictable monthly inflow | Upfront lump sum |
| Subscriber commitment | Lower barrier to entry | Higher intent at signup |
| Best for | Acquisition, lower price points | Retention, higher LTV |

**Discount annual plans to drive uptake**

A common approach: price the annual plan at 10–20% below the equivalent monthly total. This creates a clear incentive for subscribers to commit upfront and raises your average LTV without reducing perceived value.

## How to create a plan

Plans are created in the Admin Console. Before you start, decide on your billing interval and plan code — both are permanent after creation.

1

#### Navigate to Plans

Go to **Configuration → Plans** in the Recurly Admin Console and click **New Plan**.

2

#### Set your plan code

Enter a plan code — this is your internal identifier u