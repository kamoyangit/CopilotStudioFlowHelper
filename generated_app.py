import streamlit as st
import os
import json
import time
import hmac
from openai import OpenAI
from duckduckgo_search import DDGS

# 認証設定
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

# ページ設定
st.set_page_config(
    page_title="Copilot Studio Flow アシスタント",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSSでモダンなUI（ダークモード対応）
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 16px;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .main-header h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1rem;
    }
    .chat-message {
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        line-height: 1.6;
        animation: fadeIn 0.3s ease-in;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        margin-left: 15%;
        border-bottom-right-radius: 4px;
    }
    .assistant-message {
        background: rgba(255,255,255,0.1);
        color: #e0e0e0;
        margin-right: 15%;
        border-bottom-left-radius: 4px;
        border: 1px solid rgba(255,255,255,0.1);
    }
    .source-badge {
        display: inline-block;
        background: rgba(102, 126, 234, 0.2);
        color: #a0b4ff;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }
    .stTextInput input,
    .stTextArea textarea,
    div[data-baseweb="input"] input {
        background: #ffffff !important;
        color: #000000 !important;
        caret-color: #000000;
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 12px;
        padding: 0.8rem 1rem;
    }
    div[data-baseweb="input"] {
        background: #ffffff !important;
        border-radius: 12px;
    }
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: #6b7280 !important;
        opacity: 1;
    }
    .stTextInput input:focus,
    .stTextArea textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102,126,234,0.3);
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102,126,234,0.4);
    }
    @media (max-width: 768px) {
        .user-message { margin-left: 5%; }
        .assistant-message { margin-right: 5%; }
        .main-header h1 { font-size: 1.4rem; }
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- 認証
def _require_password() -> None:
    """起動時に PASS_KEY によるパスワードチェックを行う。"""
    pass_key = os.environ.get("PASS_KEY", "")
    if not pass_key:
        st.error(
            "環境変数 `PASS_KEY` が設定されていません。"
            "アプリを起動する前に `export PASS_KEY=...` を設定してください。"
        )
        st.stop()

    if st.session_state.get("authenticated", False):
        return

    now = time.time()
    lockout_until = st.session_state.get("lockout_until", 0)
    if lockout_until and now >= lockout_until:
        st.session_state.login_attempts = 0
        st.session_state.lockout_until = 0
        lockout_until = 0
    if now < lockout_until:
        wait_seconds = int(lockout_until - now) + 1
        st.error(
            "試行回数が上限に達しました。"
            f"{wait_seconds} 秒後に再試行してください。"
        )
        st.stop()

    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    st.title("Copilot Studio Flow ブロックダイアグラム生成")
    st.caption("起動にはパスワードが必要です。")
    with st.form("login_form"):
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", type="primary")

    if submitted:
        if hmac.compare_digest(
            password.encode("utf-8"),
            pass_key.encode("utf-8"),
        ):
            st.session_state.authenticated = True
            st.session_state.login_attempts = 0
            st.session_state.lockout_until = 0
            st.rerun()
        else:
            attempts = st.session_state.login_attempts + 1
            st.session_state.login_attempts = attempts
            if attempts >= MAX_LOGIN_ATTEMPTS:
                st.session_state.lockout_until = (
                    time.time() + LOGIN_LOCKOUT_SECONDS
                )
                st.rerun()
            else:
                st.error(
                    "パスワードが正しくありません。"
                    f"（{attempts}/{MAX_LOGIN_ATTEMPTS}）"
                )

    st.stop()


_require_password()

# ヘッダー
st.markdown("""
<div class="main-header">
    <h1>🤖 Copilot Studio Flow アシスタント</h1>
    <p>Copilot Studio のフロー作成に関するノウハウを学習した専用チャットボット</p>
</div>
""", unsafe_allow_html=True)

# セッション状態の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []
if "show_welcome" not in st.session_state:
    st.session_state.show_welcome = True

# サイドバー
with st.sidebar:
    st.markdown("### ⚙️ 設定")
    st.markdown("---")
    st.markdown("**参照ナレッジ**")
    st.markdown("[Microsoft Learn - Copilot Studio Flows Overview](https://learn.microsoft.com/ja-jp/microsoft-copilot-studio/flows-overview)")
    st.markdown("---")
    st.markdown("**使い方**")
    st.markdown("1. 質問を入力\n2. 送信ボタンをクリック\n3. 回答が表示されます")
    st.markdown("---")
    if st.button("🗑️ 会話をクリア", use_container_width=True):
        st.session_state.messages = []
        st.session_state.show_welcome = True
        st.rerun()

# 検索関数（指数バックオフ付きリトライ）
def search_knowledge(query: str, max_results: int = 5):
    """DuckDuckGoでCopilot Studio Flows関連の情報を検索"""
    search_query = f"site:learn.microsoft.com/microsoft-copilot-studio/flows-overview {query}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for attempt in range(3):
        try:
            with DDGS(headers=headers) as ddgs:
                results = list(ddgs.text(search_query, region="jp-jp", max_results=max_results))
            if results:
                return results
            # 結果が空の場合はフォールバック検索
            with DDGS(headers=headers) as ddgs:
                results = list(ddgs.text(f"Copilot Studio フロー {query}", region="jp-jp", max_results=max_results))
            return results
        except Exception:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                return []
    return []

# DeepSeek API呼び出し
def ask_deepseek(question: str, context: str, history: list):
    """DeepSeek APIで回答を生成"""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return "⚠️ DEEPSEEK_API_KEY が設定されていません。環境変数を確認してください。"

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    system_prompt = """あなたはMicrosoft Copilot Studioのフロー作成に関する専門家アシスタントです。
以下の参照情報を基に、ユーザーの質問に正確かつ分かりやすく日本語で回答してください。
参照情報に含まれない内容については、一般的なCopilot Studioの知識として補足しても構いませんが、その旨を明記してください。

【参照情報】
""" + context + """

回答は簡潔にまとめ、必要に応じて箇条書きや手順を示してください。"""

    messages = [{"role": "system", "content": system_prompt}]
    # 直近の会話履歴を追加（最大6件）
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.3,
            max_tokens=1500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ 回答の生成中にエラーが発生しました: {str(e)}"

# 会話履歴の表示
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-message user-message">👤 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-message assistant-message">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("sources"):
            sources_html = " ".join([f'<span class="source-badge">📎 {s}</span>' for s in msg["sources"]])
            st.markdown(sources_html, unsafe_allow_html=True)

# 入力フォーム
with st.form(key="chat_form", clear_on_submit=True):
    col1, col2 = st.columns([5, 1])
    with col1:
        user_input = st.text_input(
            "質問を入力してください",
            placeholder="例: Copilot Studioでフローを作成する手順を教えて",
            label_visibility="collapsed"
        )
    with col2:
        submitted = st.form_submit_button("送信", use_container_width=True)

if submitted and user_input.strip():
    question = user_input.strip()
    # ユーザーメッセージを追加
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("🔍 ナレッジを検索中..."):
        results = search_knowledge(question)

    # コンテキスト構築
    context_parts = []
    sources = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")
        if body:
            context_parts.append(f"【{title}】\n{body}\n(出典: {href})")
            if title and title not in sources:
                sources.append(title[:40])

    context = "\n\n".join(context_parts) if context_parts else "参照情報が見つかりませんでした。一般的な知識で回答します。"

    with st.spinner("🤔 回答を生成中..."):
        answer = ask_deepseek(question, context, st.session_state.messages[:-1])

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "sources": sources[:3]
    })
    st.session_state.show_welcome = False
    st.rerun()

# ウェルカムメッセージ
if st.session_state.show_welcome and not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding: 2rem; color: #a0a0a0;">
        <p style="font-size: 1.1rem;">💡 サンプルの質問</p>
        <p>「Copilot Studioでフローを作成するには？」</p>
        <p>「フローのトリガーとアクションの違いは？」</p>
        <p>「Power Automateとの連携方法を教えて」</p>
    </div>
    """, unsafe_allow_html=True)
