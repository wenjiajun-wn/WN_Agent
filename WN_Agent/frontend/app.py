"""
Streamlit 前端 — 快速原型
运行：streamlit run frontend/app.py
"""
import threading
import time
import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="WN Agent", page_icon="🤖", layout="wide")
st.title(" WN Agent ")

# ── 会话状态初始化 ─────────────────────────────────────────────
if "conversations" not in st.session_state:
    # 对话列表：[{"id": str, "title": str, "messages": [...]}, ...]
    st.session_state.conversations = []
if "conv_id" not in st.session_state:
    st.session_state.conv_id = None  # 当前活跃对话 ID
if "pending" not in st.session_state:
    st.session_state.pending = False
if "_reply" not in st.session_state:
    st.session_state._reply = None


def _current_conv():
    """返回当前活跃的对话对象，没有则返回 None"""
    cid = st.session_state.conv_id
    for c in st.session_state.conversations:
        if c["id"] == cid:
            return c
    return None


def _current_messages():
    """当前对话的消息列表"""
    conv = _current_conv()
    return conv["messages"] if conv else []


def _add_message(role: str, content: str):
    """向当前对话添加一条消息"""
    conv = _current_conv()
    if conv:
        conv["messages"].append({"role": role, "content": content})


def _new_conversation():
    """创建新对话"""
    import uuid
    cid = str(uuid.uuid4())[:8]
    conv = {"id": cid, "title": "", "messages": []}
    st.session_state.conversations.insert(0, conv)
    st.session_state.conv_id = cid


def _switch_conversation(cid: str):
    """切换到指定对话"""
    st.session_state.conv_id = cid


# ── 侧边栏 ─────────────────────────────────────────────────────
with st.sidebar:
    # 新建对话
    if st.button("➕ 新建对话", use_container_width=True):
        _new_conversation()
        st.rerun()

    st.divider()

    # 对话历史
    if not st.session_state.conversations:
        st.caption("暂无对话记录")

    for conv in st.session_state.conversations:
        title = conv["title"] or "（空对话）"
        is_active = conv["id"] == st.session_state.conv_id

        # 高亮当前对话
        label = f"{'🔹 ' if is_active else ''}{title}"
        if st.button(
            label,
            key=f"conv_{conv['id']}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            _switch_conversation(conv["id"])
            st.rerun()

# ── 对话主界面 ─────────────────────────────────────────────────
# 如果没有当前对话，自动创建
if not _current_conv():
    _new_conversation()
    st.rerun()

# 展示历史消息
messages = _current_messages()
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── 底部输入栏（千问风格：发送 / 停止在同一栏）─────────────────
if st.session_state.pending:
    # 等待中：禁用输入 + ■ 停止按钮
    c1, c2 = st.columns([20, 1])
    with c1:
        st.text_input(
            "输入框", key="pending_input", disabled=True,
            placeholder="AI 正在回复...",
            label_visibility="collapsed",
        )
    with c2:
        if st.button("⏹", key="stop_btn", help="停止生成", use_container_width=True):
            try:
                httpx.post(f"{API_BASE}/cancel", params={"user_id": st.session_state.conv_id}, timeout=5)
            except Exception:
                pass
            st.session_state.pending = False
            _add_message("assistant", "⏹️ 已中断")
            st.rerun()
    time.sleep(1)
    st.rerun()

else:
    # 正常：chat_input + 回车即发送
    if prompt := st.chat_input("输入消息，Enter 发送"):
        conv = _current_conv()
        if conv and not conv["title"]:
            conv["title"] = prompt[:20] + ("..." if len(prompt) > 20 else "")

        _add_message("user", prompt)
        st.session_state.pending = True
        st.session_state._reply = None

        def _call(p, uid):
            try:
                resp = httpx.post(
                    f"{API_BASE}/chat",
                    json={"message": p, "user_id": uid},
                    timeout=300.0,
                )
                if resp.status_code == 200:
                    st.session_state._reply = resp.json()["reply"]
                else:
                    st.session_state._reply = f"错误：{resp.text}"
            except httpx.ReadTimeout:
                st.session_state._reply = "⏱️ 请求超时，请简化问题后重试。"
            except httpx.ConnectError:
                st.session_state._reply = "❌ 无法连接后端，请确认已启动。"
            except Exception as e:
                st.session_state._reply = f"❌ 连接失败：{e}"
            st.session_state.pending = False

        threading.Thread(target=_call, args=(prompt, st.session_state.conv_id), daemon=True).start()
        st.rerun()

# 显示回复
if st.session_state._reply is not None:
    reply = st.session_state._reply
    st.session_state._reply = None
    _add_message("assistant", reply)
    st.rerun()
