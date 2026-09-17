"""
collector/naver_api.py
----------------------
네이버 클라우드 플랫폼(NCP) NAVER API HUB 뉴스 검색 모듈.
(News_finder.md 7절 규격)
"""

from __future__ import annotations

import html
import re
from typing import Optional
import requests
from config import NCP_CLIENT_ID, NCP_CLIENT_SECRET, NCP_API_URL


def clean_html_tags(text: str) -> str:
    """HTML 태그 및 특수 엔티티를 제거하고 일반 텍스트로 변환합니다."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def search_news_api(query: str, display: int = 10, start: int = 1, sort: str = "date") -> list[dict]:
    """
    NCP 뉴스 검색 API를 호출합니다.
    
    인증 실패(401 등) 또는 네트워크 오류 시 빈 리스트를 반환하며,
    호출부에서 웹 검색(naver_web)으로 안전하게 폴백할 수 있도록 합니다.
    """
    headers = {
        "X-NCP-APIGW-API-KEY-ID": NCP_CLIENT_ID,
        "X-NCP-APIGW-API-KEY": NCP_CLIENT_SECRET,
    }
    params = {
        "query": query,
        "display": min(display, 30),
        "start": start,
        "sort": sort,  # "date" (날짜순) 또는 "sim" (유사도순)
    }

    try:
        resp = requests.get(NCP_API_URL, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            return []
        
        data = resp.json()
        items = data.get("items", [])
        results = []
        for it in items:
            title = clean_html_tags(it.get("title", ""))
            desc = clean_html_tags(it.get("description", ""))
            link = it.get("link", "")
            orig_link = it.get("originallink", "")
            pub_date = it.get("pubDate", "")

            # 네이버뉴스 링크 우선 채택
            target_link = link if "news.naver.com" in link else (orig_link or link)

            results.append({
                "title": title,
                "link": target_link,
                "naver_link": link if "news.naver.com" in link else "",
                "description": desc,
                "pub_date": pub_date,
                "source": "api",
            })
        return results
    except Exception:
        return []
