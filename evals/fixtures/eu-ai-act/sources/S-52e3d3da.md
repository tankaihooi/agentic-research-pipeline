# Generally Speaking: Does Your Company Have EU AI Act Compliance Obligations as a General-Purpose AI Model Provider?

### A Practical Guide for Developers and Deployers

Advisory

By

On July 18, 2025, the European Commission released its guidelines on the obligations for providers of general-purpose AI (GPAI) models under the European Union’s AI Act. These GPAI Guidelines arrive just ahead of the August 2, 2025 effective date for the AI Act’s GPAI requirements and are accompanied by a general FAQ page addressing some of the key points regarding the GPAI-related provisions of the AI Act.

## Why the GPAI Guidelines Matter

Whether your company is building models from scratch, fine-tuning other parties’ models for your own use, or embedding third-party models into commercial products, the GPAI Guidelines answer some of the open questions about the AI Act’s treatment of GPAI models — beginning with how to define them. The GPAI Guidelines answers are not binding because only the Court of Justice of the European Union can interpret the AI Act authoritatively. However, the Commission’s answers do matter because its Artificial Intelligence Office (AI Office) is the sole enforcer of the AI Act’s obligations governing GPAI model providers.

## What Makes a Model “General-Purpose”?

The AI Act defines a GPAI model as one that “displays significant generality and is capable of competently performing a wide range of distinct tasks.” The Commission will presume a model with more than 10²³ floating-point operations (FLOP) of training compute that can generate language (text or audio), text-to-image, or text-to-video outputs to be a GPAI model.

 However, this presumption is not a bright-line rule. The Commission provides examples of models that exceed the compute threshold but are not GPAI models because they are limited to a narrow set of tasks (e.g., transcribing speech or generating music). Conversely, a model that falls below the 10²³ FLOP threshold may still qualify as GPAI if it demonstrates sufficient generality.

 Unfortunately, the examples in the GPAI Guidelines do not clearly define the breadth required for a model to display sufficient generality to be GPAI. Providers in these gray zones will have to decide whether to engage with the Commission’s AI Office to obtain specific guidance.

 The AI Act classifies some GPAI models as having systemic risk because they are particularly powerful. Providers of GPAI models with systemic risks have additional obligations beyond those of other GPAI model providers. We do not address these additional obligations in this Advisory.

## The AI Act May Apply Even if Your Company Is Not in the EU

The AI Act has broad extraterritorial reach. It applies to, among other actors, providers and deployers of GPAI models and AI systems located within the EU, providers outside the EU that place GPAI models or AI systems on the market in the EU, providers outside the EU that put AI systems into service in the EU, and providers and deployers of AI systems outside the EU when the system’s output is used inside the EU.

 Under the GPAI Guidelines, your company must comply as a GPAI model provider if:

* It places a GPAI model on the EU market in any of a number of ways, such as via application programming interface (API), download, or cloud service.
* It integrates its own GPAI model into a chatbot, mobile application, or other system that your company makes available in the EU.
* It provides a model to someone else who does either of the above — unless your company has clearly and unequivocally prohibited distribution and use in the EU.

A downstream actor that disregards an upstream GPAI model provider’s prohibition against placing an AI system on the EU market or putting such a system into service in the EU will be treated as the model provider and must assume the model provider’s obligations under the AI Act.

## Modifying a Model? Your Company Might Be a Provider Too

If your company modifies a GPAI model — such as by fine-tuning it — the GPAI Guidelines state that your company will become a provider under the AI Act if the modifications significantly affect the model’s generality, capabilities, or risk profile. An “indicative criterion” for when a modification has a significant effect is whether it required more than one-third of the original model’s training compute or, if the modifier does not know the original training compute, more than 3⅓ x 1022 FLOP.

 If the modification does have a significant effect, the GPAI Guidelines provide that your company will step into the shoes of the original provider for purposes of AI Act compliance — but only with respect to the modification. If your company is established or located outside the EU, it will have to appoint an authorized representative within the EU.

## What Your Company Must Do as a GPAI Model Provider

If your company qualifies as a GPAI model provider under the AI Act, your company must comply with the four obligations in Article 53 of the AI Act (unless the model qualifies for the open-source exemption from the first two):

1. Technical Documentation: GPAI model providers must prepare and maintain documentation describing the model’s training and testing processes and evaluation results.

2. Information for Downstream Providers: GPAI model providers must provide sufficient information to enable downstream providers to comply with their own AI Act obligations. This includes documentation on model capabilities, limitations, and integration requirements.

3. Copyright Compliance Policy: GPAI model providers must adopt a policy to ensure compliance with EU copyright law, including respect for opt-outs from the text and data mining otherwise permitted under Article 4(3) of Directive (EU) 2019/790 on copyright and related rights in the Digital Single Market (the CDSM Directive).

4. Training Data Summary: GPAI model providers must publish a sufficiently detailed summary of the content used to train the model on a template from the AI Office.

These obligations apply throughout the model’s lifecycle. The Commission considers the lifecycle to begin with the large pre-training run and continue through all subsequent development, deployment, and use.

## Open-Source, Open-Weight Models May Be Partially Exempt

The AI Act offers limited exemptions for GPAI models released under a free and open-source license — but only if:

* The model is not classified as having systemic risk.
* The license allows access, use, modification, and redistribution.
* The model’s weights, architecture, and usage information are publicly available.
* The provider does not monetize the model.

Redistribution restrictions that require attribution and distribution of the model or derivatives on “the same or comparable terms” will not prevent a model from qualifying for the open-source, open-weight exemption. The Commission also maintains that licensors may impose “specific, safety-oriented terms that reasonably restrict usage in applications or domains where such use would pose a significant risk to public safety, security, or fundamental rights” if the terms are “proportionate” and “based on objective non-discriminatory criteria.”

 The Commission believes that the monetization prohibition extends to indirect monetization strategies such as payment for certain usage; intrinsically necessary accompanying services; mandatory support, training, or maintenance services; or access to the platform or website hosting the model. The Commission also considers subjecting users to paid advertisements to access the hosting platform or website to be a form of monetization. The monetization prohibition does not apply to transactions between microenterprises.

 Even when the open-source, open-weight exemption applies, the model provider must still comply with the copyright policy and training data summary obligations.

## The Code of Practice: One Path to Compliance

Pending the development of harmonized standards, the Commission has published a GPAI Code of Practice as an adequate voluntary tool for providers of GPAI models to demonstrate compliance with the AI Act. The Code of Practice includes chapters on:

* Transparency measures, including a model documentation form
* Copyright compliance
* Safety and security practices (this chapter applies only to GPAI models with systemic risk)

A GPAI model provider that adheres to the Code of Practice will benefit from a presumption of compliance with its AI Act obligations and may face fewer information requests and enforcement actions from the AI Office, even though they are not required to comply with the Code of Practice until August 2, 2026. Model providers that choose to adhere only to certain chapters will receive the presumption of compliance only for those chapters. Model providers that choose not to adhere to the Code of Practice (or to particular chapters) will have to demonstrate their compliance to the AI Office via other means. Until the end of the informal moratorium to comply with the Code of Practice, the AI Office will adopt a flexible approach with signatories and will engage with them in a collaborative manner, with a view to facilitating their compliance with the provisions of the AI Act.

To guide prospective signatories of the Code of Practice, the Commission has published two general FAQ documents to give GPAI model providers additional information about the Code of Practice and assist them with queries relating to the signing of the Code of Practice, respectively.

## Interplay Between GPAI Models and Copyright Law

The Code’s thematic chapter on copyright outlines the obligations under Article 53(1)(c) of the AI Act, which requires providers of GPAI models to implement a policy ensuring compliance with EU copyright law, with a particular focus on respecting the rights of copyright holder

[…]

# Generally Speaking: Does Your Company Have EU AI Act Compliance Obligations as a General-Purpose AI Model Provider?
## Interplay Between GPAI Models and Copyright Law
how the associated content, domains, or URLs are indexed in their search engines.

**4. To mitigate the risk of copyright-infringing outputs**
 To reduce the risk of downstream AI systems producing outputs that infringe copyright, signatories commit to:

* Implementing appropriate and proportionate technical safeguards to prevent their models from generating outputs that unlawfully reproduce copyright-protected content used for their training.
* Including clear prohibitions against copyright-infringing uses in their terms of use or related documentation
  + For models released under free and open-source licenses, users should be clearly informed that infringing uses are not permitted.

These commitments apply whether the model is used internally or provided to another party under a contract.

 **5. To designate a point of contact and enable the lodging of complaints**
 Signatories commit to designating a clear point of contact for rightsholders and communicating this information in a way that makes it easily accessible to affected parties.

 Moreover, signatories are to establish a mechanism for submitting detailed complaints concerning their non-compliance with the measure in this chapter of the Code of Practice. The mechanism must facilitate the electronic submission of complaints, and signatories must commit to handling the complaints fairly and promptly.

 These commitments do not affect existing legal remedies available to enforce copyright.

## The Compliance Timeline

* August 2, 2025: The AI Act obligations for GPAI model providers take effect for models not already on the EU market.
* August 2, 2026: The Commission may begin enforcing AI Act obligations against GPAI model providers.
* August 2, 2027: Providers of GPAI models already on the EU market as of August 2, 2025 must bring them into compliance.

The Commission says that it will not require providers to retrain or “unlearn” GPAI models on the EU market by August 2, 2025 “where it is not possible to do this for actions performed in the past, where some of the information about the training data is not available, or where its retrieval would cause the provider disproportionate burden.” If your company takes advantage of this leniency, it must clearly disclose and justify the exceptions in its copyright policy and training data summary.

 The Commission is also signaling flexibility for GPAI models that will be placed on the EU market after August 2, 2025 if their training has occurred, is in progress, or is being planned as of that date. Providers that wish to put such models on the EU market, even though they anticipate difficulties in complying with their AI Act obligations, “should proactively inform the AI Office regarding how and when they will take the necessary steps to comply with their obligations.” Engagement with the AI Office may yield agreement on an acceptable compliance deadline — at least from the Commission’s perspective. If the question comes before a court in an appropriate legal action (e.g., a product liability or other extra-contractual liability (or tort) claim), the court might find otherwise.

## Final Thoughts

The Commission’s GPAI Guidelines and the Code of Practice add some clarity to the AI Act’s obligations for GPAI model providers — especially on the crucial question of when a deployer