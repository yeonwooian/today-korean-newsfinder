"""
collector/news_collector.py
---------------------------
네이버 뉴스(https://n.news.naver.com/mnews/article/...) 전용 통합 수집 모듈.
'오늘도국어' 인스타그램 자동생성 파이프라인 연계를 위해
모든 기사의 원문 링크를 100% 네이버 뉴스 URL로만 엄격하게 수집·검증 및 표준화합니다.
"""

from __future__ import annotations

import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from config import NEWS_CATEGORIES, get_default_target_date, PREFERRED_PRESS
from collector.naver_web import search_naver_news_only
from collector.article_parser import fetch_article_text

NAVER_ARTICLE_REGEX = re.compile(r"/article/([0-9]{3})/([0-9]{10})")


def normalize_to_n_news_url(url: str) -> str | None:
    """
    네이버 뉴스 URL에서 언론사코드(oid)와 기사번호(aid)를 추출하여
    표준 'https://n.news.naver.com/mnews/article/{oid}/{aid}' 주소로 정규화합니다.
    네이버 뉴스 기사 링크가 아니면 None을 반환합니다.
    """
    if not url or ("news.naver.com" not in url and "naver.com" not in url):
        return None

    match = NAVER_ARTICLE_REGEX.search(url)
    if match:
        oid, aid = match.group(1), match.group(2)
        return f"https://n.news.naver.com/mnews/article/{oid}/{aid}"

    if "news.naver.com" in url and "/article/" in url:
        clean_url = url.split("?")[0]
        if "n.news.naver.com" not in clean_url:
            clean_url = clean_url.replace("news.naver.com", "n.news.naver.com")
            clean_url = clean_url.replace("m.news.naver.com", "n.news.naver.com")
        return clean_url

    return None


def collect_news_by_category(
    category_id: str,
    target_date: datetime | None = None,
    max_per_category: int = 5,
) -> list[dict]:
    """
    특정 카테고리(A, B, C, D)의 네이버 뉴스 기사들을 수집하고 중복을 제거합니다.
    반드시 https://n.news.naver.com/... URL만 선별합니다.
    """
    cat_info = NEWS_CATEGORIES.get(category_id)
    if not cat_info:
        return []

    keywords = cat_info["keywords"]
    collected = []
    seen_urls = set()

    # 상위 3개 핵심 키워드로 네이버 뉴스 검색 수행
    queries_to_run = keywords[:3]

    for q in queries_to_run:
        results = search_naver_news_only(q, target_date=target_date, max_results=5)

        for item in results:
            raw_url = item.get("link", "")
            std_url = normalize_to_n_news_url(raw_url)
            if not std_url:
                continue

            if std_url in seen_urls:
                continue
            seen_urls.add(std_url)

            item["link"] = std_url
            item["naver_link"] = std_url
            item["category_id"] = category_id
            item["category_name"] = cat_info["name"]
            collected.append(item)

    return collected[:max_per_category]


def collect_all_categories(
    target_date: datetime | None = None,
    max_per_category: int = 4,
    fetch_full_text: bool = True,
) -> dict[str, list[dict]]:
    """
    4대 카테고리(A, B, C, D) 전체에서 네이버 뉴스만을 수집하고,
    기사 상세 메타데이터 및 발췌 본문을 병렬 추출합니다.
    """
    if target_date is None:
        target_date = get_default_target_date()

    target_date_str = target_date.strftime("%Y.%m.%d")
    all_results: dict[str, list[dict]] = {}

    # 1. 4대 카테고리 순회 수집
    for cat_id in ["A", "B", "C", "D"]:
        cat_news = collect_news_by_category(
            cat_id, target_date=target_date, max_per_category=max_per_category
        )
        all_results[cat_id] = cat_news

    # 2. 기사 페이지에서 상세 메타데이터 및 본문 병렬 추출
    if fetch_full_text:
        articles_to_fetch = []
        for cat_id, items in all_results.items():
            for item in items:
                articles_to_fetch.append(item)

        def _fetch_one(item):
            url = item.get("link")
            if url and "n.news.naver.com" in url:
                try:
                    parsed = fetch_article_text(url)
                    if parsed.get("success"):
                        if parsed.get("title"):
                            item["title"] = parsed["title"]
                        if parsed.get("source"):
                            item["source"] = parsed["source"]
                        if parsed.get("published_date"):
                            item["published_date"] = parsed["published_date"]
                        item["full_text"] = parsed.get("text", "")[:1500]
                    else:
                        item["full_text"] = item.get("description", "")
                except Exception:
                    item["full_text"] = item.get("description", "")
            else:
                item["full_text"] = item.get("description", "")

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(_fetch_one, articles_to_fetch))

    # 3. D-1 날짜 일치 여부 및 신뢰 언론사 우선 정렬
    for cat_id in all_results:
        items = all_results[cat_id]
        valid_items = [it for it in items if it.get("link", "").startswith("https://n.news.naver.com")]
        for item in valid_items:
            pdate = item.get("published_date", "")
            item["is_target_date"] = target_date_str in pdate
            item["is_preferred"] = any(p in item.get("source", "") for p in PREFERRED_PRESS)

        valid_items.sort(
            key=lambda x: (
                not x.get("is_target_date", False),
                not x.get("is_preferred", False),
            )
        )
        all_results[cat_id] = valid_items

    return all_results
