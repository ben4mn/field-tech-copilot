# Model and runtime decision

Last reviewed: 2026-08-31. Local-model tooling changes quickly; pin exact runtime versions and model digests for a field release.

## Decision for the first benchmark

Use Ollama as the first Windows-native model runtime and keep the provider boundary small. Keep Josh's existing Qwen3 8B setup as the control. A better model is one that improves the field-specific gold cases enough to justify its latency, memory, heat, battery, and installation cost—not one that wins an unrelated leaderboard.

Ollama is the first integration because it provides a local API, Windows support, embeddings, and JSON-schema-constrained structured output. `llama.cpp` remains the likely tuning/deployment path when direct control over GGUF quantization, CUDA/Vulkan/SYCL backends, and CPU/GPU hybrid offload becomes important. Its `llama-server` exposes OpenAI-compatible chat and embeddings APIs plus schema-constrained output.

Official references:

- [Ollama on Windows](https://docs.ollama.com/windows)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama embeddings](https://docs.ollama.com/capabilities/embeddings)
- [Ollama context length and memory](https://docs.ollama.com/context-length)
- [llama.cpp capabilities and backends](https://github.com/ggml-org/llama.cpp)
- [`llama-server` documentation](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## Candidate matrix

Test in this order; do not purchase hardware first.

| Profile | Why test it | Expected constraint |
| --- | --- | --- |
| Current Qwen3 8B | Known sub-20-second control and no migration cost | Establish actual quality, quantization, and memory baseline |
| Qwen3.5 9B Q4 | Newer small reasoning/tool/vision candidate; Ollama artifact is about 6.6 GB | Official card's long-context guidance may be unrealistic on this laptop; test 4K/8K/16K |
| Qwen3 14B Q4 | Larger text reasoning candidate; Ollama artifact is about 9.3 GB | Context/KV overhead must still fit; compare full versus partial GPU offload |
| gpt-oss 20B | Mixture-of-experts reasoning model with structured outputs and configurable reasoning | Ollama artifact is about 14 GB and official guidance says roughly 16 GB memory; a 12 GB GPU implies hybrid/system-memory use |
| Phi-4-mini | Small fast fallback for degraded/battery mode | Quality may be inadequate for difficult diagnostic branching |
| Qwen3.8 27B Q4 | Stretch quality/capacity experiment | Roughly 18 GB artifact; system-RAM/hybrid run, slower and relatively new |

Primary model references:

- [Qwen3.5 9B model card](https://huggingface.co/Qwen/Qwen3.5-9B) and [Ollama package](https://ollama.com/library/qwen3.5)
- [Qwen3 Ollama packages](https://ollama.com/library/qwen3)
- [OpenAI gpt-oss 20B model](https://developers.openai.com/api/docs/models/gpt-oss-20b) and [Ollama package](https://ollama.com/library/gpt-oss)
- [Microsoft Phi-4-mini model card](https://huggingface.co/microsoft/Phi-4-mini-instruct) and [Ollama package](https://ollama.com/library/phi4-mini)
- [Qwen3.8 official repository](https://github.com/QwenLM/Qwen3.8) and [Ollama package](https://ollama.com/library/qwen3.8)

Artifact size is not peak RAM or VRAM. Add model runtime state, KV cache, prompt/context, vision projector where relevant, the application, and the operating system. Use `ollama ps` or the equivalent runtime metrics to record the real CPU/GPU split.

## Context policy

Start at the smallest context that contains a compact structured case plus 4–6 retrieved passages. Benchmark 4K, 8K, and 16K rather than setting the advertised maximum. Ollama documents a 4K default on systems below 24 GiB VRAM, and larger contexts increase memory use. Long raw transcripts and entire manuals should never enter the prompt.

## Retrieval policy

The scaffold starts with SQLite FTS5/BM25 because error codes, commands, driver versions, device models, and exact Windows terms reward lexical matching. Measure retrieval separately. If gold queries show semantic misses, add:

1. `qwen3-embedding:0.6b` as a pinned local embedding model.
2. A small persistent local vector index behind the existing retriever boundary.
3. Reciprocal-rank fusion of lexical and dense results.
4. An optional local reranker only if it improves top-5 recall enough to pay its latency cost.

References: [Qwen3-Embedding-0.6B model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B), [Ollama package](https://ollama.com/library/qwen3-embedding), and [SQLite FTS5](https://www.sqlite.org/fts5.html).

## Fine-tuning gate

Do not start LoRA/QLoRA until the same evaluation set has tested:

- Correct structured state and prompt
- Relevant retrieved evidence
- Duplicate and safety guards
- At least two plausible base models/quantizations

Fine-tune only a stable, repeated behavioral failure (for example, consistently poor next-test selection despite correct state and sources). Keep commands, vendor procedures, model-specific facts, and changing documentation in the knowledge layer.

## Offline release checklist

- Pin runtime installer/version and model digest/checksum.
- Preload Python wheels, model artifacts, embedding model, knowledge pack, and recovery instructions.
- Reboot and test with all networking disabled.
- Confirm the model and API bind to loopback only.
- Record load time, first useful output, total turn time, RAM/VRAM, battery, heat, and schema-valid rate.
- Confirm no component tries to download a model, tokenizer, package, or document during startup.

