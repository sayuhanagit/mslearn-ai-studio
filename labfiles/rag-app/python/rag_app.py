import os
import requests
from flask import Flask, render_template, request, jsonify, session
from openai import AzureOpenAI

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

def get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v

def get_env_default(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v else default

def build_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_version="2024-12-01-preview",
        azure_endpoint=get_env("OPEN_AI_ENDPOINT"),
        api_key=get_env("OPEN_AI_KEY"),
    )

SYSTEM_MESSAGE = "You are a travel assistant that provides information on travel services available from Margie's Travel."

# ===== App-side RAG: Search & Embedding =====

def embed_text(client: AzureOpenAI, text: str) -> list[float]:
    # Embedding デプロイ名を使う（あなたの env: EMBEDDING_MODEL）
    emb = client.embeddings.create(
        model=get_env("EMBEDDING_MODEL"),
        input=text
    )
    return emb.data[0].embedding

def search_docs(query: str, vector: list[float], top_k: int = 5) -> list[dict]:
    """
    Azure AI Search の REST API をアプリから直接呼び出す（＝Private Endpoint 経由で通る）
    """
    search_endpoint = get_env("SEARCH_ENDPOINT").rstrip("/")
    index_name = get_env("INDEX_NAME")
    search_key = get_env("SEARCH_KEY")

    # Search API version（必要に応じて変更）
    api_version = get_env_default("SEARCH_API_VERSION", "2024-03-01-preview")

    # index のフィールド名は環境で違うので env で可変にする
    vector_field = get_env_default("SEARCH_VECTOR_FIELD", "contentVector")
    content_field = get_env_default("SEARCH_CONTENT_FIELD", "content")
    title_field = get_env_default("SEARCH_TITLE_FIELD", "title")

    url = f"{search_endpoint}/indexes/{index_name}/docs/search?api-version={api_version}"

    headers = {
        "Content-Type": "application/json",
        "api-key": search_key,
    }

    # ベクター検索（必要なら keyword も併用＝ハイブリッド）
    payload = {
        "top": top_k,
        "select": f"{title_field},{content_field}",
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": vector,
                "k": top_k,
                "fields": vector_field
            }
        ],
        # ハイブリッドにしたい場合は search を有効に（不要なら "" にする）
        "search": query
    }

    r = requests.post(url, headers=headers, json=payload, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Azure AI Search error: {r.status_code} {r.text}")

    data = r.json()
    return data.get("value", [])

def build_context(docs: list[dict]) -> str:
    """
    取得した検索結果を LLM に渡す用のコンテキスト文字列に整形
    """
    title_field = get_env_default("SEARCH_TITLE_FIELD", "title")
    content_field = get_env_default("SEARCH_CONTENT_FIELD", "content")

    chunks = []
    for i, d in enumerate(docs, start=1):
        title = d.get(title_field, "")
        content = d.get(content_field, "")
        chunks.append(f"[{i}] {title}\n{content}".strip())

    return "\n\n".join(chunks).strip()

# ===== Routes =====

@app.get("/")
def index():
    if "messages" not in session:
        session["messages"] = [{"role": "system", "content": SYSTEM_MESSAGE}]
    return render_template("index.html")

@app.post("/api/chat")
def chat():
    user_text = (request.json or {}).get("message", "").strip()
    if not user_text:
        return jsonify({"error": "message is required"}), 400

    messages = session.get("messages") or [{"role": "system", "content": SYSTEM_MESSAGE}]
    messages.append({"role": "user", "content": user_text})

    client = build_client()

    # 1) アプリ側で embedding を作る
    qvec = embed_text(client, user_text)

    # 2) アプリ側で AI Search に問い合わせ（Private Endpoint 経由で到達）
    docs = search_docs(user_text, qvec, top_k=int(get_env_default("SEARCH_TOP_K", "5")))
    context = build_context(docs)

    # 3) LLM に “コンテキスト付き” で投げる（extra_body は使わない）
    augmented_messages = list(messages)  # session の messages を壊さない
    if context:
        augmented_messages.insert(
            1,  # system の直後に入れる
            {
                "role": "system",
                "content": "Use the following retrieved context to answer. "
                           "If the context is insufficient, say you don't know.\n\n"
                           f"Retrieved context:\n{context}"
            }
        )

    resp = client.chat.completions.create(
        model=get_env("CHAT_MODEL"),
        messages=augmented_messages,
    )

    assistant_text = resp.choices[0].message.content or ""
    messages.append({"role": "assistant", "content": assistant_text})
    session["messages"] = messages

    return jsonify({"reply": assistant_text})

@app.post("/api/reset")
def reset():
    session["messages"] = [{"role": "system", "content": SYSTEM_MESSAGE}]
    return jsonify({"ok": True})
