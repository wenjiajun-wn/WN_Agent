"""
RAG 知识库模块
支持上传 PDF/TXT，向量化存储，语义检索
"""
import os
import uuid
import chromadb
from chromadb.utils import embedding_functions
from pypdf import PdfReader
from smolagents import tool

# ── 初始化 Chroma ──────────────────────────────────────────────
_CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
_client = chromadb.PersistentClient(path=_CHROMA_PATH)
_ef = embedding_functions.DefaultEmbeddingFunction()   # 使用内置 all-MiniLM-L6-v2


def _get_collection(user_id: str):
    """每个用户拥有独立的 collection，隔离知识库"""
    return _client.get_or_create_collection(
        name=f"user_{user_id}",
        embedding_function=_ef,
    )


# ── 文档入库 ───────────────────────────────────────────────────
def ingest_pdf(file_path: str, user_id: str, chunk_size: int = 500) -> int:
    """
    解析 PDF 并分块入库。
    返回入库的 chunk 数量。
    """
    reader = PdfReader(file_path)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return _ingest_text(text, user_id, source=os.path.basename(file_path), chunk_size=chunk_size)


def ingest_text_file(file_path: str, user_id: str, chunk_size: int = 500) -> int:
    """解析 TXT 文件并入库"""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    return _ingest_text(text, user_id, source=os.path.basename(file_path), chunk_size=chunk_size)


def _ingest_text(text: str, user_id: str, source: str, chunk_size: int) -> int:
    """通用文本分块入库"""
    # 简单按字符数分块（生产环境可换 LangChain TextSplitter）
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    chunks = [c.strip() for c in chunks if len(c.strip()) > 50]

    collection = _get_collection(user_id)
    collection.add(
        documents=chunks,
        ids=[str(uuid.uuid4()) for _ in chunks],
        metadatas=[{"source": source} for _ in chunks],
    )
    return len(chunks)


# ── 检索工具（注册为 SmolAgents tool）─────────────────────────
@tool
def rag_retrieve(query: str, user_id: str = "default", n_results: int = 3) -> str:
    """
    从用户知识库中检索与问题最相关的内容。

    Args:
        query:     用户的问题
        user_id:   用户 ID（默认 'default'）
        n_results: 返回结果数量

    Returns:
        检索到的相关文本段落
    """
    collection = _get_collection(user_id)
    count = collection.count()
    if count == 0:
        return "知识库为空，请先上传文档"

    results = collection.query(query_texts=[query], n_results=min(n_results, count))
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return "知识库中未找到相关内容"

    lines = ["📚 知识库检索结果：\n"]
    for doc, meta in zip(docs, metas):
        source = meta.get("source", "未知来源")
        lines.append(f"[来源：{source}]\n{doc}\n")
    return "\n".join(lines)
