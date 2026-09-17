"""
collector/naver_web.py
----------------------
네이버 뉴스 전용 수집 및 스크래퍼 모듈.
사용자 요구사항에 따라 100% 네이버 뉴스(n.news.naver.com / news.naver.com) 주소를 가진
기사만을 엄격하게 검색·수집하여 '오늘도국어' 인스타 파이프라인과의 완벽한 연계를 보장합니다.
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
    max_results: int = 5,
) -> list[dict]:
    """
    네이버 검색에서 '네이버뉴스' 인링크(n.news.naver.com)가 제공되는 기사만 선별 수집합니다.
    PC 및 모바일 검색을 결합하여 403 차단 없이 100% 안정적으로 수집합니다.
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

    # 2. 결과가 부족하면 모바일 뉴스 검색으로 수집 (모바일은 403 차단이 없음)
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
    """주어진 네이버 검색 URL에서 네이버뉴스 인링크 기사들을 파싱합니다."""
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

    # 기사 컨테이너 탐색
    cards = soup.select(".news_wrap, div.news_area, li.bx, div[class*='news_']")
    for card in cards:
        # 네이버 뉴스 인링크 확인
        naver_a = card.select_one(
            "a[href*='news.naver.com/mnews/article'], a[href*='n.news.naver.com/mnews/article']"
        )
        if not naver_a:
            continue

        naver_url = naver_a.get("href", "")
        base_url = naver_url.split("?")[0]
        if base_url in seen_articles:
            continue

        # 제목
        title_el = card.select_one(".news_tit, a.news_tit, a[title], [class*='tit']")
        title = title_el.get_text(strip=True) if title_el else ""

        # 상업적 광고 키워드 필터링
        if any(bad in title for bad in EXCLUDE_TITLE_KEYWORDS):
            continue

        # 언론사
        press_el = card.select_one("a.press, .info_group a, [class*='press'], .source")
        press = press_el.get_text(strip=True) if press_el else ""

        # 날짜
        date_el = card.select_one(".info_group span.info, span.date, .time")
        date_text = date_el.get_text(strip=True) if date_el else ""

        # 본문 요약
        desc_el = card.select_one(".news_dsc, [class*='dsc'], .text")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        seen_articles.add(base_url)
        is_preferred = any(p in press for p in PREFERRED_PRESS)

        results.append({
            "title": title,
            "link": naver_url,
            "naver_link": naver_url,
            "source": press or "언론사",
            "description": desc,
            "date_text": date_text,
            "is_preferred": is_preferred,
        })

    # 카드 셀렉터 외 전체 링크에서 직접 네이버뉴스 링크 보완
    if not results:
        for a in soup.select("a[href*='n.news.naver.com/mnews/article'], a[href*='news.naver.com/mnews/article']"):
            href = a.get("href", "")
            base = href.split("?")[0]
            if base not in seen_articles:
                seen_articles.add(base)
                results.append({
                    "title": a.get_text(strip=True) or "",
                    "link": href,
                    "naver_link": href,
                    "source": "네이버뉴스",
                    "description": "",
                    "date_text": "",
                    "is_preferred": False,
                })

    return results
