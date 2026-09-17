"""
collector/naver_web.py
----------------------
네이버 뉴스 전용 수집 및 스크래퍼 모듈.
100% 네이버 뉴스(n.news.naver.com / news.naver.com) 주소를 가진 기사만을 엄격하게 검색·수집합니다.
(PC 검색 403 방지를 위한 모바일 뉴스 검색 자동 폴백 지원)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import requests
from bs4 import BeautifulSoup
from config import PREFERRED_PRESS, EXCLUDE_TITLE_KEYWORDS

PC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def search_naver_news_only(
    query: str,
    target_date: datetime | None = None,
    max_results: int = 8,
) -> list[dict]:
    """
    네이버 검색에서 '네이버뉴스' 인링크(n.news.naver.com)가 제공되는 기사만 선별 수집합니다.
    PC 및 모바일 검색을 결합하여 403 차단 없이 안정적으로 수집합니다.
    """
    if target_date is None:
        target_date = datetime.now() - timedelta(days=1)

    target_date_dot = target_date.strftime("%Y.%m.%d")
    target_date_compact = target_date.strftime("%Y%m%d")
    encoded_query = quote_plus(query)

    # 1. PC 날짜 필터 검색
    url_date_filtered = (
        f"https://search.naver.com/search.naver?where=news&query={encoded_query}"
        f"&sm=tab_opt&sort=1&ds={target_date_dot}&de={target_date_dot}"
        f"&nso=so:dd,p:from{target_date_compact}to{target_date_compact}"
    )

    articles = _fetch_from_url(url_date_filtered, is_mobile=False)

    # 2. 결과가 부족하면 모바일 뉴스 검색으로 수집
    if len(articles) < max_results:
        m_url = f"https://m.search.naver.com/search.naver?where=m_news&query={encoded_query}&sm=mtb_jum&sort=0"
        m_articles = _fetch_from_url(m_url, is_mobile=True)
        seen_urls = {a["link"].split("?")[0] for a in articles}
        for a in m_articles:
            base_url = a["link"].split("?")[0]
            if base_url not in seen_urls:
                seen_urls.add(base_url)
                articles.append(a)
                if len(articles) >= max_results:
                    break

    return articles[:max_results]


def _fetch_from_url(url: str, is_mobile: bool = False) -> list[dict]:
    """주어진 네이버 검색 URL에서 네이버뉴스 인링크 기사들을 정밀 파싱합니다."""
    headers = MOBILE_HEADERS if is_mobile else PC_HEADERS
    try:
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return []
        html = resp.text
    except Exception:
        return []

    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_articles = set()

    # 모든 네이버뉴스 인링크 앵커 탐색 (/article/ 및 /mnews/article/ 모두 지원)
    for a in soup.find_all("a"):
        href = a.get("href", "")
        if "news.naver.com" not in href or "/article/" not in href:
            continue

        base_url = href.split("?")[0]
        if base_url in seen_articles:
            continue

        # 1. 기사 제목 추출
        title = ""
        # 앵커 자체 텍스트 확인 (모바일 검색에서는 앵커 텍스트가 기사 제목)
        txt = a.get_text(strip=True)
        if len(txt) > 8 and "새 창 열림" not in txt and "네이버뉴스" not in txt and "Keep" not in txt:
            title = txt
        else:
            # PC 검색 등 상위 카드 컨테이너에서 제목 탐색
            card = a.find_parent(["li", "div", "article"])
            if card:
                tit_el = card.select_one(".news_tit, a.news_tit, a[class*='tit'], [class*='headline'], strong, h2, h3")
                if tit_el and len(tit_el.get_text(strip=True)) > 8:
                    title = tit_el.get_text(strip=True)

        if not title:
            continue

        # 상업적 광고 키워드 필터링
        if any(bad in title for bad in EXCLUDE_TITLE_KEYWORDS):
            continue

        # 2. 언론사 추출
        press = ""
        card = a.find_parent(["li", "div", "article"])
        if card:
            press_el = card.select_one(
                "a[href*='media.naver.com/press'], a.press, .info_group a, [class*='press'], .source, [class*='source']"
            )
            if press_el:
                press = press_el.get_text(strip=True)

        # 3. 날짜 텍스트 추출
        date_text = ""
        if card:
            date_el = card.select_one(".info_group span.info, span.date, .time, [class*='date']")
            if date_el:
                date_text = date_el.get_text(strip=True)

        seen_articles.add(base_url)
        is_preferred = any(p in press for p in PREFERRED_PRESS) if press else False

        results.append({
            "title": title,
            "link": base_url,
            "naver_link": base_url,
            "source": press or "네이버뉴스",
            "description": "",
            "date_text": date_text,
            "is_preferred": is_preferred,
        })

    return results
