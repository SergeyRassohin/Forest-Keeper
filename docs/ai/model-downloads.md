# Qwen: точные версии, скачивание и проверка

Проверено 21 октября 2026 по официальным Hugging Face API и pinned model cards. Семейство, revisions, формат и размерность **не заменены**. Наличие файлов не означает, что AI интегрирован в Forest Keeper: текущий Compose не запускает LLM/embedding services, model-info и inference smoke ещё отсутствуют. Импорт/нормализация работают без Qwen.

## Какие модели соответствуют архитектуре

| Назначение | Репозиторий | Точная revision | Артефакт / параметры |
| --- | --- | --- | --- |
| Объяснения и рекомендации | Qwen/Qwen3-8B-GGUF | `7c41481f57cb95916b40956ab2f0b139b296d974` | `Qwen3-8B-Q4_K_M.gguf`, GGUF, Q4_K_M, llama.cpp, 32768 tokens configured |
| Поиск похожих решений | Qwen/Qwen3-Embedding-0.6B | `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3` | `model.safetensors` + tokenizer/config, sentence-transformers, 1024 dimensions |

Это исходный архитектурный baseline из [Local AI](local-model-v0.1.md) и [manifest](../../models/model-manifest.yaml). Страница репозитория без revision может показать новое содержимое, поэтому скачивать нужно по ссылкам ниже. Qwen3-8B, Qwen3-Embedding-0.6B, другие квантования, Instruct-варианты и другие размеры — разные artifacts, их нельзя подменять друг другом.

## Прямые официальные ссылки

- [LLM: файлы именно закреплённой revision](https://huggingface.co/Qwen/Qwen3-8B-GGUF/tree/7c41481f57cb95916b40956ab2f0b139b296d974).
- [Скачать Qwen3-8B-Q4_K_M.gguf](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/7c41481f57cb95916b40956ab2f0b139b296d974/Qwen3-8B-Q4_K_M.gguf).
- [LLM model card закреплённой revision](https://huggingface.co/Qwen/Qwen3-8B-GGUF/blob/7c41481f57cb95916b40956ab2f0b139b296d974/README.md).
- [LLM LICENSE](https://huggingface.co/Qwen/Qwen3-8B-GGUF/blob/7c41481f57cb95916b40956ab2f0b139b296d974/LICENSE).
- [Embedding: файлы именно закреплённой revision](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/tree/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3).
- [Скачать embedding weights](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/resolve/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/model.safetensors).
- [Embedding model card и лицензия Apache-2.0 в metadata](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/blob/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3/README.md).

Для embedding одного `model.safetensors` недостаточно: нужны tokenizer, config и `1_Pooling/config.json`. Полный проверяемый набор перечислен в [artifacts.lock.json](../../models/artifacts.lock.json). В upstream embedding revision отдельного LICENSE-файла нет; Apache-2.0 объявлен в model card. Это учтено, не добавлена несуществующая ссылка `/LICENSE`.

## Размеры и контрольные суммы

| Файл | Размер, байт | SHA-256 |
| --- | ---: | --- |
| Qwen3-8B-Q4_K_M.gguf | 5027783488 | `d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785` |
| embedding/model.safetensors | 1191586416 | `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd` |

Итого веса — около 6.22 GB (5.79 GiB), плюс tokenizer/config. Для файлов выделите не менее 8 GB свободного диска дополнительно к приложению. Во время повторной загрузки может потребоваться место для `.part` и существующего файла одновременно. Дисковый объём не определяет RAM/VRAM: полный configured context 32768 требует дополнительной памяти. Проверенный минимум RAM/VRAM для поддерживаемого AI runtime ещё не опубликован; не считайте размер GGUF оценкой всей памяти.

Большие SHA-256 получены из LFS metadata точных revisions; маленькие файлы скачаны и хешированы. Команда download ниже проверяет **все локальные байты**, а не только имя или HTTP 200. Checksum lock не является цифровой подписью offline bundle. Требования подписанной офлайн-поставки сохраняются отдельно.

## Поддерживаемое получение файлов

Это отдельный необязательный шаг подготовки моделей для разработчика/проверяющего AI. Базовый сценарий этапов 0–3 не требует установки этих инструментов.

1. Установите [uv по официальной инструкции](https://docs.astral.sh/uv/getting-started/installation/). Например, используйте опубликованный там installer для своей ОС. Проверьте `uv --version`.
2. Из корня Forest-Keeper выполните:

```bash
uv run --script scripts/models.py info
uv run --script scripts/models.py check-upstream
uv run --script scripts/models.py download
uv run --script scripts/models.py verify
```

uv при необходимости получает Python и закреплённую зависимость PyYAML 6.0.3 из metadata скрипта. Сетевые зависимости нужны при первой подготовке; TLS verification сохраняется. `check-upstream` проверяет model ID, revision, размеры и hashes по официальному API. Он не запускает inference. `download` получает только files из lock, пишет через временный `.part`, проверяет размер и SHA-256 и только затем заменяет финальный файл. Успех отмечается `SHA256 PASS` для каждого файла.

Каталоги по умолчанию:

```text
models/downloads/llm/Qwen3-8B-Q4_K_M.gguf
models/downloads/llm/LICENSE
models/downloads/llm/README.md
models/downloads/embedding/model.safetensors
models/downloads/embedding/tokenizer.json
models/downloads/embedding/1_Pooling/config.json
... остальные файлы artifacts.lock.json
```

Каталог не коммитится в Git. При необходимости одинаково задайте `--directory /absolute/path/to/models` для download и verify. Не публикуйте веса в Git.

Повторный download проверяет уже имеющиеся файлы и не скачивает исправные заново. При mismatch команда заканчивается ошибкой; старый файл сохраняется до успешной проверки нового. После прерванной загрузки проверьте, что другого процесса download нет, удалите только соответствующий `.part` и повторите. Автоматического resume нет; скачивание большого файла начнётся заново. Не удаляйте data volumes приложения ради исправления загрузки модели.

`verify` не обращается к Hugging Face. Для проверки на машине без Интернета заранее подготовьте uv/Python/PyYAML на этой машине, затем используйте `uv run --offline --script scripts/models.py verify`. Полный подписанный offline installer с зависимостями пока не реализован.

## Что именно подтверждено и что ещё проверить

Upstream Q4_K_M artifact имеет правильные имя и размер. Embedding config содержит `model_type=qwen3`, `hidden_size=1024`, `max_position_embeddings=32768`; pooling config указывает dimension 1024 и last-token pooling. Это соответствует архитектуре, но проверка config не заменяет получения реального вектора.

После реализации AI runtime приёмка должна отдельно подтвердить:

1. llama.cpp загрузил именно этот GGUF и сообщает revision в FK model-info.
2. Embedding service использует весь pinned snapshot, выдаёт 1024 значения и корректно обрабатывает retrieval instruction/pooling.
3. Runtime версии закреплены и проверены; установка не использует неоговорённый `latest`.
4. Non-thinking mode, structured output, русский текст и ссылки только на backend evidence проходят smoke.
5. Векторы сохраняются в pgvector; похожий случай находит реальный подтверждённый Decision.
6. Без LLM доступна история и детерминированный путь; после отключения внешней сети inference остаётся локальным.

До этих проверок AI-enabled review по #18 остаётся BLOCKED. Это документированные оставшиеся работы, а не команды к несуществующим сервисам.
