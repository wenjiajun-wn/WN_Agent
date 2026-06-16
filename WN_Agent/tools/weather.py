"""
天气工具 — 接入和风天气 API
免费额度：1000次/天，够毕设用
"""
import os
import httpx
from smolagents import tool

# 和风天气 API Host（2025年6月起每人分配专属 Host）
# 可在 https://console.qweather.com/setting 查看
_WEATHER_HOST = os.getenv("WEATHER_API_HOST", "https://devapi.qweather.com")
_GEO_HOST = os.getenv("WEATHER_GEO_HOST", "https://geoapi.qweather.com")


@tool
def get_weather(city: str) -> str:
    """
    查询城市当前天气和未来 3 天预报。

    Args:
        city: 城市名称，例如 '台中' '北京' '上海'

    Returns:
        天气信息字符串
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return "未配置天气 API Key，请在 .env 中设置 WEATHER_API_KEY"

    city_lookup_url = f"{_GEO_HOST}/geo/v2/city/lookup"
    weather_url = f"{_WEATHER_HOST}/v7/weather/3d"

    try:
        with httpx.Client(timeout=15.0) as client:
            # 先查城市 ID
            loc_resp = client.get(city_lookup_url, params={"location": city, "key": api_key})
            loc_data = loc_resp.json()
            if loc_resp.status_code != 200 or loc_data.get("code") != "200":
                # 城市查询失败，尝试用 Bing 搜索替代
                from tools.search import web_search
                search_result = web_search(f"{city} 今天天气 温度 风力")
                return f"⚠️ 天气 API 暂时不可用（错误：{loc_data.get('title', loc_resp.status_code)}），以下为搜索结果：\n{search_result}"

            if not loc_data.get("location"):
                return f"找不到城市：{city}"

            location_id = loc_data["location"][0]["id"]
            city_name = loc_data["location"][0]["name"]

            # 查天气
            weather_resp = client.get(weather_url, params={"location": location_id, "key": api_key})
            data = weather_resp.json()

        if data.get("code") != "200":
            # 天气查询失败，fallback 到搜索
            from tools.search import web_search
            search_result = web_search(f"{city} 今天天气 温度 风力")
            return f"⚠️ 天气 API 暂时不可用（错误：{data.get('title', weather_resp.status_code)}），以下为搜索结果：\n{search_result}"

        daily = data["daily"]
        lines = [f"📍 {city_name} 未来 3 天天气：\n"]
        for day in daily:
            lines.append(
                f"  {day['fxDate']}  {day['textDay']} "
                f"{day['tempMin']}°C ~ {day['tempMax']}°C  "
                f"湿度 {day['humidity']}%"
            )
        return "\n".join(lines)
    except Exception as e:
        # 完全失败时 fallback 到搜索
        try:
            from tools.search import web_search
            return f"⚠️ 天气 API 异常（{e}），以下为搜索结果：\n{web_search(f'{city} 今天天气')}"
        except Exception:
            return f"⚠️ 天气查询失败：{e}，建议使用手机天气 App 查询。"

