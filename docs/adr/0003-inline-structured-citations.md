# Inline structured citations over post-hoc NLI attribution

The generation LLM outputs Answers as structured JSON (`[{sentence, evidence_ids}]`) with citations inline, rather than generating free text and then running a separate NLI model to attribute sentences to evidence. We chose inline structured output because (a) it eliminates a second model call, cutting latency by 30-50%, (b) structured output guarantees clean parseable traces for the UI, and (c) the citation accuracy of Gemini 2.5 Pro is high enough for a demo. The trade-off is that the LLM may hallucinate citations — it can claim evidence supports a sentence when it doesn't. A post-hoc NLI verifier would catch this, but the complexity isn't warranted for a demo.

**Considered options**: Post-hoc NLI attribution (more rigorous but adds latency, a second model, and a more complex pipeline), hybrid inline+NLI (gold standard but overengineered for a demo).
