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
FROM node:18-bookworm-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production

# まず package*.json をコピーして本番依存だけ入れる
COPY --from=build /src/app/package.json /src/app/package-lock.json* /app/
RUN if [ -f package-lock.json ]; then npm ci --omit=dev; else npm install --omit=dev; fi

# アプリ本体とビルド成果物をコピー
COPY --from=build /src/app /app

EXPOSE 3000
CMD ["npm", "run", "start"]
