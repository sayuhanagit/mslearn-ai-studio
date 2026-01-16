import os
from flask import Flask, render_template, request, jsonify, session
from openai import AzureOpenAI

app = Flask(__name__)
# App Service では必ず SECRET_KEY を設定するのが望ましい
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")

def get_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v

def build_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_version="2024-12-01-preview",
        azure_endpoint=get_env("OPEN_AI_ENDPOINT"),
        api_key=get_env("OPEN_AI_KEY"),
    )

def rag_params():
    return {
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    "endpoint": get_env("SEARCH_ENDPOINT"),
                    "index_name": get_env("INDEX_NAME"),
                    "authentication": {"type": "api_key", "key": get_env("SEARCH_KEY")},
                    "query_type": "vector",
                    "embedding_dependency": {
                        "type": "deployment_name",
                        "deployment_name": get_env("EMBEDDING_MODEL"),
                    },
                },
            }
        ]
    }

SYSTEM_MESSAGE = "You are a travel assistant that provides information on travel services available from Margie's Travel."

@app.get("/")
def index():
    # セッションにチャット履歴が無ければ初期化
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
    resp = client.chat.completions.create(
        model=get_env("CHAT_MODEL"),
        messages=messages,
        extra_body=rag_params(),
    )

    assistant_text = resp.choices[0].message.content or ""
    messages.append({"role": "assistant", "content": assistant_text})

    # セッションに保存
    session["messages"] = messages

    return jsonify({"reply": assistant_text})

@app.post("/api/reset")
def reset():
    session["messages"] = [{"role": "system", "content": SYSTEM_MESSAGE}]
    return jsonify({"ok": True})
