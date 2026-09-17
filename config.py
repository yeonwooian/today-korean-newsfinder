"""
config.py
---------
오늘도국어학원 News_finder 시스템 설정 및 키워드 분류체계
(News_finder.md 지침 완벽 준수)
"""

import os
from datetime import datetime, timedelta

# 1. 네이버 클라우드 플랫폼 (NCP) API 설정 (News_finder.md 7절)
NCP_CLIENT_ID = os.environ.get("NCP_CLIENT_ID", "jvden4cgus")
NCP_CLIENT_SECRET = os.environ.get("NCP_CLIENT_SECRET", "CAbymJysI8tJ8xz35iTz480rnRwvFEAE8iBg81gP")
NCP_API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"

# 2. Gemini 모델 설정 (최신 gemini-3.6-flash)
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# 3. 4대 카테고리별 검색 키워드 체계 (News_finder.md 2.2절)
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

# 4. 언론사 신뢰도 및 우선 순위 가중치 (News_finder.md 3절)
PREFERRED_PRESS = [
    # 교육 전문지
    "베리타스알파", "대학저널", "에듀동아", "내일신문", "한국대학신문", "교수신문",
    # 주요 종합일간지
    "조선일보", "중앙일보", "동아일보", "한겨레", "경향신문", "한국일보", "매일경제", "한국경제", "서울신문", "세계일보", "국민일보",
    # 지상파 및 보도전문채널
    "KBS", "MBC", "SBS", "YTN", "연합뉴스", "연합뉴스TV", "뉴스1", "뉴시스"
]

# 5. 상업적/광고성 기사 필터링 배제 키워드 (News_finder.md 3.1절)
EXCLUDE_TITLE_KEYWORDS = [
    "수강생 모집", "개강", "선착순", "출간", "이벤트", "특강 모집",
    "체험단", "사은품", "할인", "단과 개강", "학원 개원", "수강료",
    "무료 체험", "단독 판매", "교재 증정", "포인트 지급"
]

# 6. 기준 일자 계산 규칙 (News_finder.md 2.1절: D-1 원칙)
def get_default_target_date() -> datetime:
    """봇 실행일 기준 정확히 하루 전(D-1) 반환"""
    return datetime.now() - timedelta(days=1)

def get_target_date_str(target_date: datetime | None = None) -> str:
    """YYYY-MM-DD 포맷 문자열 반환"""
    if target_date is None:
        target_date = get_default_target_date()
    return target_date.strftime("%Y-%m-%d")
