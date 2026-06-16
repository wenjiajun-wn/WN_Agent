"""
用户记忆系统
- 短期记忆：对话历史（存内存，SmolAgents 自动维护）
- 长期记忆：用户偏好，持久化到 SQLite
"""
import json
import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./WN.db")
engine  = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base    = declarative_base()


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id    = Column(String, primary_key=True)
    # JSON 字段：存储偏好字典
    preferences = Column(Text, default="{}")
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    title = Column(String, default="")
    messages = Column(Text, default="[]")  # JSON 字符串
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


# ── 对话持久化 ─────────────────────────────────────────────────
def save_conversation(conv_id: str, title: str, messages: list[dict]) -> None:
    """保存或更新对话"""
    with Session() as session:
        conv = session.get(Conversation, conv_id)
        if not conv:
            conv = Conversation(id=conv_id)
            session.add(conv)
        conv.title = title
        conv.messages = json.dumps(messages, ensure_ascii=False)
        session.commit()


def load_conversations() -> list[dict]:
    """加载所有对话（按时间倒序）"""
    with Session() as session:
        rows = session.query(Conversation).order_by(Conversation.created_at.desc()).all()
        return [
            {"id": r.id, "title": r.title, "messages": json.loads(r.messages or "[]")}
            for r in rows
        ]


def delete_conversation(conv_id: str) -> None:
    """删除对话"""
    with Session() as session:
        conv = session.get(Conversation, conv_id)
        if conv:
            session.delete(conv)
            session.commit()


# ── 用户偏好 ───────────────────────────────────────────────────
class UserMemory:
    """用户偏好的 CRUD 操作"""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_preferences(self) -> dict:
        with Session() as session:
            profile = session.get(UserProfile, self.user_id)
            if not profile:
                return {}
            return json.loads(profile.preferences)

    def update_preferences(self, updates: dict) -> None:
        """合并更新偏好，不覆盖已有字段"""
        with Session() as session:
            profile = session.get(UserProfile, self.user_id)
            if not profile:
                profile = UserProfile(user_id=self.user_id)
                session.add(profile)
            prefs = json.loads(profile.preferences or "{}")
            prefs.update(updates)
            profile.preferences = json.dumps(prefs, ensure_ascii=False)
            session.commit()

    def build_system_prompt_suffix(self) -> str:
        """将用户偏好注入 system prompt"""
        prefs = self.get_preferences()
        if not prefs:
            return ""
        lines = ["## 用户偏好（请在回答时参考）"]
        mapping = {
            "food_preference": "饮食偏好",
            "travel_budget":   "旅游预算",
            "dislike":         "不喜欢",
            "city":            "所在城市",
            "language":        "语言偏好",
        }
        for key, label in mapping.items():
            if key in prefs:
                lines.append(f"- {label}：{prefs[key]}")
        # 未知字段也输出
        for key, val in prefs.items():
            if key not in mapping:
                lines.append(f"- {key}：{val}")
        return "\n".join(lines)


# ── 使用示例 ───────────────────────────────────────────────────
"""
mem = UserMemory("user_001")
mem.update_preferences({"food_preference": "喜欢辣食", "travel_budget": "2000元以内"})
print(mem.build_system_prompt_suffix())
"""
