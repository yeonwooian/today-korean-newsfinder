"""
app.py
------
오늘도국어학원 News_finder AI 웹 대시보드 (Streamlit).
- 100% 네이버 뉴스(https://n.news.naver.com/...) 전용 수집 및 D-1 교육 트렌드 브리핑
- '오늘도국어' 인스타 카드뉴스 자동생성 파이프라인과 완벽 연동
"""

import os
from datetime import datetime
import streamlit as st
from config import (
    NEWS_CATEGORIES,
    get_default_target_date,
    DEFAULT_GEMINI_MODEL,
)
from collector.news_collector import collect_all_categories
from processor.gemini_analyzer import generate_daily_briefing

st.set_page_config(
    page_title="오늘도국어 News_finder AI",
    page_icon="📰",
    layout="wide",
)

st.title("📰 오늘도국어학원 News_finder AI")
st.caption("100% 네이버 뉴스(n.news.naver.com) 기반 D-1 교육 트렌드 자동 조사 & 인스타 연계 봇")

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 조사 설정")
    default_d1 = get_default_target_date()
    target_date = st.date_input(
        "검색 기준 일자 (D-1 기본)",
        value=default_d1,
        help="기본값은 어제 날짜입니다. 특정 일자를 선택하여 과거 이슈를 조사할 수도 있습니다.",
    )
    target_date_str = target_date.strftime("%Y-%m-%d")

    selected_model = st.selectbox(
        "Gemini 모델",
        options=[DEFAULT_GEMINI_MODEL, "gemini-2.0-flash", "gemini-1.5-flash"],
        index=0,
    )

    st.markdown("---")
    st.subheader("📚 4대 카테고리 (네이버뉴스 전용)")
    for cid, info in NEWS_CATEGORIES.items():
        with st.expander(f"[{cid}] {info['name']}", expanded=False):
            st.write(f"**설명**: {info['description']}")
            st.write(f"**키워드**: {', '.join(info['keywords'])}")

    st.markdown("---")
    start_btn = st.button("🚀 네이버 교육뉴스 브리핑 생성", type="primary", use_container_width=True)

# 브리핑 생성 실행
if start_btn:
    progress_bar = st.progress(0, text="네이버 뉴스 조사를 시작합니다...")
    status_text = st.empty()

    try:
        status_text.info(f"[{target_date_str}] 네이버 뉴스(n.news.naver.com)에서 4대 카테고리 기사를 수집 중입니다...")
        progress_bar.progress(30, text="네이버 뉴스 검색 및 기사 본문 파싱 중...")

        # 새롭게 수집 실행
        collected = collect_all_categories(
            target_date=datetime.combine(target_date, datetime.min.time()),
            max_per_category=4,
            fetch_full_text=True,
        )
        st.session_state.collected_news = collected

        total_articles = sum(len(items) for items in collected.values())
        progress_bar.progress(65, text=f"총 {total_articles}건 네이버뉴스 분석 및 큐레이션 중...")
        status_text.info("Gemini AI가 3대 지표(학부모 민감도/인스타 화제성/국어 연계성)로 TOP 3를 선별 중입니다...")

        briefing_md = generate_daily_briefing(
            collected,
            target_date=target_date_str,
            model=selected_model,
        )

        st.session_state.briefing_md = briefing_md
        st.session_state.last_date = target_date_str

        # 파일 자동 저장
        base_dir = os.path.dirname(os.path.abspath(__file__))
        reports_dir = os.path.join(base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, f"{target_date_str}.md")
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(briefing_md)

        progress_bar.progress(100, text="완료되었습니다!")
        status_text.success(f"✅ 데일리 브리핑 생성 완료! (저장 위치: {report_file})")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
        progress_bar.empty()
        status_text.empty()

# 결과 표시 영역
briefing_md = st.session_state.get("briefing_md")
collected_news = st.session_state.get("collected_news")

if briefing_md:
    tab1, tab2 = st.tabs(["📋 교육 뉴스 데일리 브리핑 (네이버뉴스 100%)", "🔍 수집된 네이버뉴스 원문 풀"])

    with tab1:
        col_down1, col_down2 = st.columns([1, 1])
        with col_down1:
            st.download_button(
                label="📥 마크다운 파일 다운로드 (.md)",
                data=briefing_md,
                file_name=f"교육뉴스_브리핑_{st.session_state.get('last_date')}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col_down2:
            st.success("🔗 **인스타 연계 안내**: 브리핑 내 모든 기사 링크는 네이버뉴스(n.news.naver.com)로 제공되므로, '오늘도국어' 인스타 카드뉴스 파이프라인에 그대로 사용하실 수 있습니다.")

        st.markdown("---")
        st.markdown(briefing_md)

    with tab2:
        if collected_news:
            for cid in ["A", "B", "C", "D"]:
                cinfo = NEWS_CATEGORIES[cid]
                articles = collected_news.get(cid, [])
                st.subheader(f"[{cid}] {cinfo['name']} ({len(articles)}건)")

                if not articles:
                    st.write("수집된 네이버 뉴스 기사가 없습니다.")
                else:
                    for i, art in enumerate(articles, 1):
                        title = art.get("title") or "기사 제목"
                        source = art.get("source") or "언론사"
                        link = art.get("link", "")
                        with st.expander(f"{i}. {title} ({source})", expanded=False):
                            st.markdown(f"**네이버 뉴스 원문 링크**: [{link}]({link})")
                            st.write(f"**언론사**: {source}")
                            st.write(f"**발행일시**: {art.get('published_date', '미상')}")
                            if art.get("full_text"):
                                st.caption(f"**본문 발췌**: {art['full_text'][:300]}...")
else:
    st.info("👈 왼쪽 사이드바에서 날짜를 확인하고 **'🚀 네이버 교육뉴스 브리핑 생성'** 버튼을 클릭하세요.")
