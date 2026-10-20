# Forest Keeper — AI model artifacts

Эта папка хранит **описание и конфигурацию моделей**, но не их веса.

## Canonical manifest

`model-manifest.yaml` определяет допустимые для MVP модели, upstream revision, формат, quantization, embedding dimension и правила offline-пакета.

## Получение и проверка

[Проверенные ссылки и пошаговая инструкция](../docs/ai/model-downloads.md) фиксируют обе Qwen revisions и expected hashes. Из корня:

```bash
uv run --script scripts/models.py check-upstream
uv run --script scripts/models.py download
uv run --script scripts/models.py verify
```

`artifacts.lock.json` содержит полный набор tokenizer/config/weights и их SHA-256. Это подготовка файлов, не запуск AI. Поддерживаемый inference runtime/model-info остаётся блокером внешней AI-проверки.

## Do not commit

Не добавлять в Git:
- `*.gguf`
- `*.safetensors`
- Hugging Face cache
- model snapshots
- offline model bundles
- временные checksum-файлы и подписанные bundles; утверждённый `artifacts.lock.json` с проверенными hashes хранится в Git

Весовые файлы поставляются через отдельный model/offline artifact pipeline.

## MVP baseline

- LLM: `Qwen/Qwen3-8B-GGUF`, `Q4_K_M`, llama.cpp.
- Embeddings: `Qwen/Qwen3-Embedding-0.6B`, 1024 dimensions, sentence-transformers.
- Vector store: PostgreSQL + pgvector.

Подробности: `docs/ai/local-model-v0.1.md`.

## Rule for Codex

Не заменять модель, revision, quantization или embedding dimension по собственному усмотрению. Любое изменение сначала фиксируется в Decision Log и model manifest.
