# EU AI Act GPAI Systemic Risk: Obligations Under Articles 51–55

The EU AI Act creates a two-tier framework for General Purpose AI (GPAI) models. All GPAI providers face baseline obligations under Art. 50–53. But providers whose models meet the systemic risk threshold face an additional, significantly more demanding set of requirements under Art. 51–55.

If you are building, fine-tuning, or distributing a GPAI model in or into the EU, understanding whether you cross the systemic risk threshold — and what it triggers — is now operational.

## What Qualifies as a GPAI Model with Systemic Risk

Art. 51 defines the classification trigger. A GPAI model is presumed to carry systemic risk if it was trained with a computational capacity exceeding **10^25 floating point operations (FLOPs)**.

This threshold is not a hard ceiling that exempts everything below it. Art. 51(2) allows the European AI Office to designate additional models as having systemic risk based on:

* The model's reach and number of users across the EU
* Economic or societal dependence on the model
* Multimodal capabilities (text, image, audio, code)
* Access to exceptional resources, information, or capabilities
* Potential for significant negative impact on public health, safety, security, or fundamental rights

In practice, this means frontier models — GPT-4 class, Gemini Ultra class, large Claude models — fall within systemic risk scope. Many mid-tier commercial models do not, but the AI Office retains discretion to classify upward based on impact, not just compute.

## Baseline GPAI Obligations (Art. 50–53)

Before getting to systemic risk obligations, confirm whether baseline GPAI obligations apply. Art. 50 applies to providers who place GPAI models on the EU market, whether via API, direct deployment, or release under open source licenses.

Baseline obligations include:

* Drawing up and keeping up to date technical documentation (Art. 11 equivalent, Art. 53(1)(a))
* Providing information and documentation to downstream providers who build on the model
* Complying with copyright transparency requirements (EU Copyright Directive Art. 4(3) disclosure)
* Publishing summaries of training data used to train the model

These baseline obligations are binding regardless of compute thresholds. The systemic risk tier adds to them.

## Systemic Risk Obligations Under Art. 52–55

### Adversarial Testing and Red Teaming (Art. 55(1)(a))

Providers of systemic risk GPAI models must perform model evaluations, including **adversarial testing**, to identify and mitigate systemic risks before and after market release.

Adversarial testing under Art. 55 is not optional or informal. The AI Office publishes guidelines specifying what adequate testing looks like. Current guidance from the AI Office (aligned with NIST AI RMF) expects:

* Testing for catastrophic risk capabilities: mass casualty weapon assistance, cyberattack facilitation, undermining oversight mechanisms
* Testing for loss of control risks: deceptive alignment, goal misgeneralization
* Red team exercises with external evaluators for frontier models
* Structured documentation of test protocols, findings, and mitigations

Providers can conduct internal red teaming or engage third-party evaluators. For models above the compute threshold, the AI Office may mandate specific testing protocols.

### Incident Reporting (Art. 55(1)(b))

Systemic risk GPAI providers must report **serious incidents** to the AI Office without undue delay. Art. 3(49) defines serious incidents as actual or reasonably foreseeable adverse effects on:

* Public health or safety
* Critical infrastructure
* Democratic processes
* Property (at significant scale)
* Fundamental rights

This creates an obligation analogous to breach notification under GDPR Art. 33 — but scoped to model-level incidents rather than individual data breaches. For multi-modal frontier models deployed at scale, serious incidents could include:

* Discovery that the model provides detailed synthesis routes for chemical or biological agents
* Model output that enables large-scale coordinated fraud or disinformation
* Evidence that the model is being systematically exploited for cyberattack assistance

The notification obligation goes to the AI Office directly (not national authorities), and affected downstream providers and deployers should also be notified.

### Cybersecurity Protection (Art. 55(1)(c))

Systemic risk GPAI providers must implement appropriate technical and organizational measures to protect against model theft, unauthorized access, and adversarial manipulation of the model itself.

This goes beyond standard application security. It includes:

* **Model weight security**: protecting trained model weights from extraction, exfiltration, or unauthorized copying. This requires strict access controls on inference infrastructure and model storage.
* **Training pipeline security**: protecting training data pipelines and checkpoints from poisoning attacks
* **Inference monitoring**: detecting adversarial prompting attempts, model extraction via API, or large-scale probing of capabilities
* **Insider threat controls**: access controls, audit logs, and separation of duties for staff with access to model weights or training infrastructure

For cloud-hosted models, the infrastructure security requirements under AI Act Art. 55 align substantially with GDPR Art. 32 security obligations — but extend to model-level assets, not just personal data.

For more on AI infrastructure security, see AI Hosting Security: Infrastructure Obligations Under the EU AI Act.

### Ongoing Risk Assessment and Documentation (Art. 55(1)(d))

Providers must conduct **ongoing** risk assessments — not a one-time pre-deployment exercise. This mirrors the continuous nature of high-risk AI system risk management under Art. 9, applied to GPAI at the model level.

Risk assessments must cover:

* Foreseeable misuses and their potential for systemic harm
* Capability evolution as the model is fine-tuned or updated
* New threat vectors identified through incident reports or external research
* Interaction effects with downstream use cases

Documentation of these assessments must be maintained and made available to the AI Office on request. The AI Office can conduct audits of systemic risk providers at any time.

### Cooperation with the AI Office (Art. 52–54)

Systemic risk GPAI providers must:

* Register with the AI Office (via the EU database established under Art. 71)
* Provide the AI Office with technical documentation on request
* Cooperate with evaluations, investigations, and testing mandated by the AI Office
* Implement corrective measures required by the AI Office

Art. 54 establishes that the AI Office can conduct evaluations of systemic risk GPAI models on its own initiative or at the request of a qualified alert mechanism (scientific community, civil society, national authorities). These evaluations can include API-level access to the model.

## Open Source Systemic Risk GPAI: Partial Exemptions

Art. 53(2) provides a partial exemption for open source GPAI models: providers who release model weights publicly are exempted from some of the Art. 53 documentation and transparency obligations.

However, this exemption **does not apply** to systemic risk models. Art. 53(2) explicitly states that the exemption does not cover providers of GPAI models with systemic risk. If your open source model crosses the 10^25 FLOP threshold, you retain the full systemic risk obligation set.

This is a deliberate policy choice — the argument that open source models cannot be controlled post-release does not eliminate the provider's obligation to conduct adversarial testing, report incidents, and protect the model weights prior to release.

## Codes of Practice

Art. 56 creates a mechanism for the AI Office to develop **codes of practice** that systemic risk GPAI providers can adhere to as a means of demonstrating compliance with Art. 55 obligations. The AI Office published a draft code of practice in 2025, with major GPAI providers involved in its development.

Compliance with an approved code of practice creates a presumption of conformity with the corresponding Art. 55 obligations. This is practically significant — it provides a defined compliance path rather than leaving providers to determine independently what "adequate" adversarial testing or incident reporting means.

For providers above the compute threshold, engaging with the code of practice process is the fastest path to auditable compliance documentation.

## Timeline and Enforcement

The GPAI obligations under Art. 50–55 applied from **August 2025** — 12 months after the AI Act's entry into force. Unlike the high-risk AI system obligations (which phase in by use case through 2027), GPAI systemic risk obligations are already in force.

The AI Office holds primary enforcement authority for GPAI. National market surveillance authorities handle enforcement for high-risk AI systems deployed in their territory. For cross-border GPAI incidents, the AI Office coordinates with national authorities.

Maximum fines for GPAI violations: up to €15 million or 3% of global annual turnover, whichever is higher.

## Compliance Checklist

* Determine whether your GPAI model exceeds 10^25 FLOPs training compute (or assess non-compute risk indicators per Art. 51(2))
* If systemic risk applies: register with the AI Office via the EU GPAI database
* Conduct and document pre-deployment adversarial testing following AI Office guidelines
* Implement model weight security, training pipeline security, and inference monitoring
* Establish incident reporting procedures with defined triggers and notification timelines
* Build ongoing risk assessment cadence into your model lifecycle (not just pre-deployment)
* Review the AI Office codes of practice and assess adherence as your compliance path
* Prepare technical documentation for AI Office inspection at any time
* Ensure downstream providers (who build on your model) receive sufficient documentation to meet their own obligations

## ComplyJudge

ComplyJudge tracks GPAI model compliance obligations, helping providers document adversarial testing pr