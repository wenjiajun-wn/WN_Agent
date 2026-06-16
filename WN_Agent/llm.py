"""
统一 LLM 接入层
支持 DeepSeek / Qwen / OpenAI,切换只需改 .env
"""
import os
from dotenv import load_dotenv
from smolagents import OpenAIServerModel

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")
MODEL    = os.getenv("LLM_MODEL", "deepseek-v4-pro")

_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "qwen":     "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "openai":   "https://api.openai.com/v1",
}

_API_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen":     "QWEN_API_KEY",
    "openai":   "OPENAI_API_KEY",
}

def get_model() -> OpenAIServerModel:
    """返回配置好的 SmolAgents 模型实例"""
    api_key  = os.getenv(_API_KEY_ENV[PROVIDER], "")
    base_url = _BASE_URLS[PROVIDER]
    # deepseek-v4 系列有 thinking mode，与 tool_choice="required" 冲突
    # tool_choice="auto" 告诉模型"可以调工具但不强制"
    return OpenAIServerModel(
        model_id=MODEL,
        api_base=base_url,
        api_key=api_key,
        tool_choice="auto",
    )
