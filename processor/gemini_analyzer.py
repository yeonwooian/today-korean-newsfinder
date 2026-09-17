"""
processor/gemini_analyzer.py
----------------------------
Gemini AI를 활용하여 수집된 기사들을 심층 분석하고,
News_finder.md 규격의 '교육 뉴스 데일리 브리핑'을 생성하는 핵심 모듈.
(로컬 환경변수 및 Streamlit Cloud Secrets 완벽 호환)
"""

from __future__ import annotations

import os
import time
from typing import Optional
from google import genai
from google.genai import types
from config import DEFAULT_GEMINI_MODEL
from processor.prompt_rules import SYSTEM_PROMPT, ANALYSIS_INSTRUCTIONS


def _get_client() -> genai.Client:
    # 1. 로컬 환경변수 확인
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 2. Streamlit Cloud Secrets 확인 (배포 환경)
    if not api_key:
        try:
            import streamlit as st
            if "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY가 설정되지 않았습니다. 환경변수 또는 Streamlit Secrets를 확인해주세요."
        )
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90000))


def _format_candidates_for_prompt(all_news: dict[str, list[dict]]) -> str:
    """수집된 기사 목록을 프롬프트용 텍스트 블록으로 포맷팅합니다."""
    sections = []
    category_labels = {
        "A": "A. 교육 정책/제도",
        "B": "B. 중·고등 내신/평가",
        "C": "C. 수능/모의평가",
        "D": "D. 입시/대입 전형",
    }

    for cat_id in ["A", "B", "C", "D"]:
        items = all_news.get(cat_id, [])
        cat_name = category_labels.get(cat_id, cat_id)
        sec_lines = [f"### [분야: {cat_name}] (후보 {len(items)}건)"]
        
        if not items:
            sec_lines.append("(해당 분야 수집 기사 없음)")
        else:
            for idx, item in enumerate(items, 1):
                title = item.get("title", "")
                link = item.get("naver_link") or item.get("link", "")
                source = item.get("source", "")
                pub_date = item.get("published_date") or item.get("date_text", "")
                text = item.get("full_text") or item.get("description", "")
                
                sec_lines.append(f"기사 {idx}:")
                sec_lines.append(f"- 제목: {title}")
                sec_lines.append(f"- 원문 링크(네이버뉴스): {link}")
                sec_lines.append(f"- 언론사: {source}")
                sec_lines.append(f"- 발행일: {pub_date}")
                sec_lines.append(f"- 본문 내용/요약:\n{text[:800]}")
                sec_lines.append("")

        sections.append("\n".join(sec_lines))

    return "\n\n".join(sections)


def generate_daily_briefing(
    all_news: dict[str, list[dict]],
    target_date: str,
    model: str = DEFAULT_GEMINI_MODEL,
    max_attempts: int = 3,
) -> str:
    """
    수집된 4대 카테고리 네이버 뉴스 기사들을 Gemini AI에 전달하여
    News_finder.md 규격의 데일리 브리핑 마크다운 문서를 생성합니다.
    """
    client = _get_client()
    candidates_text = _format_candidates_for_prompt(all_news)

    prompt = SYSTEM_PROMPT + "\n\n" + ANALYSIS_INSTRUCTIONS.format(
        target_date=target_date,
        candidate_articles_text=candidates_text,
    )

    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[prompt],
            )
            text = (response.text or "").strip()
            if text:
                return text
        except Exception as e:
            last_error = e
            print(f"[Gemini 분석 시도 {attempt}/{max_attempts} 실패] {e}")
            if attempt < max_attempts:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Gemini 데일리 브리핑 생성 실패: {last_error}")
