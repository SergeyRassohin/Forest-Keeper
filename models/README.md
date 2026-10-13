# Forest Keeper — AI model artifacts

Эта папка хранит **описание и конфигурацию моделей**, но не их веса.

## Canonical manifest

`model-manifest.yaml` определяет допустимые для MVP модели, upstream revision, формат, quantization, embedding dimension и правила offline-пакета.

## Do not commit

Не добавлять в Git:
- `*.gguf`
- `*.safetensors`
- Hugging Face cache
- model snapshots
- offline model bundles
- временные checksum-файлы, созданные до утверждения release package

Весовые файлы поставляются через отдельный model/offline artifact pipeline.

## MVP baseline

- LLM: `Qwen/Qwen3-8B-GGUF`, `Q4_K_M`, llama.cpp.
- Embeddings: `Qwen/Qwen3-Embedding-0.6B`, 1024 dimensions, sentence-transformers.
- Vector store: PostgreSQL + pgvector.

Подробности: `docs/ai/local-model-v0.1.md`.

## Rule for Codex

Не заменять модель, revision, quantization или embedding dimension по собственному усмотрению. Любое изменение сначала фиксируется в Decision Log и model manifest.
