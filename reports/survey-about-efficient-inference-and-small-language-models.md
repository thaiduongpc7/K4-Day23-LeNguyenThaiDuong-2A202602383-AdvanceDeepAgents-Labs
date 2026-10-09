# Efficient inference and small language models

## TL;DR

Small language models (SLMs) are becoming a practical path to efficient inference, especially when paired with local deployment, routing, and training-time efficiency techniques. H2O-Danube3 illustrates that SLMs can achieve high benchmark performance while supporting efficient local inference on smartphones [1][2]. Recent systems extend this idea with collaborative edge–cloud inference, where queries are routed between local SLMs and a cloud foundation model using uncertainty and safety signals [3]. Serving research is also moving from query-level routing toward token-level routing, which can improve the cost–quality Pareto frontier but introduces systems challenges such as step desynchronization and frequent batch admission [4]. Efficient SLM development further depends on faster fine-tuning methods such as RAPID, which reduces training time through batched inference and off-policy updates with group advantage estimation [5].

## Background

Efficient inference addresses the cost, latency, and deployment constraints of running language models in real applications. The SLM direction targets these constraints by reducing model scale while retaining useful capability. H2O-Danube3 is an example of this trend: it is a series of SLMs reported to perform well across benchmarks and to support efficient local inference on smartphones [1][2]. This matters because local inference can reduce dependence on remote serving infrastructure and make language-model capabilities more accessible on edge devices [1].

The inference-efficiency problem is not only about model size. It also includes deciding where computation should happen, which model should answer a request, and how serving systems batch and schedule work. SWARM-LLM frames deployment as collaborative inference: local SLMs handle some requests, while a cloud foundation model is invoked based on uncertainty estimates and safety signals [3]. TokenRouter highlights a finer-grained version of the same broad idea: instead of routing at the session or query level, routing can happen at the token level, with the goal of improving the cost–quality Pareto frontier of LLM serving [4].

A related issue is the cost of improving SLMs themselves. RAPID targets reinforcement-learning fine-tuning for SLMs and reduces training time by combining batched inference, off-policy updates, and group advantage estimation [5]. Although training efficiency is distinct from inference efficiency, it affects how quickly small models can be adapted for specialized efficient deployment.

## Compact models for local inference

The simplest efficient-inference strategy is to use a smaller model that can run near the user. H2O-Danube3 demonstrates this approach by presenting a family of SLMs that achieve high performance across benchmarks while being efficient for local inference on smartphones [1][2]. This suggests a deployment pattern in which SLMs are not merely fallback models but primary inference engines for constrained environments [1].

Local smartphone inference is especially important because it imposes practical limits on compute, memory, and energy. The source notes do not provide architectural details or quantitative benchmark results, but they establish that H2O-Danube3 was designed and evaluated as a high-performing SLM series suitable for such local use [1][2]. For a survey of efficient inference, this places compact model design at the foundation: without capable SLMs, higher-level routing and orchestration systems have fewer useful local options.

A key implication is that benchmark performance and deployment efficiency must be evaluated together. H2O-Danube3 is notable because the reported contribution spans both benchmark performance and smartphone inference efficiency, rather than focusing only on one dimension [1][2]. This reflects a broader shift from model-centric evaluation toward deployment-aware evaluation.

## Collaborative edge–cloud inference

A second theme is adaptive collaboration between edge SLMs and larger cloud models. SWARM-LLM proposes efficient edge deployment by dynamically routing queries between local SLMs and a cloud foundation model [3]. Its routing decisions use uncertainty estimates and safety signals, which indicates that efficiency is balanced against answer reliability and safety-sensitive behavior [3].

This design recognizes that local SLMs may be sufficient for many queries, while other queries require escalation. The source notes do not specify the exact uncertainty method or safety classifier, but they make clear that SWARM-LLM treats routing as a dynamic decision rather than a fixed deployment choice [3]. This is important for efficient inference because it avoids sending every request to a cloud model while still preserving an escalation path.

Collaborative inference also reframes SLMs as components in a larger serving ecosystem. Instead of asking whether an SLM can replace a larger model entirely, SWARM-LLM asks when an SLM can answer locally and when cloud inference is warranted [3]. That makes SLM deployment more flexible: efficiency gains can come from selective use, not only from universal substitution.

## Routing and serving granularity

Routing is also evolving inside serving systems. TokenRouter addresses token-level LLM routing, where inference work is distributed across different models at a finer granularity than session-level or query-level routing [4]. The motivation is to advance the cost–quality Pareto frontier of LLM serving, and recent algorithmic work is described as showing substantial efficiency and quality gains from token-level routing [4].

However, token-level routing creates serving challenges that differ from conventional single-model inference. TokenRouter notes that current systems are built on single-LLM assumptions and can suffer from severe step desynchronization and frequent batch admission under token-level routed inference [4]. These issues matter because batching and synchronization are central to high-throughput inference serving; routing at token granularity can disrupt those assumptions [4].

This theme complements edge–cloud routing. SWARM-LLM focuses on dynamic query routing between local SLMs and a cloud foundation model using uncertainty and safety signals [3], while TokenRouter focuses on token-level routing across models during serving [4]. Together, they show that efficient inference is becoming a multi-level routing problem: decisions may occur across devices, across models, and across decoding steps.

## Trends and open problems

Several trends stand out. First, capable SLMs are becoming plausible targets for local inference, as illustrated by H2O-Danube3’s combination of benchmark performance and smartphone-oriented efficiency [1][2]. Second, deployment is moving toward adaptive hybrid systems, where local SLMs and cloud foundation models cooperate through uncertainty- and safety-aware routing [3]. Third, routing is becoming finer-grained: TokenRouter identifies token-level routing as a way to improve cost–quality tradeoffs, while also exposing serving-system bottlenecks such as step desynchronization and frequent batch admission [4]. Fourth, efficient training and fine-tuning remain part of the pipeline, with RAPID reducing SLM fine-tuning time through batched inference and off-policy reinforcement-learning updates with group advantage estimation [5].

Open problems follow directly from these directions. One is evaluation: SLMs for efficient inference need to be assessed not only on benchmark performance but also on local deployment behavior, as in the smartphone-inference framing of H2O-Danube3 [1][2]. Another is routing reliability: SWARM-LLM depends on uncertainty estimates and safety signals, so practical systems need robust criteria for deciding when to stay local and when to escalate to a cloud foundation model [3]. A third is serving architecture: token-level routing promises efficiency and quality gains, but existing systems face desynchronization and batching challenges under this workload [4]. Finally, faster SLM adaptation remains important, because methods such as RAPID suggest that reducing fine-tuning time can make specialized efficient models easier to produce and update [5].

## References
[1] H2O-Danube3 Technical Report. hf-search. https://huggingface.co/papers/2407.09276 (2024-07-12)
[2] H2O-Danube3 Technical Report. arxiv. https://arxiv.org/abs/2407.09276 (2024-07-12)
[3] SWARM-LLM: Collaborative Inference for Edge-based Small Language Models. hf-search. https://huggingface.co/papers/2606.14711 (2026-04-22)
[4] TokenRouter: Efficient Serving System for Token-Level LLM Routing. hf-daily. https://huggingface.co/papers/2610.12242 (2026-10-08)
[5] RAPID: An Efficient Reinforcement Learning Algorithm for Small Language Models. hf-search. https://huggingface.co/papers/2510.03515 (2025-10-03)
