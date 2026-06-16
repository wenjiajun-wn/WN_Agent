"""
子 Agent 定义
每个 Agent 配备专属工具，职责单一
"""
from smolagents import CodeAgent, ToolCallingAgent

from llm import get_model
from tools.weather  import get_weather
from tools.map_tool import search_places, get_route, get_coordinates
from tools.search   import web_search
from tools.coffee   import (
    query_coffee_shops,
    search_coffee_products,
    query_coffee_product_detail,
    switch_coffee_product,
    preview_coffee_order,
    create_coffee_order,
    query_coffee_order,
    cancel_coffee_order,
)
from rag.knowledge_base import rag_retrieve


def build_weather_agent() -> CodeAgent:
    return CodeAgent(
        tools=[get_weather],
        model=get_model(),
        name="weather_agent",
        description="负责查询天气预报和出行天气建议。用户询问天气、是否适合出行时调用。",
    )


def build_travel_agent() -> CodeAgent:
    return CodeAgent(
        tools=[search_places, get_route, get_weather, web_search],
        model=get_model(),
        name="travel_agent",
        description="负责旅游路线规划、景点推荐、酒店搜索、交通路线查询。用户提到旅游、出行、玩哪里时调用。",
    )


def build_food_agent() -> CodeAgent:
    return CodeAgent(
        tools=[search_places, web_search],
        model=get_model(),
        name="food_agent",
        description="负责餐厅推荐、美食搜索。用户询问吃什么、推荐餐厅、附近美食时调用。不处理咖啡点单。",
        instructions=(
            '你是专业的美食推荐助手。\n'
            '1. 用 search_places 搜索附近餐厅（city填城市，keyword填菜系或餐厅类型）；\n'
            '2. 结果不够时用 web_search 补充；\n'
            '3. 整理成简洁列表，推荐最好的 3 家；\n'
            '4. 不要重复搜索相同内容。'
        ),
    )


def build_coffee_agent() -> ToolCallingAgent:
    return ToolCallingAgent(
        tools=[
            get_coordinates,
            query_coffee_shops,
            search_coffee_products,
            query_coffee_product_detail,
            switch_coffee_product,
            preview_coffee_order,
            create_coffee_order,
            query_coffee_order,
            cancel_coffee_order,
        ],
        model=get_model(),
        max_steps=6,
        name="coffee_agent",
        description="负责瑞幸咖啡点单。用户提到咖啡、拿铁、美式、生椰、瑞幸、点饮品、买咖啡时调用。",
        instructions=(
            '你是瑞幸咖啡点单助手。流程如下，直接连续调用工具，中间不要输出任何文字：\n'
            '\n'
            '1. get_coordinates → 获取经纬度\n'
            '2. query_coffee_shops → 展示附近门店（选第一家/最近的）\n'
            '3. search_coffee_products → 搜索饮品\n'
            '4. preview_coffee_order → 确认价格（product_list 格式: [{"productId": 4805, "skuCode": "SP3225-00147", "amount": 1}]）\n'
            '5. create_coffee_order → 下单（传 product_list + longitude + latitude）\n'
            '\n'
            '规则：\n'
            '- 连续调工具，不要停顿。只有下单成功或真正出错才输出文字。\n'
            '- 调用 create_coffee_order 之前不要输出任何内容。\n'
            '- 默认规格：大杯、冰、标准甜，不要确认。\n'
            '- 自动选最近的门店。\n'
            '- query_coffee_product_detail 和 query_coffee_order 只在用户明确要求时调用。\n'
            '- 下单成功后一句话返回结果（订单ID + 门店 + 商品）。'
        ),
    )


def build_qa_agent() -> CodeAgent:
    return CodeAgent(
        tools=[web_search, rag_retrieve],
        model=get_model(),
        name="qa_agent",
        description="负责百科知识问答、概念解释、查询用户已上传的文档资料。涉及天气/出行/美食/咖啡/待办时不要调用。",
    )


def build_todo_agent() -> CodeAgent:
    from smolagents import tool

    @tool
    def format_todo(task: str, deadline: str = "") -> str:
        """
        格式化并记录一条待办事项。

        Args:
            task:     任务描述
            deadline: 截止时间（可选），格式 'YYYY-MM-DD'

        Returns:
            格式化后的待办字符串
        """
        deadline_str = f"  📅 截止：{deadline}" if deadline else ""
        return f"✅ 已记录：{task}{deadline_str}\n（提示：接入日历 API 后可自动同步）"

    return CodeAgent(
        tools=[format_todo],
        model=get_model(),
        name="todo_agent",
        description="负责管理待办事项、提醒事项、日程安排。用户提到提醒、记录任务、安排日程时调用。",
    )
