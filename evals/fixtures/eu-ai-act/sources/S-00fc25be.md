# EU AI Act Article 53 (General-Purpose AI Model Obligations)

Article 53 of the EU AI Act (Regulation (EU) 2024/1689) sets the baseline obligations that apply to every provider of a general-purpose AI (GPAI) model placed on the EU market -- a model trained on large amounts of data using self-supervision at scale, showing significant generality, and capable of competently performing a wide range o

[…]

# EU AI Act Article 53 (General-Purpose AI Model Obligations)
## Worked examples
n a commercial vendor.
* Is an instance

  A research institute takes an existing open-weight foundation model and substantially fine-tunes it (materially modifying its behavior or capabilities) before redistributing it under its own name. Substantial modification of a GPAI model can make the modifying institution a provider in its own right for the modified model, triggering the same Article 53 documentation and transparency duties for that version -- a distinction research units doing heavy fine-tuning or continued pretraining should not assume they are exempt from just because they started from someone else's open model.

Counter-examples

## Looks similar, but isn't

* Not an instance

  A university lab builds and deploys a narrow, single-purpose model -- for example, a classifier trained only to flag a specific type of image artifact in microscopy data -- with no broader general-task competence. This is not a general-purpose AI model under Article 3(63), so Article 53's GPAI-specific documentation and training-data-summary duties do not apply to it, even though the lab may still have other AI Act obligations if the tool is separately classified as high-risk under Article 6.

Editorial commentary

**Article 53 of the EU AI Act (Regulation (EU) 2024/1689) sets out what a provider of a general-purpose AI (GPAI) model must do before and after placing that model on the EU market — baseline obligations including documentation, training-data summaries, and copyright policy.** These requirements, set out in Chapter V, became applicable on 2 August 2025.

## The four baseline obligations

Every GPAI provider — commercial or academic, whether the model is released openly or kept proprietary — must, at minimum:

* **Technical documentation (Annex XI).** Keep current documentation of the model’s development and testing process and evaluation results, available on request to the EU AI Office and national competent authorities.
* **Downstream-provider documentation (Annex XII).** Provide information and documentation to any AI-system provider who integrates the GPAI model into their own system, sufficient for that downstream provider to understand the model’s capabilities and limitations.
* **Copyright-compliance policy.** Put in place a policy for complying with EU copyright law, in particular Directive (EU) 2019/790, including honoring rightsholders’ opt-outs from text-and-data-mining reserved under Article 4(3) of that Directive.
* **Training-data summary.** Draw up and publicly release a sufficiently detailed summary of the content used to train the model, using a template the AI Office provides.

## The open-source exemption — and its limits

Providers of GPAI models released under a genuinely free and open-source licence — one that allows access, use, modification, and redistribution, with model weights, architecture information, and usage information all made public — are exempt from the technical-documentation and downstream-documentation obligations above. This exemption does **not** extend to the copyright-policy or training-data-summary duties, both of which apply regardless of licensing model, and it does not apply at all to a GPAI model classified as carrying systemic risk.

## Heightened obligations for models with systemic risk

Article 51 creates a rebuttable presumption that a GPAI model carries **systemic risk** when the cumulative compute used to train it exceeds **10^25 floating-point operations (FLOPs)**, or when the Commission designates it as such based on high-impact capability criteria in Annex XIII. Providers of a systemic-risk GPAI model face additional duties under Article 55 on top of the Article 53 baseline: state-of-the-art model evaluation including adversarial testing, systemic-risk assessment and mitigation, serious-incident reporting to the AI Office, and adequate cybersecurity protection for the model and its infrastructure. As of this writing, the 10^25 FLOP threshold is a presumption, not an absolute line — the Commission retains authority to designate a model as systemic-risk on capability grounds even below that compute level, and providers can rebut the presumption with evidence the model does not in fact pose systemic risks.

## Why this matters for research institutions

Article 53 does not exempt universities, national labs, or nonprofit research consortia as a category. A research group that pretrains its own foundation model, or substantially fine-tunes and redistributes someone else’s, can itself become a GPAI “provider” for AI Act purposes — with the same documentation, training-data-summary, and copyright-policy duties as a commercial AI vendor. This is a materially different question from the research-specific carve-outs elsewhere in the Act: Article 2(6) and 2(8) exempt AI systems developed and used *purely for scientific research* from most of the Act, but a GPAI model a research institution releases or makes available beyond that narrow purely-research context does not automatically inherit that exemption. Institutions developing or fine-tuning large models should treat model-release decisions — open-weight or not, internal-only or public — as a point where Article 53 obligations may attach, and should not assume nonprofit or academic status is itself a defense.

## A fast-moving regulatory picture

The EU’s 2026 “Digital Omnibus on AI” simplification package, politically agreed