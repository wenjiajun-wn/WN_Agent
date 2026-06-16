# AI Personal Assistant

基于 SmolAgents 的多 Agent 个人助理，支持天气查询、旅游规划、餐厅推荐、知识问答、待办管理。

## 项目结构

```
ai_assistant/
├── llm.py                    # LLM 统一接入层（DeepSeek/Qwen/OpenAI）
├── agents/
│   ├── manager.py            # Manager Agent（总控）
│   └── sub_agents.py         # 各子 Agent 定义
├── tools/
│   ├── weather.py            # 天气工具（和风天气）
│   ├── map_tool.py           # 地图工具（高德地图）
│   └── search.py             # 联网搜索（DuckDuckGo）
├── memory/
│   └── user_memory.py        # 用户偏好持久化（SQLite）
├── rag/
│   └── knowledge_base.py     # RAG 向量库（Chroma）
├── api/
│   └── main.py               # FastAPI 后端
├── frontend/
│   └── app.py                # Streamlit 前端
├── requirements.txt
└── .env.example
```

## 快速启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env，填入 API Key
```

### 3. 启动后端
```bash
uvicorn api.main:app --reload --port 8000
```

### 4. 启动前端（新终端）
```bash
streamlit run frontend/app.py
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat` | 对话接口 |
| POST | `/upload` | 上传文档入库 |
| POST | `/preferences` | 更新用户偏好 |
| GET  | `/preferences/{user_id}` | 查询用户偏好 |

## 开发路线

- [x] V1：天气 + 搜索 + 基础问答
- [ ] V2：旅游 Agent + 地图工具
- [ ] V3：记忆系统 + 用户偏好
- [ ] V4：RAG 知识库（PDF 问答）
- [ ] V5：外卖/订票执行（需人工确认）
