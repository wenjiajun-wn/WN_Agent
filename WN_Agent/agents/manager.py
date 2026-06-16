"""
Manager Agent — 总控 Agent
负责意图识别 + 任务路由 + 结果汇总
集成三层记忆 + 三层推理：思维链 / 自我反思 / 树状搜索
"""
import re
from smolagents import CodeAgent

from llm import get_model
from agents.sub_agents import (
    build_weather_agent,
    build_travel_agent,
    build_food_agent,
    build_coffee_agent,
    build_qa_agent,
    build_todo_agent,
)
from memory.user_memory import UserMemory
from memory.long_term import recall, remember, summarize_and_remember

# ── 中断信号 ──────────────────────────────────────────────────
_cancel_signals: dict[str, bool] = {}


def request_cancel(user_id: str) -> None:
    """标记用户请求需要中断"""
    _cancel_signals[user_id] = True


def _clear_cancel(user_id: str) -> None:
    """清除中断标记"""
    _cancel_signals.pop(user_id, None)


def _make_cancel_check(user_id: str):
    """生成 step callback：每步执行前检查是否被取消"""

    def check(*args, **kwargs):
        if _cancel_signals.get(user_id):
            _clear_cancel(user_id)
            raise RuntimeError("用户中断了本次对话")

    return check


def _compress_history(history: list[dict]) -> str:
    """
    工作记忆管理：压缩过长的对话历史。
    保留最近 8 轮，更早的用摘要替代。
    """
    if len(history) <= 16:
        lines = []
        for m in history[-8:]:
            role = "用户" if m["role"] == "user" else "助手"
            lines.append(f"{role}: {m['content'][:500]}")
        return "## 对话历史\n" + "\n".join(lines)

    # 压缩早期消息
    older = history[:-8]
    recent = history[-8:]
    summary = "早期对话摘要：" + "；".join(
        f"{'用户' if m['role'] == 'user' else '助手'}说: {m['content'][:60]}"
        for m in older[-6:]
    )
    lines = [summary, ""]
    for m in recent:
        role = "用户" if m["role"] == "user" else "助手"
        lines.append(f"{role}: {m['content'][:500]}")
    return "## 对话历史（已压缩）\n" + "\n".join(lines)


def build_manager(user_id: str = "default", long_term_context: str = "") -> CodeAgent:
    """
    构建带有三层记忆的 Manager Agent。

    Args:
        user_id: 当前用户 ID
        long_term_context: 从长期记忆中检索到的相关内容
    """
    mem = UserMemory(user_id)
    pref_prompt = mem.build_system_prompt_suffix()

    memory_section = ""
    if long_term_context:
        memory_section = (
            "## 长期记忆（跨会话回忆）\n"
            "以下是用户之前提到过的重要信息，请优先参考：\n"
            f"{long_term_context}\n"
        )

    system_prompt = f"""
你是一个主动型智能个人助理。核心原则：**不要当问答机器人，要像真人助理一样理解和行动。**

## 上下文理解（最重要）
- 用户说"第一个""好的""选A"等简短回复 → **必须对照对话历史理解**，你上次列出了什么选项
- 用户提供的信息（地址、偏好、预算）都是线索，**立刻结合对话历史推断真实需求**
- 用户说"我家在XX"然后说"帮我点外卖"→ 自动用XX地址搜附近外卖，不要反问地址
- 用户说"帮我查天气"前面提过城市 → 直接查那个城市，不要反问
- **禁止反复确认已知信息**，除非真的模糊不清
- 对话历史中的信息优先使用

## 能力范围
- 查询天气 → weather_agent
- 规划旅游路线和景点推荐 → travel_agent
- 推荐餐厅 → food_agent
- 瑞幸咖啡点单 → coffee_agent（查门店 → 搜饮品 → 确认 → 下单）
- 知识问答和文档检索 → qa_agent
- 管理待办事项和日程 → todo_agent

## 重要规则
- 咖啡/饮品/瑞幸相关 → **只调 coffee_agent，不要调 todo_agent 或其他 agent**
- 咖啡点单失败时如实告知用户，**禁止用 todo_agent 创建待办作为替代**
- 多领域任务同时调用多个 Agent 并汇总
- 只调与用户需求相关的 agent，不要画蛇添足

{memory_section}
{pref_prompt}
"""

    manager = CodeAgent(
        tools=[],
        model=get_model(),
        managed_agents=[
            build_weather_agent(),
            build_travel_agent(),
            build_food_agent(),
            build_coffee_agent(),
            build_qa_agent(),
            build_todo_agent(),
        ],
        instructions=system_prompt,
        max_steps=3,
        step_callbacks=[_make_cancel_check(user_id)],
    )
    return manager


# ── 自我反思 ──────────────────────────────────────────────────
def _reflect_and_refine(user_input: str, first_answer: str, model) -> str:
    """
    对 Agent 的回答进行自我反思，评分并优化。
    评分 < 8 时自动改进。
    """
    reflect_prompt = (
        "你是一个严格的评审。请对以下回答评分（1-10分），评估标准：\n"
        "1. 是否准确回答了问题？\n"
        "2. 信息是否具体、有用？\n"
        "3. 逻辑是否清晰？\n"
        "4. 有没有遗漏或编造？\n\n"
        f"【用户问题】{user_input}\n\n"
        f"【当前回答】{first_answer}\n\n"
        "请先打分（格式：评分：X/10），再给出改进建议。\n"
        "如果评分 >= 8，在建议开头写「通过」。\n"
        "如果评分 < 8，在建议开头写「需改进」，然后给出优化后的完整回答。"
    )
    try:
        resp = model.client.chat.completions.create(
            model=model.model_id,
            messages=[{"role": "user", "content": reflect_prompt}],
            temperature=0.3,
            max_tokens=600,
        )
        review = resp.choices[0].message.content.strip()
    except Exception:
        return first_answer

    # 通过则原样返回
    score_match = re.search(r"评分[：:]\s*(\d+)", review)
    if score_match and int(score_match.group(1)) >= 8:
        return first_answer

    # 需改进：提取优化后的回答
    if score_match or "需改进" in review:
        improved = re.split(
            r"优化后[的答回]*[：:]|改进后[的答回]*[：:]|完整回答[：:]",
            review, maxsplit=1,
        )
        if len(improved) > 1 and len(improved[1].strip()) > 20:
            return improved[1].strip()

    return first_answer


def _is_complex_query(user_input: str) -> bool:
    """判断是否需要树状搜索"""
    markers = ["比较", "对比", "分析", "规划", "攻略", "方案", "推荐", "优缺点", "哪个好", "怎么选"]
    return len(user_input) > 80 and any(m in user_input for m in markers)


def _tree_think(user_input: str, user_id: str, long_term_context: str, model) -> str:
    """
    树状搜索：两路推理，选优。
    路径 A：直接分析    路径 B：拆成子问题分步解
    """
    # 路径 A
    try:
        mgr_a = build_manager(user_id, long_term_context)
        result_a = str(mgr_a.run(user_input))
    except RuntimeError:
        return None

    # 拆解子问题
    try:
        resp = model.client.chat.completions.create(
            model=model.model_id,
            messages=[{"role": "user", "content": f"将以下问题拆解为 2-3 个子问题：\n{user_input}"}],
            temperature=0.3, max_tokens=200,
        )
        sub_tasks = resp.choices[0].message.content.strip()
    except Exception:
        return result_a

    # 路径 B
    try:
        mgr_b = build_manager(user_id, long_term_context)
        result_b = str(mgr_b.run(f"按以下步骤分步解决：\n{sub_tasks}\n\n原始问题：{user_input}"))
    except RuntimeError:
        return result_a

    # 比较选优
    try:
        resp = model.client.chat.completions.create(
            model=model.model_id,
            messages=[{"role": "user", "content": (
                f"【问题】{user_input}\n【回答A】{result_a[:500]}\n【回答B】{result_b[:500]}\n"
                "哪个更好？输出更好的完整回答。"
            )}],
            temperature=0.3, max_tokens=600,
        )
        chosen = resp.choices[0].message.content.strip()
        clean = re.split(r"更好[的]*[回答答案][：:]", chosen, maxsplit=1)
        return clean[1].strip() if len(clean) > 1 and len(clean[1].strip()) > 20 else chosen
    except Exception:
        return result_a


# ── 单次对话入口 ───────────────────────────────────────────────
def chat(user_input: str, user_id: str = "default", history: list[dict] | None = None) -> str:
    """
    处理一条用户消息。
    三层记忆 + 三层推理：
      记忆：长期检索 → 工作压缩 → 情景存储
      推理：思维链(system prompt) → 树状搜索(复杂问题) → 自我反思(输出审查)
    """
    _clear_cancel(user_id)
    model = get_model()
    original_input = user_input

    # ① 长期记忆检索
    memories = recall(user_id, user_input, n=5)
    long_term_context = "\n".join(f"- {m}" for m in memories) if memories else ""

    # ② 工作记忆压缩
    history_context = _compress_history(history) if history else ""
    if history_context:
        user_input = f"{history_context}\n\n## 当前问题\n用户: {user_input}"

    # ③ Agent 执行（复杂问题走树状搜索）
    try:
        if _is_complex_query(original_input):
            reply = _tree_think(user_input, user_id, long_term_context, model)
            if reply is None:
                return "⏹️ 用户已中断本次对话。"
        else:
            manager = build_manager(user_id, long_term_context)
            reply = str(manager.run(user_input))
    except RuntimeError:
        return "⏹️ 用户已中断本次对话。"

    # ④ 自我反思
    reply = _reflect_and_refine(original_input, reply, model)

    # ⑤ 情景记忆存储
    all_msgs = (history or []) + [
        {"role": "user", "content": original_input},
        {"role": "assistant", "content": reply},
    ]
    try:
        summarize_and_remember(user_id, all_msgs, model)
    except Exception:
        pass

    return reply
