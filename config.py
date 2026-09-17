"""
config.py
---------
오늘도국어학원 인스타 카드뉴스 통합 시스템 설정.
- 솔트 기반 비밀번호 해시 검증 (암호 평문 미노출)
- 텔레그램 송신 전용 설정 (오늘도_인스타운영 대상)
- 네이버 뉴스 4대 카테고리 및 D-1 검색 체계
"""

from __future__ import annotations

import os
import hashlib
from datetime import datetime, timedelta

def get_setting(key: str, default: str = "") -> str:
    """Streamlit Secrets (클라우드 환경) 및 환경변수를 안전하게 조회합니다."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)

# 1. 관리자 암호 보안 설정 (Salted SHA-256 해시 검증)
# 원본 암호는 코드나 UI에 노출되지 않습니다.
PASSWORD_SALT = "todaykorean_salt_2026"
PASSWORD_HASH = get_setting(
    "ADMIN_PASSWORD_HASH",
    "9abd61c5d45ee60305a3974e72b04c94c70ccf3a7c3a5c5a03bbf6c7e3e8e272"
)

def verify_password(input_pw: str) -> bool:
    """입력받은 비밀번호를 해시하여 설정된 암호와 일치하는지 검증합니다."""
    if not input_pw:
        return False
    calc_hash = hashlib.sha256((PASSWORD_SALT + input_pw.strip()).encode("utf-8")).hexdigest()
    return calc_hash == PASSWORD_HASH

# 2. 텔레그램 전송 설정 (송신 전용: 오늘도_인스타운영 그룹)
# 타 프로젝트(창영초 등)의 TELEGRAM_BOT_TOKEN 환경변수와 충돌하지 않도록 전용 토큰 고정
TELEGRAM_BOT_TOKEN = get_setting(
    "TODAYKOREAN_BOT_TOKEN",
    "8520917536:AAEsTJ863uIGK3rOs0zFrwx_4MxGULFXXUk"
)
TELEGRAM_CHAT_ID = get_setting(
    "TODAYKOREAN_CHAT_ID",
    "-5537868086"
)

# 3. 네이버 클라우드 플랫폼 (NCP) Search API 설정
NCP_CLIENT_ID = get_setting("NCP_CLIENT_ID", "jvden4cgus")
NCP_CLIENT_SECRET = get_setting("NCP_CLIENT_SECRET", "CAbymJysI8tJ8xz35iTz480rnRwvFEAE8iBg81gP")
NCP_API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

# 4. Gemini AI 모델 기본 설정
DEFAULT_GEMINI_MODEL = get_setting("GEMINI_MODEL", "gemini-2.5-flash")

# 5. 4대 카테고리별 검색 키워드 체계
NEWS_CATEGORIES = {
    "A": {
        "name": "교육 정책/제도",
        "description": "교육부 정책, 고교학점제, 2028 대입 개편안",
        "keywords": ["교육부", "고교학점제", "2028 대입", "내신 5등급제", "서논술형 평가", "문해력"],
    },
    "B": {
        "name": "중·고등 내신/평가",
        "description": "수행평가, 서논술형 확대, 학교 시험 트렌드",
        "keywords": ["중등 내신", "고등 내신", "수행평가", "서술형 평가", "중간고사", "기말고사", "국어 내신"],
    },
    "C": {
        "name": "수능/모의평가",
        "description": "평가원 모평, 킬러문항 배제, 국어 영역 분석",
        "keywords": ["수능 국어", "6월 모평", "9월 모평", "수능 모의평가", "EBS 연계", "불수능", "물수능"],
    },
    "D": {
        "name": "입시/대입 전형",
        "description": "의대 정원, 무전공 확대, 수시/정시 경쟁률",
        "keywords": ["수시 모집", "정시 모집", "의대 정원", "무전공", "학생부종합", "대입 경쟁률", "입시 설명회"],
    },
}

# 6. 언론사 신뢰도 가중치
PREFERRED_PRESS = [
    # 교육 전문지
    "베리타스알파", "대학저널", "에듀동아", "내일신문", "한국대학신문", "교수신문",
    # 주요 종합일간지
    "조선일보", "중앙일보", "동아일보", "한겨레", "경향신문", "한국일보", "매일경제", "한국경제", "서울신문", "세계일보", "국민일보",
    # 지상파 및 보도전문채널
    "KBS", "MBC", "SBS", "YTN", "연합뉴스", "연합뉴스TV", "뉴스1", "뉴시스"
]

# 7. 상업적/광고성 기사 필터링 배제 키워드
EXCLUDE_TITLE_KEYWORDS = [
    "수강생 모집", "개강", "선착순", "출간", "이벤트", "특강 모집",
    "체험단", "사은품", "할인", "단과 개강", "학원 개원", "수강료",
    "무료 체험", "단독 판매", "교재 증정", "포인트 지급"
]

# 8. 기준 일자 계산 규칙 (D-1 기본 원칙)
def get_default_target_date() -> datetime:
    """실행일 기준 어제(D-1) 반환"""
    return datetime.now() - timedelta(days=1)

def get_target_date_str(target_date: datetime | None = None) -> str:
    """YYYY-MM-DD 포맷 문자열 반환"""
    if target_date is None:
        target_date = get_default_target_date()
    return target_date.strftime("%Y-%m-%d")
