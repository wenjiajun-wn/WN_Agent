"""
长期记忆 — ChromaDB 存储跨会话的重要信息
- 自动存储对话摘要
- 检索相关历史记忆
"""
import uuid
import chromadb
from chromadb.utils import embedding_functions

_client = chromadb.PersistentClient(path="./memory_db")
_ef = embedding_functions.DefaultEmbeddingFunction()


def _get_collection(user_id: str):
    return _client.get_or_create_collection(
        name=f"mem_{user_id}",
        embedding_function=_ef,
    )


def remember(user_id: str, fact: str, category: str = "general") -> None:
    """
    存入一条长期记忆。
    category: preference | task | knowledge | general
    """
    collection = _get_collection(user_id)
    collection.add(
        documents=[fact],
        metadatas=[{"category": category}],
        ids=[str(uuid.uuid4())],
    )


def recall(user_id: str, query: str, n: int = 5) -> list[str]:
    """
    从长期记忆中检索与 query 最相关的记忆。
    返回记忆文本列表。
    """
    collection = _get_collection(user_id)
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n, collection.count()))
    docs = results.get("documents", [[]])[0]
    return [d for d in docs if d]


def recall_all(user_id: str, limit: int = 20) -> list[str]:
    """获取最近存储的记忆"""
    collection = _get_collection(user_id)
    if collection.count() == 0:
        return []
    results = collection.get(limit=min(limit, collection.count()))
    return results.get("documents", [])


def summarize_and_remember(user_id: str, messages: list[dict], llm_model) -> str:
    """
    用 LLM 从对话中提取关键信息，存入长期记忆。
    返回摘要文本。
    """
    if not messages or len(messages) < 2:
        return ""

    # 拼接对话
    dialog = "\n".join(
        f"{'用户' if m['role'] == 'user' else '助手'}: {m['content'][:300]}"
        for m in messages[-20:]
    )

    # 用 LLM 提取关键信息
    summary_prompt = (
        "从以下对话中提取需要长期记住的关键信息，用简短的要点列出（每条不超过50字）。"
        "包括：用户偏好、重要决策、待办事项、个人资料等。"
        "如果没有值得记住的信息，回复'无'。\n\n"
        f"{dialog}"
    )

    try:
        from smolagents import OpenAIServerModel
        if isinstance(llm_model, OpenAIServerModel):
            # 直接用底层 client 做 completion
            resp = llm_model.client.chat.completions.create(
                model=llm_model.model_id,
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            summary = resp.choices[0].message.content.strip()
        else:
            return ""
    except Exception:
        return ""

    if not summary or summary == "无":
        return ""

    # 拆成逐条存储
    for line in summary.split("\n"):
        line = line.lstrip("-•·1234567890. ").strip()
        if len(line) > 5:
            remember(user_id, line, category="knowledge")

    return summary
