# syntax=docker/dockerfile:1

############################
# Build stage
############################
FROM node:18-bookworm-slim AS build

# git/ca-certificates（https clone用）
RUN apt-get update \
  && apt-get install -y --no-install-recommends git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

ARG REPO_URL=https://github.com/sayuhanagit/chatbot-ui.git
ARG REPO_REF=main

WORKDIR /src

# clone（REPO_REFはブランチ/タグ/コミットSHAでもOK）
RUN git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" app

WORKDIR /src/app

# 依存関係（lockがあれば npm ci）
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# メモリ増やしたい場合
ENV NODE_OPTIONS=--max-old-space-size=8192

# build
RUN npm run build


############################
# Runtime stage
############################
# Runtime stage
FROM node:18-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /src/app/package.json /src/app/package-lock.json* /app/

# ★ ここがポイント：--ignore-scripts を付ける
RUN if [ -f package-lock.json ]; then \
      npm ci --omit=dev --ignore-scripts; \
    else \
      npm install --omit=dev --ignore-scripts; \
    fi