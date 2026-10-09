# Survey: Video and Multimodal Generation

## TL;DR

Recent work in video and multimodal generation is moving from offline text-to-video synthesis toward interactive, controllable, and task-grounded systems. Key directions include proactive safety for text-and-image-to-video generation, real-time diffusion for multimodal interaction, agentic visual workflows, robot world models for action-faithful video prediction, and systems techniques for efficient model serving. The field’s central tension is balancing quality, latency, controllability, physical fidelity, and safety.

## Background

Video generation extends generative modeling from static images to temporally coherent sequences, while multimodal generation conditions synthesis on combinations of text, images, actions, visual controls, or other signals. Recent source notes emphasize diffusion-based approaches for real-time multimodal video generation [1], unified multimodal video diffusion frameworks [2], and video prediction models for robotics [3]. Compared with image generation, video generation adds temporal consistency and interaction requirements, especially when systems must respond in real time or follow embodied actions.

The scope of “multimodal” is also widening. ConceptGuard targets text-and-image-to-video generation and treats safety as a multimodal semantic detection problem [4]. LiveTalk focuses on real-time multimodal interactive video diffusion using improved on-policy distillation, multimodal conditioning, and optimized scheduling [1]. LynnReal-Omni frames video generation as part of agentic visual workflows, integrating visual controls, high-fidelity generation, and real-time acceleration [2]. DreamTrue moves toward world modeling, using multi-view and cross-embodiment robot data for action-faithful and physically plausible video prediction [3].

## Safety and semantic control

Safety has become a first-class concern as video generators accept richer inputs and produce more realistic outputs. ConceptGuard proposes a unified safeguard framework for text-and-image-to-video generation that proactively detects and mitigates unsafe semantics before or during generation [4]. Its source summary identifies two core mechanisms: contrastive detection and semantic suppression [4]. This framing is important because unsafe content in multimodal video generation may arise not only from explicit text prompts but also from image conditions or their combination.

ConceptGuard is also listed in an arXiv source with the same title and summary, reinforcing that the framework is specifically designed for proactive safety in multimodal video generation rather than only post-hoc filtering [5]. The repeated emphasis on unsafe “semantics” suggests a shift from surface-level moderation toward concept-level risk detection and mitigation [4][5]. In practical systems, such mechanisms may need to coexist with controllability features, because suppressing unsafe semantics without over-constraining benign creative intent is a core challenge implied by proactive mitigation.

## Real-time and agentic multimodal generation

A second major theme is latency reduction for interactive use. LiveTalk targets real-time multimodal interactive video diffusion and uses improved on-policy distillation to reduce inference latency while maintaining quality [1]. Its approach combines multimodal conditioning with optimized scheduling, indicating that speedups are not treated as a single-model compression problem alone but as a broader generation pipeline issue [1]. This matters for interactive systems, where response time can determine usability.

LynnReal-Omni extends this trajectory toward native multimodal video generation for agentic visual workflows [2]. It is described as a unified multimodal video diffusion framework that integrates agentic visual controls, high-fidelity generation, and real-time acceleration [2]. The “agentic” framing points to systems in which generation is not merely prompted once, but directed through controls that can support visual task execution or iterative workflow automation.

Although TokenRouter is not a video-generation paper, it addresses efficient serving through token-level LLM routing and is relevant to multimodal generation systems that rely on language-model components for prompting, planning, routing, or control [6]. The source notes state that token-level routing can improve the cost-quality Pareto frontier of LLM serving, but serving such inference creates challenges including step desynchronization and frequent batch admission under assumptions inherited from single-LLM systems [6]. This suggests that multimodal generation pipelines may increasingly depend not only on generative model architecture but also on serving systems that coordinate heterogeneous model components efficiently.

## World models and embodied video prediction

Video generation is also being applied as a predictive model of physical interaction. DreamTrue is presented as a multi-view, cross-embodiment robot world model for action-faithful and physically plausible video prediction [3]. Unlike open-ended creative video generation, this setting requires generated futures to respect robot actions and physical consequences.

The source notes identify two obstacles for training such models on existing robot datasets: imprecise calibration can impair action following, and limited coverage of unsuccessful interactions can bias predictions toward successful outcomes [3]. DreamTrue addresses action following by rendering action trajectories into image-space conditions and introducing offline geometric calibration to align these conditions with target videos [3]. It also broadens interaction coverage through counterfactual post-training, according to the paper title and summary [3]. This highlights an emerging distinction between visually plausible video and action-faithful video: for robotics, a model must not only look realistic but also predict failures, contact outcomes, and embodiment-specific consequences.

## Trends and open problems

Several trends emerge across the surveyed works. First, video generation is becoming more interactive: LiveTalk targets real-time multimodal interaction [1], while LynnReal-Omni combines agentic controls with real-time acceleration [2]. Second, safety is shifting upstream into generation-time risk detection and mitigation, as shown by ConceptGuard’s proactive contrastive detection and semantic suppression framework [4][5]. Third, video models are expanding from media synthesis into world modeling, where DreamTrue emphasizes action faithfulness, calibration, and physically plausible prediction [3]. Fourth, efficient serving is becoming a systems bottleneck, with TokenRouter showing that fine-grained routing can improve cost-quality tradeoffs while introducing new scheduling challenges [6].

Open problems include building safeguards that understand multimodal context without suppressing benign content, achieving real-time generation without visible quality loss, integrating agentic controls while preserving temporal coherence, and evaluating whether generated videos are physically and action-conditionally faithful rather than merely realistic. Another open systems problem is how to serve complex multimodal pipelines efficiently when they combine diffusion models, language models, routing mechanisms, and control modules under tight latency constraints [1][2][6].

## References
[1] LiveTalk: Real-Time Multimodal Interactive Video Diffusion via Improved On-Policy Distillation. hf-search. https://huggingface.co/papers/2512.23576 (2025-12-29)
[2] LynnReal-Omni: Native multi-modal Video Generation for Agentic Visual Workflows. hf-search. https://huggingface.co/papers/2609.15863 (2026-09-14)
[3] DreamTrue: Action-Faithful Robot World Model with Counterfactual Post-Training. hf-daily. https://huggingface.co/papers/2610.12468 (2026-10-08)
[4] ConceptGuard: Proactive Safety in Text-and-Image-to-Video Generation through Multimodal Risk Detection. hf-search. https://huggingface.co/papers/2511.18780 (2025-11-24)
[5] ConceptGuard: Proactive Safety in Text-and-Image-to-Video Generation through Multimodal Risk Detection. arxiv. https://arxiv.org/abs/2511.18780 (2025-11-24)
[6] TokenRouter: Efficient Serving System for Token-Level LLM Routing. hf-daily. https://huggingface.co/papers/2610.12242 (2026-10-08)
