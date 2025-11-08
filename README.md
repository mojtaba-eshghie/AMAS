## ACO: Adversarial Co-Evolutory LLM Agentic Systems

The problem is when multiple LLM agents work in parallel and they have their evolution in parallel but not in an agentic system since they are adversaries (as agentic systems as I know them typically are collaboratory). For instance, one learns how to generate exploits and the other is trained on ground truth to avoid them or defend against them. I want to put them together in a GAN/RL regime so they can talk to eachother and learn to co-evolve. We have concrete case studies for software engineering. 



RQs: In what scenarios does this system make sense instead of individually evolving agents?
RQs: What hierarchical system is best for these?


Use case for smart contracts: 
Agent: Vulnerability injector
Agent: Exploit generator
Agent: Vulnerability detector
Agent: Patch generator
Agent: Arbiter/… (probably to not let the evolution go in weird direction/not fall into local minima like one adding dead code the other fixing it and thus learning something useless)

We can analyze and evaluate this use-case end-to-end.
