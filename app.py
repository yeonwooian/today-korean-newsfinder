"""
app.py
------
오늘도국어학원 모바일 최적화(Mobile-First) 인스타 카드뉴스 자동생성 웹앱.
- 보안 암호 접근 (해시 인증, 평문 노출 없음)
- 수집된 네이버 기사모음 탐색 (4대 카테고리, D-1 자동 수집)
- 원클릭 인스타 카드뉴스(1080×1350) 및 피드 캡션 생성
- 텔레그램(오늘도_인스타운영) 송신 전용 자동 발송
- 스마트폰 화면에 최적화된 결과물 미리보기 및 원클릭 복귀
"""

from __future__ import annotations

import base64
import os
import sys
from datetime import datetime
from pathlib import Path

# 작업 디렉터리 경로 등록
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
from config import (
    NEWS_CATEGORIES,
    get_default_target_date,
    get_target_date_str,
    verify_password,
    TELEGRAM_CHAT_ID,
)
from collector.news_collector import collect_all_categories
from main import run_pipeline

# 1. 모바일 최적화 페이지 설정
st.set_page_config(
    page_title="뉴스파인더 by 오늘도국어 학원",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# 2. 스마트폰 전용 반응형 CSS 인젝션 (상단 짤림 방지 및 가독성 최적화)
st.markdown(
    """
    <style>
    /* 상단 헤더 짤림 완전 방지 (여백 충분히 확보) */
    .block-container {
        padding-top: 3.8rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
        max-width: 540px !important;
    }
    /* 타이틀 및 헤더 우측 로고 영역 스타일링 */
    .top-title-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 0.2rem;
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
        border-bottom: 1.5px solid #edf2f7;
        gap: 12px;
    }
    .top-title-text {
        flex: 1;
        min-width: 0;
    }
    .app-main-title {
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        color: #1a202c !important;
        letter-spacing: -0.3px;
        line-height: 1.35;
        word-break: keep-all;
    }
    .app-sub-title {
        font-size: 0.82rem !important;
        color: #718096 !important;
        font-weight: 600;
        margin-top: 3px;
        letter-spacing: 0.2px;
    }
    .top-title-logo {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        flex-shrink: 0;
    }
    .top-title-logo img {
        height: 44px;
        width: auto;
        max-width: 135px;
        object-fit: contain;
    }
    @media (max-width: 440px) {
        .top-title-container {
            gap: 8px;
        }
        .app-main-title {
            font-size: 1.18rem !important;
        }
        .app-sub-title {
            font-size: 0.76rem !important;
        }
        .top-title-logo img {
            height: 34px;
            max-width: 100px;
        }
    }
    .section-title {
        font-size: 1.18rem !important;
        font-weight: 750 !important;
        color: #2d3748 !important;
        margin-top: 0.4rem;
        margin-bottom: 0.2rem;
    }
    .section-desc {
        font-size: 0.85rem !important;
        color: #718096 !important;
        margin-bottom: 1rem;
    }
    h2, h3 {
        font-size: 1.15rem !important;
        font-weight: 700 !important;
    }
    p, span, label {
        font-size: 0.95rem !important;
    }
    /* 터치 타깃이 편한 대형 버튼 */
    .stButton > button {
        width: 100% !important;
        min-height: 48px !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        border-radius: 12px !important;
        padding: 0.6rem 1rem !important;
        transition: transform 0.1s ease-in-out;
    }
    .stButton > button:active {
        transform: scale(0.98);
    }
    /* 카드형 컨테이너 디자인 */
    .article-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .article-source {
        color: #2b6cb0;
        font-size: 0.8rem !important;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .article-title {
        font-size: 1.05rem !important;
        font-weight: 700;
        line-height: 1.4;
        color: #1a202c;
        margin-bottom: 8px;
    }
    .article-desc {
        font-size: 0.85rem !important;
        color: #4a5568;
        line-height: 1.45;
        margin-bottom: 12px;
    }
    .badge-telegram {
        background-color: #ebf8ff;
        color: #2b6cb0;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 0.85rem !important;
        font-weight: 600;
        display: inline-block;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def get_logo_html() -> str:
    """헤더 우측에 표시할 오늘도국어 로고(background/logo_black.png) base64 HTML 반환"""
    logo_path = BASE_DIR / "background" / "logo_black.png"
    if logo_path.exists():
        try:
            b64 = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
            return f'<img src="data:image/png;base64,{b64}" alt="오늘도국어 학원 로고" />'
        except Exception:
            return ""
    return ""


def render_top_header():
    """모바일 최적화 상단 브랜드 헤더 (타이틀 + 우측 로고) 컴포넌트"""
    logo_img = get_logo_html()
    st.markdown(
        f"""
        <div class="top-title-container">
            <div class="top-title-text">
                <div class="app-main-title">뉴스파인더 by 오늘도국어 학원.</div>
                <div class="app-sub-title">produced by 4J_System.</div>
            </div>
            <div class="top-title-logo">
                {logo_img}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# 3. 로그인 세션 관리 (솔트 해시 기반 보안 인증)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    render_top_header()
    st.markdown("### 🔒 오늘도국어 관리자 인증")
    st.caption("안전한 시스템 관리를 위해 암호를 입력해 주세요.")

    with st.form("login_form", clear_on_submit=False):
        input_pw = st.text_input("접속 비밀번호", type="password", placeholder="비밀번호 입력")
        submit_btn = st.form_submit_button("확인 후 로그인", type="primary", use_container_width=True)

        if submit_btn:
            if verify_password(input_pw):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다. 다시 확인해 주세요.")

    st.stop()


# 4. 세션 상태 초기화
if "collected_news" not in st.session_state:
    st.session_state.collected_news = None
if "current_generation" not in st.session_state:
    st.session_state.current_generation = None
if "search_date" not in st.session_state:
    st.session_state.search_date = get_default_target_date()


# ==========================================
# 화면 A: 결과물 상세 및 캡션 확인 화면
# ==========================================
gen_data = st.session_state.current_generation
if gen_data is not None:
    render_top_header()
    # 1. 상단 복귀 버튼
    if st.button("↩ 기사모음으로 복귀", key="btn_return_top", use_container_width=True):
        st.session_state.current_generation = None
        st.rerun()

    st.markdown("---")
    st.markdown("### 🎉 인스타 카드뉴스 제작 완료")
    
    tg_res = gen_data.get("telegram_result")
    if tg_res and tg_res.get("success"):
        st.markdown(
            '<div class="badge-telegram">📱 텔레그램(오늘도_인스타운영)으로 자동 전송되었습니다!</div>',
            unsafe_allow_html=True,
        )
    elif tg_res and not tg_res.get("success"):
        st.warning(f"⚠️ 텔레그램 전송 알림: {tg_res.get('error')}")

    article_info = gen_data.get("article", {})
    st.caption(f"기사 원문: {article_info.get('title', '')}")

    # 생성된 카드뉴스 갤러리 표시 (1080×1350 스마트폰 스크롤 맞춤)
    images = gen_data.get("images", [])
    st.markdown(f"#### 🖼️ 완성된 카드뉴스 ({len(images)}장)")
    
    for idx, img_path in enumerate(images, 1):
        if Path(img_path).exists():
            st.image(str(img_path), caption=f"Card {idx}", use_container_width=True)
            with open(img_path, "rb") as f_img:
                st.download_button(
                    label=f"💾 Card {idx} 이미지 다운로드",
                    data=f_img,
                    file_name=f"card_{idx}.png",
                    mime="image/png",
                    key=f"dl_card_{idx}",
                    use_container_width=True,
                )

    st.markdown("---")
    # 인스타그램 피드 캡션 텍스트 박스
    caption = gen_data.get("caption", "")
    st.markdown("#### 📝 인스타그램 피드 캡션")
    st.text_area("아래 내용을 복사하여 인스타 게시물 본문에 붙여넣으세요:", value=caption, height=280)

    st.markdown("---")
    # 2. 하단 복귀 버튼
    if st.button("↩ 기사모음으로 복귀", key="btn_return_bottom", type="primary", use_container_width=True):
        st.session_state.current_generation = None
        st.rerun()

    st.stop()


# ==========================================
# 화면 B: 메인 수집된 네이버 기사모음 화면
# ==========================================
render_top_header()
st.markdown(
    """
    <div class="section-title">📰 수집된 네이버 기사모음</div>
    <div class="section-desc">100% 네이버 뉴스(n.news.naver.com) 기준 D-1 교육 트렌드</div>
    """,
    unsafe_allow_html=True,
)

# 모바일 날짜 선택 및 기사 새로고침 아코디언
with st.expander("📅 검색 일자 변경 / 새로고침", expanded=False):
    sel_date = st.date_input(
        "검색 기준일자 (기본: 어제 D-1)",
        value=st.session_state.search_date,
    )
    if st.button("🔄 이 날짜로 네이버 기사 수집", use_container_width=True):
        st.session_state.search_date = sel_date
        st.session_state.collected_news = None
        st.rerun()

target_date = st.session_state.search_date
target_date_str = target_date.strftime("%Y-%m-%d")

# 기사 데이터가 없으면 자동 수집 시작
if st.session_state.collected_news is None:
    with st.spinner(f"[{target_date_str}] 네이버 교육 뉴스를 수집하는 중입니다..."):
        try:
            collected = collect_all_categories(
                target_date=datetime.combine(target_date, datetime.min.time()),
                max_per_category=8,
                fetch_full_text=True,
            )
            st.session_state.collected_news = collected
        except Exception as e:
            st.error(f"기사 수집 중 오류가 발생했습니다: {e}")
            st.stop()

collected_news = st.session_state.collected_news or {}
total_articles = sum(len(items) for items in collected_news.values())

st.write(f"📌 기준일: **{target_date_str}** | 총 **{total_articles}건**의 기사")

# 4대 카테고리 탭 구성 (스마트폰 터치 탭)
tabs = st.tabs([f"{cid}. {info['name']}" for cid, info in NEWS_CATEGORIES.items()])

for (cid, info), tab in zip(NEWS_CATEGORIES.items(), tabs):
    with tab:
        articles = collected_news.get(cid, [])
        if not articles:
            st.info("수집된 네이버 뉴스 기사가 없습니다.")
            continue

        for idx, art in enumerate(articles, 1):
            title = art.get("title") or "기사 제목 없음"
            source = art.get("source") or "언론사"
            link = art.get("link", "")
            date_str = art.get("published_date") or art.get("date_text") or ""
            desc = art.get("full_text") or art.get("description") or ""
            desc_preview = (desc[:180] + "...") if len(desc) > 180 else desc

            # 모바일 카드 뷰
            st.markdown(
                f"""
                <div class="article-box">
                    <div class="article-source">[{source}] {date_str}</div>
                    <div class="article-title">{title}</div>
                    <div class="article-desc">{desc_preview}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # 네이버 원문 확인 링크 & 게시물 생성 버튼
            col_link, col_btn = st.columns([1, 2])
            with col_link:
                st.markdown(
                    f'<a href="{link}" target="_blank" style="text-decoration:none;">'
                    f'<button style="width:100%; min-height:44px; border-radius:10px; border:1px solid #cbd5e0; background:#f7fafc; font-size:0.85rem; font-weight:600; cursor:pointer;">'
                    f'🔗 원문보기</button></a>',
                    unsafe_allow_html=True,
                )
            with col_btn:
                btn_key = f"btn_create_{cid}_{idx}"
                if st.button("🚀 게시물 생성", key=btn_key, type="primary", use_container_width=True):
                    # 실행 프로그레스 표시
                    with st.status("🎨 인스타그램 카드뉴스 생성 진행 중...", expanded=True) as status:
                        try:
                            def _cb(msg, pct):
                                status.update(label=f"[{pct}%] {msg}")

                            result = run_pipeline(
                                url=link,
                                output_dir=str(BASE_DIR / "output"),
                                send_telegram=True,
                                progress_callback=_cb,
                            )
                            status.update(label="✅ 생성 및 텔레그램 전송 완료!", state="complete")
                            st.session_state.current_generation = result
                            st.rerun()
                        except Exception as pe:
                            status.update(label="❌ 작업 중 오류 발생", state="error")
                            st.error(f"오류가 발생했습니다: {pe}")
            
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
