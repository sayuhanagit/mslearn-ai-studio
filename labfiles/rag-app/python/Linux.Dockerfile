# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 依存関係
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY . .

# App Service は PORT 環境変数でポートを渡す（無い場合は 8000）
ENV PORT=8000
EXPOSE 8000

# gunicorn で Flask(app) を起動
# rag_app:app ＝ rag_app.py の中の app 変数
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 rag_app:app"]
