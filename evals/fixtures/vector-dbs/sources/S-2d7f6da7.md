## The Primary User Is Changing

Every technological paradigm shift produces a defining data infrastructure category. Relational databases for client-server. Object stores for clouds. Vector databases for Assistive AI.

Pinecone built the market-leading vector database. 800,000+ active developers and 9,000+ paying customers run their AI on it: semantic search, recommendation systems, retrieval-aug

[…]

# The Primary User Is Changing
gement remain essential. But the retrieval patterns agents need are fundamentally different from what humans need. That is what changed.

**The agentic era needs something different.**

## Introducing Pinecone Nexus

Pinecone Nexus is a knowledge engine, not a retrieval system. The distinction matters.

A retrieval system finds documents and hands them to a frontier model at inference time. The model burns tokens sifting through raw content, introduces latency, and risks hallucination. This is reasoning at the retrieval stage. It is fragile, slow, and expensive.

Nexus moves the reasoning upstream, from retrieval to knowledge compilation. It structures, contextualizes, and composes specialized contexts (derived *artifacts*) before the agent needs them. The agent receives trusted knowledge in a context-specific structured format, not raw documents. It completes the task, not the retrieval. Frontier models are freed to do what they were designed for — intelligent reasoning, not managing knowledge.

With Nexus, governance is built into the knowledge engine. Context is assembled dynamically per task, scoped to RBAC permissions, and free of context-rot. Every artifact is versioned — every answer traces back to its source data and transformations. PII is tagged at ingest with centralized rules governing how LLMs process it. Token consumption is managed across users and workloads in one place, and a unified dashboard provides real-time visibility into usage, spend, and compliance.

Nexus has two core components: a context compiler and a composable retriever. The context compiler builds and organizes knowledge around how your company operates. The composable retriever formats and serves responses precisely for how each agent needs knowledge to complete its task.

**The context compiler** is the heart of the shift. Give it source data and a task spec. It compiles raw data into task-optimized specialized contexts. These contexts include newly-derived artifacts — the concrete form of information an AI agent acts on. Purpose-built for accuracy and speed, agents consume these artifacts directly. Unlike a traditional compiler, it is iterative: it experiments with representations, evaluates them against the task, and converges on the precise knowledge structure the agent needs. The work that used to happen at inference time, burning tokens and producing ambiguous results, now happens once at compilation time — and gets better with every iteration.

Take a mid-market SaaS company. Its data lives in a data warehouse, Salesforce, Slack, Gong, Gmail, Jira, Google Drive.

The current approach: point a vibe coding tool at all the sources and unleash it to perform the task. It scans everything, retrieves what it can, and hopes the right context surfaces. Sometimes it works. Often it hallucinates, misses critical connections, or drowns in irrelevant data.

The context compiler works differently. It reads the same underlying data but builds specialized context artifacts for each agent's task:

A **Sales Agent** gets deal context — Gong transcripts synthesized with opportunity stages, champion email threads, and competitive mentions from Slack. Not a CRM lookup. A picture of the deal.

A **Finance Agent** gets revenue context — contract terms linked

[…]

# KnowQL: A Declarative Query Language for Agents
reliable, ungoverned answers.

“Standard depth, under 500 milliseconds.”No budget envelope. Every call runs however deep, however long. Unpredictable, slow, wasteful.

***KnowQL gives agents the vocabulary they are missing*.** Six core primitives: intent, filter, provenance, output shape, confidence, and budget, in a single declarative interface that returns trusted knowledge — structured, precise, and grounded. Composable across the heterogeneous knowledge sources that real enterprise AI requires.

> Building reliable, long-horizon agents is fundamentally a context engineering problem. Getting the right information to the agent in the right format is what separates demos from production. Pinecone Nexus solves that at the knowledge layer, and KnowQL is the standard interface the agentic ecosystem has been waiting for. That's why LangChain is collaborating with Pinecone to advance it. And as teams build agents with Nexus, LangSmith gives them the observability and evals to help them move through the agent improvement loop. – Harrison Chase, CEO of LangChain

> Enterprises win with agentic AI when their agents can reason over the full landscape of trusted business data. Teradata is partnering with Pinecone on KnowQL and Knowledge engine, giving the world's most demanding organizations a clear path from governed data to autonomous, accurate, agent-driven outcomes — backed by the scale and trust enterprises have built on Teradata. – Sumeet Arora, Chief Product Officer, Teradata

*Early access for Pinecone Nexus and KnowQL is open now to customers and partners building agent-native applications in financial services, healthcare, legal, enterprise SaaS, and any domain where agents reason over complex, proprietary knowledge.*

## What Pinecone Nexus & KnowQL Make Possible

Knowledge Artifact Curation

The context compiler produces persistent, durable knowledge representations that maintain context across sessions, users, and workflows. Not ephemeral retrieval results but rather curated artifacts that compound over time. This becomes the system of knowledge for the organization.

Autonomous Query Planning

An embedded agent builds and refines ingestion and retrieval pipelines purpose-built for each task. The pipeline adapts to the context, not the other way around.

Governed Reasoning at Scale

Native hybrid retrieval, vector and full-text unified, delivering semantic breadth with exact-match precision at agent query volumes. Per-field citations, confidence scores, and ACL-aware filtering make every answer auditable and policy-safe by default.

Composable Retrieval with KnowQL

Agents compose knowledge access on demand using the six KnowQL primitives. Vertical AI applications become buildable without custom retrieval infrastructure for every deployment.

**Measured impact:** Task completion rates above 90%. 30x faster time-to-completion. Measurably improved precision and relevance, with every answer cited, scored, and auditable. And up to 90% less token spend on top of it. This changes the ROI equation for enterprise AI.

## Pinecone Marketplace: From Pinecone Nexus to Production in Minutes

Pinecone Nexus gives agents trusted knowledge. Pinecone Marketplace gives teams the fastest path to production.

Most teams spend more time assembling ingestion, embedding, retrieval, and orchestration plumbing than building the applications that make them unique. Marketplace eliminates that with production-ready knowledge applications, built by Pinecone and partners, deployable and customizable in minutes. No infrastructure assembly required.

These are not demos. Every solution in the Marketplace addresses a problem our customers are actively building for.

**Launch-day solutions:**

Pinecone Marketplace launches with more than 90 knowledge applications across the following categories and more:

Sales & Revenue

Equip reps with instant answers on product, pricing, and competitive positioning. Streamline deal approvals, discount exceptions, and contract decisions — all grounded in your internal knowledge.

Insurance

End-to-end apps for underwriting, claims, fraud, policy servicing, and compliance. Purpose-built for the document-heavy workflows that define every role in the insurance value chain.

Real Estate

Cover the full CRE lifecycle, from acquisitions diligence and development to leasing, asset management, and property operations. Purpose-built for the deal teams and operators who move markets.

Legal & C

[…]

# Pinecone Marketplace: From Pinecone Nexus to Production in Minutes
rface customer signal that feeds directly into product and CX strategy.

*Free at launch. Partner-built commercial solutions coming soon. Built to be modified, extended, and taken to production.*

> 2026 is the year agents move from workflows to employees — and the bottleneck is no longer the model, it's getting agents grounded in the right knowledge. We're excited to bring LlamaParse's document ingestion and parsing into Pinecone Nexus and the Pinecone Marketplace. Teams can now go from messy documents with complex layouts, tables, handwriting, and images to trusted knowledge ready for agents to act on — whether they're shipping a Marketplace app or building on Nexus directly. – Jerry Liu, CEO of LlamaIndex

> Enterprise AI only delivers when it shows up inside the workflows teams actually rely on. ThoughtFocus is partnering with Pinecone on two fronts: building production-ready knowledge applications on the Pinecone Marketplace for our clients, and deploying those same applications inside ThoughtFocus to accelerate how our own teams work every day. The Marketplace gives services partners like us a way to package deep domain expertise into customer-ready apps — and to prove the model on ourselves first. This is how enterprise AI moves from pilots to production. — Nick Sharma, CEO of ThoughtFocus

## Removing the Barrier to Build

The best knowledge infrastructure on the market should be accessible to every builder, at every stage. We restructured pricing to make that real.

### Builder Tier — $20/Month

Full access to Pinecone’s production-grade infrastructure for developers and small teams. No degraded performance. Flat, predictable cost. No surprise bills. Free support. The same Pinecone that enterprises run mission-critical workloads on, now at a price that removes the barrier for any serious builder.

### Dedicated Read Nodes

On-Demand works exactly as designed for variable, unpredictable workloads. As retrieval scales — sustained high volume, tight latency SLO’s, finance asking for predictable spend — fixed pricing becomes necessary. Dedicated Read Nodes (DRN) gives you dedicated, provisioned read capacity with a warm data path. Vectors stay hot. No cold starts. No rate limits. Fixed hourly per-node pricing. Production workloads see **77–97% cost reduction at scale.**

### Bring Your Own Cloud

For organizations with data residency requirements, regulatory constraints or existing cloud commitments, BYOC deploys Pinecone fully managed within your cloud environment. Complete data control that includes Pinecone Nexus very soon, with the simplicity of a managed service.

*Builder tier at $20/month, DRN, and BYOC for the largest enterprises exist for the same reason: infrastructure should enable ambition, not constrain it.*

## The Full Stack

Today’s announcements are new components of Pinecone’s knowledge platform:

| LAYER | PRODUCT | WHAT IT DOES |
| --- | --- | --- |
| Access Layer | **Pinecone Marketplace**New | Production-ready knowledge applications. Deploy in minutes. No infrastructure assembly required. |
| Knowledge Engine | **Pinecone Nexus + KnowQL** New | Transforms organization data into trusted, persistent, queryable knowledge for agents. KnowQL is the declarative query language for the agentic era. |
| Foundation | Pinecone Database | Native hybrid retrieval with **full-text search**New. BYOC. DRN. **Builder tier**New at $20/mo. The most performant and affordable vector database in the market. |

Based on years of partnering with our users to build knowledge retrieval systems and the real-world demands we uncovered developing Pinecone Nexus, we integrated native full-text search into the core Pinecone Database. This ensures the stack handles the unique economic and technical demands of agent-scale query volumes. We will continue to evolve the core database based on these Nexus workloads, ensuring our infrastructure is purpose-built for the speed of autonomous AI.

## What Comes Next

We pioneered the vector database and defined RAG as a standard pattern. Those contributions are embedded in AI infrastructure today. Our continuous research and engineering innovation enables us to lower prices so that both the solo builder and the largest global enterprise can build on Pinecone.

What is unique to every organization, and what did not exist until today, is a knowledge engine that moves reasoning from retrieval to curation. A declarative query language that gives agents the vocabulary they have been missing. Infrastructure architected for agentic systems operating at orders of magnitude beyond human scale.

The companies that will define their industries over the next decade are building agents that operate on trusted knowledge. They are discovering that the limits they thought were intrinsic — limited expert bandwidth, slow decision cycles, high cost per unit of insight — were infrastructure problems wait