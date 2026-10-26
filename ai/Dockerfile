# syntax=docker/dockerfile:1
ARG PYTHON_BASE=python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
FROM ${PYTHON_BASE} AS native
RUN --mount=type=secret,id=network_ca,required=true \
    apt-get -o Acquire::https::CaInfo=/run/secrets/network_ca update \
    && apt-get -o Acquire::https::CaInfo=/run/secrets/network_ca install -y --no-install-recommends g++ cmake make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /native
COPY work/stage9-native-src/ ./
RUN python -c 'import json,pathlib,hashlib; r=pathlib.Path("."); m=json.loads((r/"FK_SOURCE_SHA256.json").read_text()); assert all(hashlib.sha256((r/p).read_bytes()).hexdigest()==v for p,v in m.items())' \
    && test "$(cat FK_SOURCE_REVISION)" = 620d2225cc436ab0b001e3200e590e3b286ef9ab \
    && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_NUMBER=0 -DLLAMA_BUILD_COMMIT=620d2225c \
       -DGGML_NATIVE=OFF -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON \
       -DLLAMA_CURL=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF \
    && cmake --build build --target llama-server -j 2 \
    && mkdir /release && cp -L build/bin/llama-server build/bin/*.so* /release/ \
    && cp LICENSE FK_SOURCE_REVISION /release/ \
    && c++ --version > /release/compiler.txt \
    && cd /release && sha256sum llama-server *.so* > native.sha256
RUN mkdir -p /release/notices \
    && cp FK_SOURCE_SHA256.json /release/ \
    && find vendor ggml -type f \( -iname '*license*' -o -iname '*copying*' \) \
       -exec cp --parents '{}' /release/notices/ \;

FROM ${PYTHON_BASE} AS base
RUN --mount=type=secret,id=network_ca,required=true \
    apt-get -o Acquire::https::CaInfo=/run/secrets/network_ca update \
    && apt-get -o Acquire::https::CaInfo=/run/secrets/network_ca install -y --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && PIP_CERT=/run/secrets/network_ca pip install --no-cache-dir uv==0.12.23
WORKDIR /app
COPY ai/pyproject.toml ai/uv.lock ./
RUN --mount=type=secret,id=network_ca,required=true \
    SSL_CERT_FILE=/run/secrets/network_ca uv sync --frozen --no-dev --no-install-project \
    && useradd --uid 10001 --create-home fk
COPY backend/app/__init__.py ./app/__init__.py
COPY backend/app/ai ./app/ai
COPY models/artifacts.lock.json /app/artifacts.lock.json
ENV PATH="/app/.venv/bin:$PATH" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 \
    TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
    FK_AI_ARTIFACT_LOCK=/app/artifacts.lock.json FK_AI_MODEL_ROOT=/models \
    FK_AI_KEY_FILE=/run/secrets/fk_ai_key FK_AI_FAULT_FILE=/tmp/fk-ai-fault
USER fk
ENTRYPOINT ["python", "-m", "app.ai.supervisor"]

FROM base AS embedding
USER root
RUN --mount=type=secret,id=network_ca,required=true \
    SSL_CERT_FILE=/run/secrets/network_ca uv sync --frozen --extra embedding --no-dev --no-install-project
USER fk
ENV FK_AI_COMPONENT=embedding

FROM base AS llm
COPY --from=native /release /app/native
ENV FK_AI_COMPONENT=llm LD_LIBRARY_PATH=/app/native
