# EU AI Act Article 55: GPAI systemic risk obligations explained

Article 55 of the EU AI Act binds providers of general-purpose AI models with systemic risk: model evaluations including adversarial testing, systemic risk assessment + mitigation, serious incident reporting to the AI Office under Article 55(1)(c), and adequate cybersecurity. The 10^25 FLOP cumulative compute threshold triggers the

[…]

# EU AI Act Article 55: GPAI systemic risk obligations explained
**model evaluations, adversarial testing, risk mitigation, incident reporting, cybersecurity**
* Article 55(1)(c) incident reports go to the **AI Office**, not national authorities
* Applied from **2 August 2025**; full Commission enforcement live since **2 August 2026**
* Fines under Article 101: up to **EUR 15M or 3% of turnover**, whichever is higher
* The Omnibus deal of 7 May 2026 did **not** change Article 55
* Major signatories of the voluntary Code of Practice: **OpenAI, Anthropic, Google, Mistral**

Check the threshold

Are you above the 10^25 FLOP systemic-risk threshold?

Convert from H100 GPU-days, GPU-years, or raw FLOPs and see whether Article 55 obligations attach. Reference table for known frontier models included.

## Who Article 55 actually applies to

Article 55 applies to **providers** of general-purpose AI (GPAI) models classified as having **systemic risk** under Article 51"). Three things matter for that classification.

First, the model must be a GPAI model. Article 3(63)") defines a GPAI model as an AI model trained on broad data, designed for generality of output, capable of competently performing a wide range of distinct tasks, and able to be integrated into a variety of downstream systems or applications. In practice this captures foundation models: GPT-4 and successors, Claude, Gemini, Llama, Mistral Large, and similar frontier models. Models trained for a single narrow task are not GPAI.

Second, the model must reach the systemic-risk threshold. Article 51(2) sets the trigger as cumulative training compute exceeding **10^25 floating-point operations (FLOP)**. Models below the threshold are still subject to the baseline Article 53 obligations (technical documentation, copyright policy, downstream transparency) but not the additional Article 55 systemic-risk obligations.

Third, even if a model is below the threshold, the Commission can designate it as systemic-risk under Article 51(1)(b) based on a separate set of criteria: number of users, modalities, scientific or technical complexity, market reach, or capabilities equivalent to those of state-of-the-art GPAI models. This is the Commission's escape hatch for capability surprises.

## What changed on 2 August 2025

The GPAI provider regime under Articles 51 to 56 became enforceable on 2 August 2025. Before this date, the regulation was in force (since 1 August 2024) but the specific GPAI provisions had a 12-month transition period. From 2 August 2025 onwards:

**Article 53 baseline obligations apply to every GPAI provider.** Technical documentation under Annex XI, downstream-provider information packs under Annex XII, copyright policy, and a public summary of training data per Article 53(1)(d).

**Article 55 obligations apply to systemic-risk GPAI providers.** Model evaluations, risk assessment + mitigation, Article 55(1)(c) incident reporting, cybersecurity.

**Notification to the Commission.** Providers must notify the Commission within two weeks of reasonably foreseeing or reaching the 10^25 FLOP threshold (Article 52(1)).

Crucially, the 2 August 2025 date is when the obligations became *legally enforceable*. The Commission's *enforcement powers* (formal requests for information, model recalls, administrative fines) followed on **2 August 2026**. Between those two dates sat a deliberate transitional period: providers were legally bound while the AI Office staffed up, the Code of Practice was operationalised, and the Commission's enforcement playbook was finalised. That window has closed; the Commission's enforcement powers are now live.

Newsletter

Weekly EU AI Act updates, delivered.

One email per week. Deadlines, enforcement actions, regulatory shifts. Curated by John Ferguson, founder of Agentic Fluxus. Unsubscribe anytime.

## Article 53: the baseline every GPAI provider must meet

Before getting to the systemic-risk-specific Article 55 obligations, every GPAI provider must satisfy Article 53"). These obligations are not specific to systemic risk; they apply whether your model is 10^22 FLOP or 10^27 FLOP.

### Technical documentation (Article 53(1)(a))

Providers must draw up and keep up-to-date technical documentation of the model, including its training and testing process and the results of its evaluation. The minimum content is set out in Annex XI of the regulation. The documentation must be made available to the AI

[…]

# EU AI Act Article 55: GPAI systemic risk obligations explained
## Article 53: the baseline every GPAI provider must meet
### Training data summary (Article 53(1)(d))
nly:

• Technical documentation (Annex XI)

• Downstream-provider info pack (Annex XII)

• Copyright policy + rights-reservation handling

• Public training-data summary

Penalty ceiling: **EUR 15M / 3%** for Article 53 violations under Article 101.

Above threshold≥ 10^25 FLOP

Article 53 baseline + Article 55:

**+** 55(1)(a): model evaluations + adversarial testing

**+** 55(1)(b): systemic risk assessment + mitigation

**+** 55(1)(c): incident reporting to AI Office

**+** 55(1)(d): cybersecurity protection

Notification within **2 weeks** of foreseeing or reaching the threshold (Article 52(1)).

**Models widely understood above the threshold (Code of Practice signatories):** OpenAI GPT-4 class and above, Anthropic Claude 3 Opus class and above, Google Gemini Ultra class, Mistral's largest models. GPT-3 (175B params, 2020) was ~3.14 × 10^23 FLOP, two orders of magnitude below.

**Methodology.** Threshold derived from Article 51(2) of Regulation (EU) 2024/1689. The Commission can also designate a model as systemic-risk under Article 51(1)(b) on capability + reach criteria below the compute threshold. Penalty ceilings from Article 101. Sources: Article 51, Article 53, Article 55, Code of Practice.

## Article 55: the additional load for systemic-risk GPAI

For models above the 10^25 FLOP threshold (or designated by the Commission as systemic-risk), Article 55 adds four obligations on top of Article 53.

### Article 55(1)(a): Model evaluations including adversarial testing

Providers must perform model evaluation in accordance with state-of-the-art protocols and tools, including conducting and documenting adversarial testing of the model. The aim is to identify and mitigate systemic risks. The Code of Practice (see below) provides operational guidance on what "state-of-the-art" means in practice: red-teaming, capability evaluations against benchmarks, jailbreak resistance testing, misuse-potential analysis.

### Article 55(1)(b): Systemic risk assessment and mitigation

Providers must assess and mitigate possible systemic risks at the Union level, including their sources, that may stem from development, placing on the market, or use of GPAI models with systemic risk. Article 3(65) defines systemic risk as a risk that is specific to the high-impact capabilities of GPAI models, having a significant impact on the Union market due to their reach, or due to actual or reasonably foreseeable negative effects on public health, safety, public security, fundamental rights, or society as a whole, that can be propagated at scale across the value chain.

### Article 55(1)(c): Serious incident reporting

Providers must keep track of, document, and report without undue delay to the AI Office and, where appropriate, to national competent authorities, relevant information about **serious incidents** and possible corrective measures to address them. This is the GPAI analogue to Article 73") for high-risk AI deployers, but with different scope and a different reporting destination.

The Article 55(1)(c) clock

*Without undue delay* is the legal standard, not a specific number of days. The Code of Practice provides operational guidance: incident reports should reach the AI Office within days of awareness for capability-surprise incidents, and immediately for incidents involving actual real-world harm. The Article 73 clocks (2 / 10 / 15 days from awareness) are a reasonable benchmark even though they technically apply to high-risk AI deployers, not GPAI providers.

### Article 55(1)(d): Cybersecurity

Providers must ensure an adequate level of cybersecurity protection for the GPAI model with systemic risk and the physical infrastructure of the model. This includes protecting model weights, training data, and inference infrastructure against unauthorised access, exfiltration, or tampering. The Code of Practice translates this into specific controls: weight encryption, access controls, supply-chain security for compute providers, vulnerability disclosure programmes.

## The 10^25 FLOP threshold in context

10^25 FLOP is a big number that sounds abstract until you scale it. To train a model at the threshold takes **weeks of compute on tens of thousands of high-end GPUs**. GPT-3 (175B parameters, 2020) was trained at roughly 3.14 × 10^23 FLOP; GPT-4 is widely understood to exceed 10^25 FLOP. Claude 3 Opus, Gemini Ultra, and Mistral Large are similarly above the threshold by capability comparison.

The threshold is set deliberately to capture frontier-scale foundation models. The Commission can adjust it by delegated act under Article 51(3) as compute economics evolve. As training-efficiency improves, the same capability frontier can be reached at lower FLOP, so a lower threshold might apply in future delegated acts.

Threshold notification

Providers must notify the Commission within **two weeks** of foreseeing or reaching the 10^25 FLOP threshold (Article 52(1)). The notification triggers a 90-day window for the Commission to confirm or contest the classification. Reaching the threshold without notifying is itself an Article 101 violation.

## The GPAI Code of Practice

The General-Purpose AI Code of Practice is a voluntary tool published by the European Commission on **10 July 2025**. It was developed through a multi-stakeholder process involving GPAI providers, civil society organisations, academic researchers, and Member State authorities, coordinated by the AI Office. The Code's purpose is to provide operational guidance on complying