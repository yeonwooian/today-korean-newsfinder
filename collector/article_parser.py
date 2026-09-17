"""
collector/article_parser.py
---------------------------
네이버 뉴스 기사 페이지 및 언론사 원문 파서.
제목, 언론사, 발행일시, 본문 텍스트를 정밀 추출합니다.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

ARTICLE_BODY_SELECTORS = [
    "#dic_area",
    "#articleBodyContents",
    "#newsct_article",
    "#articeBody",
    ".article_body",
    "#article_body",
    ".article-body",
    "#articleText",
    ".content_area",
]

TITLE_SELECTORS = [
    "#title_area span",
    "h2#title_area",
    "h3#articleTitle",
    "h2.media_end_head_headline",
    "h1.headline",
    "h1.title",
]

DATE_SELECTORS = [
    "span.media_end_head_info_datestamp_time",
    ".article_info .t11",
    "span._ARTICLE_DATE_TIME",
    ".date_time",
    ".byline_date",
]

PRESS_LOGO_SELECTORS = [
    "img.media_end_head_top_logo_img",
    ".press_logo img",
    ".media_end_head_top_channel_layer_name",
]


def fetch_article_text(url: str, timeout: int = 10) -> dict:
    """
    주어진 URL의 웹페이지를 가져와 기사 메타데이터와 본문 텍스트를 반환합니다.
    실패 시 기본 메타데이터 및 빈 텍스트를 반환합니다.
    """
    result = {
        "url": url,
        "title": "",
        "source": "",
        "published_date": "",
        "text": "",
        "success": False,
    }

    try:
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding
        html = resp.text
    except Exception as e:
        result["text"] = f"[가져오기 오류: {e}]"
        return result

    soup = BeautifulSoup(html, "html.parser")

    # 1. 제목 추출
    title = None
    for sel in TITLE_SELECTORS:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            title = el.get_text(strip=True)
            break
    if not title and soup.title:
        title = re.sub(r"\s*[:|-]\s*네이버\s*(뉴스)?\s*$", "", soup.title.get_text(strip=True))
    result["title"] = title or ""

    # 2. 언론사 추출
    source = None
    for sel in PRESS_LOGO_SELECTORS:
        el = soup.select_one(sel)
        if el:
            source = el.get("alt") or el.get_text(strip=True)
            if source:
                break
    if not source:
        meta = soup.select_one('meta[property="og:site_name"]') or soup.select_one('meta[name="twitter:creator"]')
        if meta and meta.get("content"):
            source = meta["content"].strip()
    result["source"] = source or "언론사"

    # 3. 발행일시 추출
    date_val = None
    for sel in DATE_SELECTORS:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            date_val = el.get_text(strip=True)
            break
    if not date_val:
        meta = soup.select_one('meta[property="article:published_time"]')
        if meta and meta.get("content"):
            date_val = meta["content"].strip()
    result["published_date"] = date_val or ""

    # 4. 본문 추출
    body_text = ""
    for sel in ARTICLE_BODY_SELECTORS:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            # 불필요 태그 제거
            for junk in el.select("script, style, .ad_wrap, .end_photo_org, noscript"):
                junk.decompose()
            body_text = el.get_text("\n", strip=True)
            break

    if not body_text:
        # 본문 셀렉터 매칭 안 될 경우 meta description 시도
        meta_desc = soup.select_one('meta[property="og:description"]') or soup.select_one('meta[name="description"]')
        if meta_desc and meta_desc.get("content"):
            body_text = meta_desc["content"].strip()

    result["text"] = body_text
    result["success"] = bool(body_text)
    return result
