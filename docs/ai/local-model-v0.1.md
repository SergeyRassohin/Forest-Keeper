# Forest Keeper — Local AI Model Baseline v0.1

Статус: обязательный baseline для разработки AI-контура MVP. AI runtime ещё не реализован в main. [Проверенные ссылки, hashes и команды получения файлов](model-downloads.md); загрузка файлов не означает готовности inference.

## 1. Назначение

Forest Keeper использует две локальные модели с разными задачами:

1. **LLM** — объяснение конфликтов, формирование понятной рекомендации и работа с уже отобранным структурированным контекстом.
2. **Embedding model** — векторизация Decision context и поиск похожих подтверждённых решений через PostgreSQL + pgvector.

Модели не являются корпоративной памятью и не обучаются после каждого решения пользователя. Память FK — это Decision Registry, Rules, mappings, CustomerTemplate, provenance и Audit.

## 2. LLM baseline

- Provider/author: Qwen
- Model repository: `Qwen/Qwen3-8B-GGUF`
- Pinned upstream revision: `7c41481f57cb95916b40956ab2f0b139b296d974`
- Artifact: `Qwen3-8B-Q4_K_M.gguf`
- Quantization: `Q4_K_M`
- License: Apache-2.0
- Runtime: `llama.cpp`
- Native context: 32,768 tokens
- Extended context supported upstream with YaRN: up to 131,072 tokens
- **MVP configured context: 32,768 tokens**
- MVP default mode: non-thinking / concise structured answer
- Network requirement at runtime: none

### Why this model

Для MVP требуется локальная модель, которая:
- поддерживает русский и английский текст;
- работает без передачи клиентских данных наружу;
- имеет достаточно компактный GGUF-вариант для on-prem развёртывания;
- может обслуживаться через OpenAI-compatible local HTTP API;
- допускает замену в будущем без изменения Decision Registry.

## 3. Embedding baseline

- Provider/author: Qwen
- Model repository: `Qwen/Qwen3-Embedding-0.6B`
- Pinned upstream revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`
- Format: Safetensors / sentence-transformers
- License: Apache-2.0
- Context length: 32K
- Native embedding dimension: up to 1024
- **MVP embedding dimension: 1024**
- Runtime/library: `sentence-transformers`
- Vector store: PostgreSQL + pgvector
- Network requirement at runtime: none

## 4. Architecture rules

1. LLM and embedding model are separate services/components.
2. Backend business logic must not depend on model-specific Python classes.
3. Integration with the LLM goes through an internal adapter/interface.
4. Similarity search must remain usable even if the LLM is unavailable.
5. Recommendation must contain structured evidence: Rules/Basis, similar Decision IDs and provenance.
6. AI confidence never authorizes a business action.
7. LLM never writes directly to source systems, Decision Registry, Rule or CustomerTemplate.
8. Model output is treated as untrusted input and validated against an application schema.
9. Prompt/template versions are versioned in Git.
10. Model revision used for a Recommendation must be recordable in Audit/Recommendation metadata.

## 5. MVP inference contract

Recommended internal LLM service API:

```text
POST /internal/ai/recommend
POST /internal/ai/explain
GET  /internal/ai/health
GET  /internal/ai/model-info
```

The application sends only the minimum necessary structured context:
- current Conflict;
- normalized/raw values required for explanation;
- active relevant Rules/Basis;
- selected similar confirmed Decisions;
- authoritative-source information;
- output schema.

The service returns:
- recommended action;
- concise reasoning summary;
- references to evidence provided by the application;
- model identifier/revision;
- inference metadata.

The LLM must not invent prior decisions. Any Decision referenced by the response must already be present in the supplied context and be validated by backend.

## 6. Similarity flow

```text
Human Decision
    ↓
structured Decision context
    ↓
Qwen3-Embedding-0.6B
    ↓
vector(1024)
    ↓
PostgreSQL / pgvector
    ↓
structured filters + semantic search
    ↓
top similar confirmed Decisions
    ↓
Recommendation Engine
    ↓
Qwen3-8B for explanation/recommendation
    ↓
Human Review
```

Structured SQL filters must narrow candidates before/alongside vector similarity where appropriate. Embedding similarity is evidence, not truth.

## 7. Model files and Git

Model weights **must not be committed to the Forest Keeper Git repository**.

Git contains:
- this specification;
- `models/model-manifest.yaml`;
- runtime configuration;
- prompt/templates;
- artifact acquisition/verification script (`scripts/models.py`); packaging/signature workflow remains future work;
- license notices required for distribution.

Git does not contain:
- `*.gguf`;
- `*.safetensors`;
- downloaded model caches;
- generated offline model packages.

## 8. Online development flow

Use `uv run --script scripts/models.py download` from the repository root. It downloads only the model/revision and artifacts fixed in `models/model-manifest.yaml` and `models/artifacts.lock.json`. Full instructions: [model downloads](model-downloads.md).

A developer must not use `latest` or silently substitute another model.

After download:
1. verify repository revision/artifact;
2. record local artifact checksum;
3. run model smoke test;
4. run embedding-dimension test;
5. run Russian-language recommendation test;
6. run offline test with outbound network disabled.

## 9. Offline customer flow

For closed customer networks the supplier prepares a signed offline AI package containing:
- exact model artifacts;
- model manifest;
- license/notice files;
- SHA-256 checksums;
- supported FK version range;
- package signature.

Suggested artifact name:

`FK_AI_Model_Bundle_<version>.pkg`

The customer-side installer verifies signature and checksums before installing. The customer does not need Hugging Face or Internet access.

## 10. Compatibility and upgrades

Changing any of the following requires an explicit compatibility test:
- LLM family or revision;
- GGUF quantization;
- embedding model;
- embedding dimension;
- prompt/template format;
- inference runtime.

Changing embedding model or dimension requires a controlled re-embedding migration. Existing Decision records themselves are never replaced.

## 11. Acceptance criteria for MVP AI baseline

- Qwen3-8B Q4_K_M starts locally through llama.cpp.
- `/internal/ai/model-info` reports exact model ID and pinned revision.
- Qwen3-Embedding-0.6B produces vectors of dimension 1024.
- pgvector stores and retrieves Decision embeddings.
- A known second conflict retrieves the earlier confirmed Decision as a similar case.
- Recommendation references only evidence actually supplied by backend.
- With the LLM stopped, deterministic conflict review and Decision Registry remain available.
- With external network blocked, the full AI recommendation path works using preinstalled model files.

## 12. Upstream references

- https://huggingface.co/Qwen/Qwen3-8B-GGUF
- https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- https://github.com/QwenLM/Qwen3
- https://github.com/QwenLM/Qwen3-Embedding
- https://github.com/ggml-org/llama.cpp

Upstream documentation is reference material. Forest Keeper implementation must follow the pinned model manifest and project decisions rather than automatically following upstream `main`.
