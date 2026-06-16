"""
地图工具 — 接入高德地图 API
"""
import os
import httpx
from smolagents import tool

API_KEY = os.getenv("AMAP_API_KEY")


@tool
def search_places(keyword: str, city: str) -> str:
    """
    搜索城市内的景点、餐厅、酒店等地点，返回名称、地址和经纬度。

    Args:
        keyword: 搜索关键词，例如 '景点' '川菜餐厅' '酒店'
        city:    城市名称，例如 '台中' '北京'

    Returns:
        地点列表字符串（含经纬度）
    """
    url = "https://restapi.amap.com/v3/place/text"

    with httpx.Client() as client:
        resp = client.get(url, params={
            "key": API_KEY,
            "keywords": keyword,
            "city": city,
            "output": "json",
            "offset": 5,
        })
        data = resp.json()

    if data.get("status") != "1" or not data.get("pois"):
        return f"在 {city} 未找到相关地点：{keyword}"

    lines = [f"📍 {city} · {keyword} 搜索结果：\n"]
    for poi in data["pois"]:
        loc = poi.get("location", "")
        rating = poi.get("biz_ext", {}).get("rating", "N/A")
        lines.append(
            f"  • {poi['name']} | {poi.get('address','')} | 坐标:{loc} | ⭐{rating}"
        )
    return "\n".join(lines)


@tool
def get_coordinates(address: str, city: str = "") -> str:
    """
    将地址转换为经纬度坐标。调用 query_coffee_shops 之前必须先调用此工具获取坐标。

    Args:
        address: 地址名称，例如 '王府井大街' '漕河泾开发区'
        city:    所在城市，例如 '北京' '上海'（可选但推荐填写）

    Returns:
        经度和纬度，格式如 "116.404,39.915"
    """
    full = f"{city}{address}" if city else address
    url = "https://restapi.amap.com/v3/geocode/geo"

    with httpx.Client() as client:
        resp = client.get(url, params={"key": API_KEY, "address": full})
        data = resp.json()

    if data.get("status") != "1" or not data.get("geocodes"):
        return f"未找到「{full}」的坐标，请提供更具体的地址"

    geo = data["geocodes"][0]
    lng, lat = geo["location"].split(",")
    return (
        f"📍 {geo.get('formatted_address', full)}\n"
        f"  经度: {lng}\n"
        f"  纬度: {lat}"
    )


@tool
def get_route(origin: str, destination: str, city: str) -> str:
    """
    规划两地之间的步行/驾车路线。

    Args:
        origin:      出发地名称
        destination: 目的地名称
        city:        所在城市

    Returns:
        路线信息字符串
    """
    api_key = os.getenv("AMAP_API_KEY")
    geocode_url = "https://restapi.amap.com/v3/geocode/geo"
    route_url   = "https://restapi.amap.com/v3/direction/walking"

    def geocode(address: str) -> str | None:
        with httpx.Client() as client:
            resp = client.get(geocode_url, params={"key": api_key, "address": f"{city}{address}"})
            data = resp.json()
        if data.get("status") == "1" and data["geocodes"]:
            return data["geocodes"][0]["location"]
        return None

    o_loc = geocode(origin)
    d_loc = geocode(destination)
    if not o_loc or not d_loc:
        return "无法解析地址，请提供更具体的地点名称"

    with httpx.Client() as client:
        resp = client.get(route_url, params={
            "key": api_key,
            "origin": o_loc,
            "destination": d_loc,
        })
        data = resp.json()

    if data.get("status") != "1":
        return "路线规划失败"

    path = data["route"]["paths"][0]
    distance = int(path["distance"])
    duration = int(path["duration"]) // 60
    return f"🗺️ {origin} → {destination}\n  步行距离：{distance}米，预计 {duration} 分钟"
