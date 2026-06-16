"""
FastAPI 后端
提供对话、文档上传、用户偏好管理接口
"""
import os
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from agents.manager import chat, request_cancel
from memory.user_memory import UserMemory, save_conversation, load_conversations, delete_conversation
from rag.knowledge_base import ingest_pdf, ingest_text_file

app = FastAPI(title="AI Personal Assistant", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # 生产环境改为具体域名
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 数据模型 ───────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    user_id: str = "default"
    history: list[dict] | None = None  # [{"role":"user","content":"..."}, ...]

class ChatResponse(BaseModel):
    reply: str
    user_id: str

class PreferenceRequest(BaseModel):
    user_id: str = "default"
    preferences: dict       # 例如 {"food_preference": "辣", "city": "台中"}


# ── 接口定义 ───────────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """对话接口 — 核心入口"""
    try:
        reply = chat(req.message, req.user_id, req.history)
        return ChatResponse(reply=reply, user_id=req.user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "default",
):
    """上传文档并入库（支持 PDF / TXT）"""
    suffix = os.path.splitext(file.filename)[1].lower()
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 TXT 文件")

    # 写到临时文件再处理
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        if suffix == ".pdf":
            count = ingest_pdf(tmp_path, user_id)
        else:
            count = ingest_text_file(tmp_path, user_id)
    finally:
        os.unlink(tmp_path)

    return {"message": f"文档上传成功，共入库 {count} 个片段", "filename": file.filename}


@app.post("/preferences")
async def update_preferences(req: PreferenceRequest):
    """更新用户偏好"""
    mem = UserMemory(req.user_id)
    mem.update_preferences(req.preferences)
    return {"message": "偏好已更新", "preferences": mem.get_preferences()}


@app.get("/preferences/{user_id}")
async def get_preferences(user_id: str):
    """查询用户偏好"""
    mem = UserMemory(user_id)
    return {"user_id": user_id, "preferences": mem.get_preferences()}


@app.post("/cancel")
async def cancel_request(user_id: str = "default"):
    """中断当前对话"""
    request_cancel(user_id)
    return {"message": "已发送中断信号", "user_id": user_id}


_FRONTEND_HTML = Path(__file__).parent.parent / "frontend" / "index.html"


@app.get("/conversations")
async def list_conversations():
    """获取所有对话列表"""
    return load_conversations()


@app.post("/conversations")
async def save_conv(req: dict):
    """保存对话"""
    save_conversation(req["id"], req.get("title", ""), req.get("messages", []))
    return {"status": "ok"}


@app.delete("/conversations/{conv_id}")
async def delete_conv(conv_id: str):
    """删除对话"""
    delete_conversation(conv_id)
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    """前端页面"""
    return _FRONTEND_HTML.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── 启动命令 ───────────────────────────────────────────────────
# uvicorn api.main:app --reload --port 8000
