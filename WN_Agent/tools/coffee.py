"""瑞幸咖啡 MCP 工具集 — 门店查询、商品搜索、下单"""
import requests
import json
import os
from smolagents import tool

MCP_URL = "https://gwmcp.lkcoffee.com/order/user/mcp"
TOKEN = os.getenv("LUCKIN_MCP_TOKEN")
if not TOKEN:
    raise RuntimeError("请在 .env 中设置 LUCKIN_MCP_TOKEN")
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {TOKEN}",
}
NO_PROXY = {"http": "", "https": ""}


def _call_mcp(tool_name: str, arguments: dict) -> dict:
    """调用瑞幸 MCP 工具，返回解析后的 data 字段"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
        resp = requests.post(MCP_URL, headers=HEADERS, json=payload, timeout=20, proxies=NO_PROXY)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            return {"success": False, "msg": str(result["error"])}
        content = result.get("result", {}).get("content", [])
        if content and content[0].get("type") == "text":
            return json.loads(content[0]["text"])
        return {"success": False, "msg": "empty response"}
    except Exception as e:
        return {"success": False, "msg": str(e)}


def _fmt_price(price: float) -> str:
    """格式化价格"""
    return f"¥{price:.2f}" if price else "价格待查"


@tool
def query_coffee_shops(longitude: float, latitude: float, name: str = "") -> str:
    """
    查询附近的瑞幸咖啡门店列表。需要提供经纬度坐标。

    Args:
        longitude: 经度（高德/GCJ-02 坐标系）
        latitude:  纬度（高德/GCJ-02 坐标系）
        name:      门店名称关键词（可选）

    Returns:
        门店列表,包含门店ID、名称、地址、营业时间、距离
    """
    args = {"longitude": longitude, "latitude": latitude}
    if name:
        args["deptName"] = name
    res = _call_mcp("queryShopList", args)
    if not res.get("success"):
        return f"查询门店失败: {res.get('msg')}"

    shops = res.get("data", [])
    if not shops:
        return f"附近暂未找到瑞幸咖啡门店"

    lines = [f"📍 附近瑞幸咖啡门店 ({len(shops)}家，显示最近3家):"]
    for s in shops[:3]:
        status = s.get("workStatus", "")
        distance = s.get("distance", 0)
        lines.append(
            f"  ID:{s['deptId']} | {s['deptName']} | {s.get('address','')} | "
            f"{s.get('workTimeStart','')}-{s.get('workTimeEnd','')} | "
            f"{'🟢' if status == '营业中' else '🔴'}{status} | {distance:.0f}km"
        )
    return "\n".join(lines)


@tool
def search_coffee_products(dept_id: int, query: str) -> str:
    """
    在瑞幸门店搜索可购买的商品。

    Args:
        dept_id: 门店ID(从 query_coffee_shops 返回结果中获取）
        query:   搜索关键词，如 "拿铁"、"生椰"、"美式"

    Returns:
        匹配的商品列表,含商品ID、名称、SKU编码、价格、可选规格
    """
    res = _call_mcp("searchProductForMcp", {"deptId": dept_id, "query": query})
    if not res.get("success"):
        return f"搜索商品失败: {res.get('msg')}"

    products = res.get("data", [])
    if not products:
        return f"门店 {dept_id} 未找到「{query}」相关商品"

    lines = [f"☕ 搜索「{query}」结果 ({len(products)}款):"]
    for p in products[:8]:
        min_price = p.get("minPrice", "")
        price_str = _fmt_price(min_price) if min_price else _fmt_price(0)
        sku = p.get("skuCode", "")
        lines.append(
            f"  ID:{p['productId']} | {p['productName']} | {price_str} | SKU:{sku}"
        )
        attrs = p.get("productAttrs", [])
        for attr in attrs[:3]:
            sub_names = [s['attributeName'] for s in attr.get("productSubAttrs", [])]
            lines.append(f"    {attr['attributeName']}: {' / '.join(sub_names)}")
    return "\n".join(lines)


@tool
def query_coffee_product_detail(dept_id: int, product_id: int) -> str:
    """
    查询瑞幸商品详细信息（规格、价格等）。

    Args:
        dept_id:    门店ID
        product_id: 商品ID(从 search_coffee_products 返回结果中获取）

    Returns:
        商品详情，含完整规格列表和价格
    """
    res = _call_mcp("queryProductDetailInfo", {"deptId": dept_id, "productId": product_id})
    if not res.get("success"):
        return f"查询商品详情失败: {res.get('msg')}"

    p = res.get("data", {})
    if not p:
        return f"未找到商品 {product_id} 的详情"

    lines = [
        f"📋 {p.get('productName', '商品详情')}",
        f"  商品ID: {p.get('productId')}",
        f"  SKU: {p.get('skuCode', '')}",
    ]
    for attr in p.get("productAttrs", []):
        subs = []
        for s in attr.get("productSubAttrs", []):
            price_tag = f" (+{_fmt_price(s['price'])})" if s.get("price") else ""
            subs.append(f"{s['attributeName']}{price_tag}")
        lines.append(f"  {attr['attributeName']}: {' | '.join(subs)}")
    return "\n".join(lines)


def _parse_product_list(product_list):
    """解析 product_list，兼容 list 和 JSON 字符串两种格式"""
    if isinstance(product_list, list):
        return product_list
    if isinstance(product_list, str):
        try:
            return json.loads(product_list)
        except json.JSONDecodeError:
            return None
    return None


@tool
def preview_coffee_order(dept_id: int, product_list: list) -> str:
    """
    预览瑞幸订单（计算价格、可用优惠券等），下单前必须先调用此工具确认。

    Args:
        dept_id:      门店ID
        product_list: 商品列表，格式为 list，每项含 productId、skuCode、amount。
                      示例: [{"productId": 4805, "skuCode": "SP3225-00147", "amount": 1}]

    Returns:
        订单预览，含商品明细、金额、可用优惠券
    """
    items = _parse_product_list(product_list)
    if items is None:
        return "参数 product_list 格式错误，应为 list，如 [{\"productId\": 4805, \"skuCode\": \"SP3225-00147\", \"amount\": 1}]"

    res = _call_mcp("previewOrder", {"deptId": dept_id, "productList": items})
    if not res.get("success"):
        return f"订单预览失败: {res.get('msg')}"

    data = res.get("data", {})
    lines = [f"🧾 订单预览 | 门店: {dept_id}"]
    for item in data.get("productList", []):
        lines.append(
            f"  {item.get('productName','')} x{item.get('amount',1)} "
            f" {_fmt_price(item.get('totalPrice', item.get('price', 0)))}"
        )
    lines.append(f"  合计: {_fmt_price(data.get('totalAmount', 0))}")
    coupons = data.get("couponCodeList", [])
    if coupons:
        lines.append(f"  可用优惠券: {', '.join(coupons[:5])}")
    else:
        lines.append("  暂无可用优惠券")
    return "\n".join(lines)


@tool
def create_coffee_order(dept_id: int, product_list: list,
                        longitude: float, latitude: float,
                        coupon_code_list: list = None, remark: str = "") -> str:
    """
    正式创建瑞幸咖啡订单。必须在调用 preview_coffee_order 确认价格后才能调用。

    Args:
        dept_id:          门店ID
        product_list:     商品列表，格式同 preview_coffee_order
        longitude:        经度
        latitude:         纬度
        coupon_code_list: 优惠券编码列表，如 ["code1","code2"]（可选）
        remark:           订单备注（可选）

    Returns:
        订单创建结果,含订单ID
    """
    items = _parse_product_list(product_list)
    if items is None:
        return "参数 product_list 格式错误，应为 list"

    args = {
        "deptId": dept_id,
        "productList": items,
        "longitude": longitude,
        "latitude": latitude,
    }
    if coupon_code_list:
        coupons = _parse_product_list(coupon_code_list)
        if coupons is None:
            return "参数 coupon_code_list 格式错误"
        args["couponCodeList"] = coupons
    if remark:
        args["remark"] = remark

    res = _call_mcp("createOrder", args)
    if not res.get("success"):
        return f"创建订单失败: {res.get('msg')}"

    data = res.get("data", {})
    order_id = data.get("orderId", "未知")
    return (
        f"✅ 订单创建成功！\n"
        f"  订单ID: {order_id}\n"
        f"  金额: {_fmt_price(data.get('totalAmount', 0))}\n"
        f"  状态: {data.get('orderStatus', '处理中')}\n"
        f"  可用 query_coffee_order({order_id}) 查询订单状态"
    )


@tool
def query_coffee_order(order_id: str) -> str:
    """
    查询瑞幸订单状态。

    Args:
        order_id: 订单ID（从 create_coffee_order 返回结果中获取）

    Returns:
        订单详情，含状态、商品列表、金额
    """
    res = _call_mcp("queryOrderDetailInfo", {"orderId": order_id})
    if not res.get("success"):
        return f"查询订单失败: {res.get('msg')}"

    data = res.get("data", {})
    lines = [
        f"📋 订单详情",
        f"  订单ID: {order_id}",
        f"  状态: {data.get('orderStatus', '未知')}",
        f"  金额: {_fmt_price(data.get('totalAmount', 0))}",
    ]
    return "\n".join(lines)


@tool
def cancel_coffee_order(order_id: str) -> str:
    """
    取消瑞幸订单。

    Args:
        order_id: 订单ID（从 create_coffee_order 返回结果中获取）

    Returns:
        取消结果
    """
    res = _call_mcp("cancelOrder", {"orderId": order_id})
    if not res.get("success"):
        return f"取消订单失败: {res.get('msg')}"
    return f"✅ 订单 {order_id} 已取消"


@tool
def switch_coffee_product(dept_id: int, product_id: int, sku_code: str,
                          attr_id: int, sub_attr_id: int, operation: int = 1,
                          amount: int = 1) -> str:
    """
    切换瑞幸咖啡商品的规格属性（杯型、温度、糖度等），返回新的 SKU。
    一般在 preview_coffee_order 之前调用，确保规格正确。

    Args:
        dept_id:      门店ID
        product_id:   商品ID
        sku_code:     当前 SKU 编码
        attr_id:      一级属性ID，如 "杯型" 的 attributeId
        sub_attr_id:  二级属性ID，如 "大杯" 的 attributeId
        operation:    操作类型，1=选择该属性（默认）
        amount:       商品数量（默认 1）

    Returns:
        切换后的商品信息，含新 SKU
    """
    args = {
        "deptId": dept_id,
        "productId": product_id,
        "skuCode": sku_code,
        "attrOperationParam": {
            "attributeId": attr_id,
            "subAttr": {
                "attributeId": sub_attr_id,
                "operation": operation,
            },
        },
        "amount": amount,
    }
    res = _call_mcp("switchProduct", args)
    if not res.get("success"):
        return f"规格切换失败: {res.get('msg')}"

    data = res.get("data", {})
    return (
        f"🔄 规格已切换\n"
        f"  商品: {data.get('productName', '')}\n"
        f"  新SKU: {data.get('skuCode', '')}\n"
        f"  价格: {_fmt_price(data.get('minPrice', 0))}"
    )
