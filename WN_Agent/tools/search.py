"""
搜索工具 — 使用 Bing（国内可访问，免费无需 API Key）
"""
import re
import httpx
from smolagents import tool

_BING_URL = "https://cn.bing.com/search"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _parse_results(html: str, limit: int = 5) -> list[str]:
    """从 Bing 搜索结果页 HTML 中提取标题、URL 和摘要"""
    results = []
    blocks = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)
    for block in blocks:
        if len(results) >= limit:
            break
        # 跳过没有 b_tpcn 的块（CSS 模板等）
        if "b_tpcn" not in block:
            continue
        # 提取标题（aria-label 属性）
        title_match = re.search(r'aria-label="([^"]+)"', block)
        title = title_match.group(1) if title_match else ""
        # 提取 URL
        url_match = re.search(r'<a class="tilk"[^>]*href="([^"]+)"', block)
        url = url_match.group(1) if url_match else ""
        # 提取摘要段落
        snippet_match = re.search(r'<p[^>]*>(.*?)</p>', block, re.DOTALL)
        snippet = re.sub(r'<[^>]+>', "", snippet_match.group(1)) if snippet_match else ""
        snippet = snippet.strip()
        title = title.strip()
        if title:
            line = f"  • {title}\n    {url}"
            if snippet:
                line += f"\n    {snippet}"
            results.append(line)
    return results


@tool
def web_search(query: str) -> str:
    """
    搜索互联网获取最新信息（使用 Bing 搜索引擎）。

    Args:
        query: 搜索关键词

    Returns:
        搜索结果摘要
    """
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(_BING_URL, params={"q": query, "setlang": "zh"}, headers=_HEADERS)
            resp.raise_for_status()
    except Exception:
        return (
            "⚠️ 网络搜索暂时不可用（Bing 连接失败）。"
            "请根据已有知识回答问题，或建议用户自行搜索。"
        )

    results = _parse_results(resp.text)
    if not results:
        return f"未找到关于 '{query}' 的相关结果，建议换个关键词或自行搜索。"

    return f"🔍 '{query}' 搜索结果：\n" + "\n".join(results)
