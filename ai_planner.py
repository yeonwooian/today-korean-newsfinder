import os
import re
import json
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ==========================================
# 1. Pydantic 스키마 정의 (정형 JSON 출력 보장)
# ==========================================
class CardItem(BaseModel):
    label: str = Field(description="항목명 또는 서브 타이틀 (예: '서강대 시스템반도체', '총 지원자 수')")
    value: Optional[str] = Field(default=None, description="핵심 수치 (stat/comparison 카드에 필수, 예: '66.15 : 1', '5,992명')")
    sub: Optional[str] = Field(default=None, description="보조 수치나 증감률 (예: '+36.5% ▲')")
    detail: Optional[str] = Field(default=None, description="추가 설명이나 부연 텍스트")
    highlight: Optional[Literal["orange", "blue"]] = Field(default="orange", description="핵심 수치 강조 색상")
    sub_highlight: Optional[Literal["orange", "blue"]] = Field(default="blue", description="보조 수치 강조 색상")
    color: Optional[Literal["orange", "blue"]] = Field(default="orange", description="박스 테두리 포인트 색상")

class CardData(BaseModel):
    card_number: int = Field(description="카드 번호 (1부터 시작)")
    badge: str = Field(description="상단 주황색 캡슐 배지 (예: 'IT/AI 대격변 ⚡', '입시 긴급 속보 ⚡', '부동산 정책 체크')")
    category_tag: Optional[str] = Field(
        default=None, 
        description="표지(1번 카드) 제목 바로 위 파란색 소분류 태그. 기사 분야(IT/테크, 입시/교육, 사회, 경제, 생활 등)와 기사 주제에 맞추어 매번 참신하게 생성 (예: IT는 '빅테크/AI 생태계 분석', 교육은 '2027 대입 심층 분석', 경제는 '비즈니스 금융 브리핑', 사회는 '사회·생활 트렌드 이슈' 등 10~15자 내외)"
    )
    brand_report_name: Optional[str] = Field(
        default="오늘도국어학원 이슈 리포트",
        description="표지(1번 카드) 하단 브랜드명 (입시/교육 기사는 '오늘도국어학원 입시 리포트', IT/사회/경제/생활 등 일반 기사는 '오늘도국어학원 트렌드 리포트' 또는 '오늘도국어학원 이슈 리포트')"
    )
    title: str = Field(description="헤드라인 제목 (원 기사 제목을 모방하지 않고 인스타그램용으로 새롭게 창작한 임팩트 있는 헤드라인)")
    subtitle: Optional[str] = Field(default=None, description="제목 보조 설명")
    layout_type: Literal[
        "cover", "stat", "comparison", "list", 
        "step", "hero_stat", "grid", "flow", 
        "chat", "table", "factcheck", 
        "push", "ox_quiz", "mindmap", "before_after",
        "radar", "exam",
        "conclusion"
    ] = Field(
        description="레이아웃 타입 (1번은 cover, 마지막은 conclusion 고정, 본문은 기사 특성에 맞게 다양하게 채택)"
    )
    items: List[CardItem] = Field(default=[], description="카드 본문에 표시할 주요 데이터 항목")
    footer_insight: Optional[str] = Field(default=None, description="하단 한 줄 팁/인사이트 코멘트 (1줄에 깔끔하게 들어가도록 30~35자 내외의 간결한 한 문장)")

class CardNewsPlanResult(BaseModel):
    total_pages: int = Field(description="전체 카드 장수 (최소 4장 ~ 최대 10장 사이에서 AI가 내용 밀도와 기사 분량에 따라 결정)")
    cards: List[CardData] = Field(description="순서대로 정렬된 카드 데이터 목록")
    instagram_caption: str = Field(description="인스타그램 피드 업로드용 본문 (도입 훅, 3줄 요약, 독자 질문, 해시태그 10개 이상)")


# ==========================================
# 2. AI 기획 함수
# ==========================================
def plan_cardnews_and_caption(
    article_title: str, 
    article_content: str, 
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    기사 제목과 본문을 입력받아 가변(4~10장) 카드뉴스 데이터와 인스타 캡션을 1회 API 호출로 동시 생성합니다.
    """
    active_api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not active_api_key:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                active_api_key = str(st.secrets["GEMINI_API_KEY"])
        except Exception:
            pass

    if not active_api_key:
        raise ValueError("GEMINI_API_KEY 환경변수 또는 Streamlit Secrets 설정이 필요합니다.")

    client = genai.Client(api_key=active_api_key)

    system_instruction = """
당신은 대한민국 1티어 인스타그램 입시/시사 카드뉴스 전문 수석 에디터이자 카피라이터입니다.
주어진 기사의 사실을 왜곡하지 않고, 2030 학부모/수험생의 시선을 사로잡는 카드뉴스와 캡션을 기획하세요.

[필수 규칙]
1. [★제목 창작 원칙 - 엄격 준수★]:
   - 카드뉴스의 제목(특히 1번 표지 카드의 title 및 각 본문 카드의 title)은 **원 기사의 제목을 그대로 따라하거나 베끼지 마세요.**
   - 딱딱하고 평이한 신문 보도형 문장 대신, 기사의 핵심 인사이트와 가장 충격적이거나 중요한 수치/변수를 추출하여 **완전히 새로운 인스타그램 맞춤형 카피(Hooking Title)를 독창적으로 창작**하세요.
   - 예시 비교:
     * 원 기사 제목: "반도체 계약학과 수시 지원자 전년 대비 19.4% 증가" (지양)
     * 새롭게 창작한 카드뉴스 제목: "의대 가려다 반도체로? 2027 수시 계약학과 대폭발", "취업 보장의 힘! 수험생 6천 명이 몰린 이유" (권장)
2. [★팩트 기반 작성 및 임의 날조/환각 절대 금지 (STRICT FACTUALITY)★]:
   - 카드뉴스의 제목은 독창적으로 후킹하게 창작하되, **본문에 들어가는 모든 내용(수치, 일정, 연도, 고유명사, 기업명, 정책 내용, 서비스 기능, 통계 등)은 오직 제공된 기사 원문에 명시된 팩트에만 100% 철저히 근거**해야 합니다.
   - **기사에 명시되지 않은 연도(예: 2025년, 2026년 등), 가상의 출시 일정이나 타임라인(예: 2024년 12월, 2025년 상반기 등), 기사에 전혀 언급 없는 외부 신조어/트렌드 용어(예: 바이브 코딩 등)를 그럴듯하게 날조하거나 지어내어 채워 넣지 마세요.**
   - 기사에 구체적인 날짜나 타임라인이 없는 경우, 일정을 억지로 만들어내지 말고 기사에 실제로 나와 있는 서비스 기능, 협력사 현황, 핵심 장점, 기대 효과 등의 팩트를 기반으로 레이아웃(list, grid, flow, table, comparison 등)을 구성하세요.
   - 하단 팁(footer_insight) 역시 기사 내용과 무관한 가상의 연도나 단어를 임의로 언급하지 말고, 기사 본문 기반의 인사이트에만 집중하세요.
3. 전체 카드 장수는 기사 분량과 정보의 깊이에 따라 최소 4장에서 최대 10장 사이(인스타그램 1회 업로드 최대치)로 유동적으로 결정하세요.
4. 1번 카드는 반드시 'cover' 타입이어야 합니다 (스크롤을 즉시 멈추게 하는 강력한 훅킹 타이틀).
5. 마지막 카드는 반드시 'conclusion' 타입이어야 합니다 (전체 총평, 수험생이 주의할 변수, 저장 및 댓글 유도 CTA).
6. 중간 본문 카드들은 기사 내용의 성격과 데이터 형태에 맞춰 아래 레이아웃 중 최적의 것을 풍부하고 다채롭게 선택하세요:
   - 'stat': 복수 통계/수치 지표 나열 및 강조
   - 'hero_stat': 단 하나의 가장 충격적이거나 파급력 큰 초대형 수치(+142% 등) 강조 + 하단 세부 분석 리스트
   - 'comparison': 2개 기업/대학/전형 대조 비교 (2분할 박스)
   - 'table': 세부 기준별(마감 정보, 심리 상태, 지원 전략 등) 다항목 정밀 대조 테이블
   - 'step': 3단계 로드맵, 일정별 행동 요령, 단계별 필승 전략 (STEP 1-2-3 타임라인)
   - 'grid': 4대 필수 체크포인트, 4개 대학군 분류 등 4분할(2x2) 매트릭스
   - 'flow': 원인 ➔ 결과, 문제점 ➔ 대응 전략 등 상하 인과관계 흐름
   - 'chat': 학생의 생생한 고민/질문 vs 선생님의 명쾌한 솔루션 1:1 Q&A 메신저 대화
   - 'factcheck': 시중의 루머/오해 인용(“ ”) ➔ 하향 화살표 ➔ 객관적 팩트 체크 및 근거 분석
   - 'push': 긴급 속보, 실시간 마감 알림, 타임라인 전개 (스마트폰 푸시 알림 센터 UI, sub 필드는 '오늘도국어학원에서 알림' 지정)
   - 'ox_quiz': 원서 접수 전 최종 자가 진단, 필수 체크 문항 (O/X 선택지 체크리스트)
   - 'mindmap': 4대 핵심 성공 전략, 종합 로드맵 (중앙 코어 목표 허브 & 4방위 마인드맵)
   - 'before_after': 실패하는 패턴(❌) vs 합격하는 패턴(✔) (비포 & 애프터 대조형)
   - 'radar': 중심 개념에서 파생되는 4대 종합 전략/대응 매뉴얼 (중앙 핵심 허브에서 사방으로 뻗어나가는 4개 화살표 연결선 & 세부 정보 박스)
   - 'exam': 실제 시험지/모의고사 국어 지문 첨삭 분석 (상단 라이트 시험지 지문 박스 + 오렌지 형광펜 및 빨간 볼펜 첨삭 + 하단 이T의 3초 킬러 독해 솔루션 네이비 박스)
   - 'list': 기본 배경 설명, 다각도 심층 분석 불릿 요약
7. 중요한 수치나 키워드는 주황색('orange') 또는 파랑색('blue')을 적절히 배분하여 시각적 리듬감을 부여하세요.
8. [★표지 파란색 카테고리 태그 동적 생성 - 필수★]:
   - 1번 표지(cover) 카드의 `category_tag`는 표지 제목 상단 파란색 글씨('● 카테고리')로 노출되는 핵심 소분류입니다.
   - 절대로 '2027 수시 긴급 팩트체크' 같은 특정 분야 문구를 고정으로 넣지 마세요! 뉴스는 교육뿐만 아니라 IT/테크, 경제, 사회, 문화, 정책 등 다양한 분야를 다룹니다.
   - 반드시 기사 내용의 분야와 주제에 맞추어 매번 참신한 소분류 태그를 동적으로 생성하세요.
     * IT/테크 기사 예시: '빅테크/AI 생태계 분석', '국산 AI 연합 전격 분석', '차세대 모바일 테크 동향'
     * 입시/교육 기사 예시: '2027 대입 수시 팩트체크', '의대·반도체 지원 동향', '수능 국어 킬러문항 분석'
     * 경제/금융 기사 예시: '생활 경제 트렌드 브리핑', '부동산 청약 긴급 점검', '고물가 대응 실전 전략'
     * 사회/일반 기사 예시: '사회·생활 트렌드 이슈', '청년 일자리 정책 분석', '직장인 커리어 가이드'
   - 표지 하단의 `brand_report_name`도 입시 기사는 '오늘도국어학원 입시 리포트', IT/사회/경제 기사는 '오늘도국어학원 트렌드 리포트' 또는 '오늘도국어학원 이슈 리포트'로 맞추어 설정하세요.
9. 인스타그램 캡션은 [도입 훅 -> 핵심 요약 3줄 -> 독자 참여 유도 질문 -> 연관 해시태그 10개 이상]으로 깔끔한 줄바꿈과 이모지를 섞어 작성하세요. 해시태그 목록의 맨 처음에는 반드시 '#오늘도국어' 가 가장 먼저 오도록 작성하세요.
10. 하단 팁(footer_insight)은 줄바꿈 없이 한눈에 들어오도록 30~35자 내외의 간결하고 핵심적인 한 문장으로 작성하세요.
"""

    prompt = f"""
다음 기사를 면밀히 분석하여 카드뉴스 전체 기획 데이터와 인스타그램 캡션을 생성해 주세요.

[핵심 요구사항]
- 1번 표지(Cover) 카드 및 각 카드의 제목은 **제공된 기사 제목을 흉내 내지 말고**, 기사 본문의 핵심 가치와 독자의 궁금증을 파고드는 **새롭고 신선한 타이틀로 창작**해 주세요.
- **[★표지 파란색 카테고리 태그 동적 생성★]**: 1번 표지 카드의 `category_tag`는 기사의 분야(IT, 경제, 사회, 교육 등)에 맞춰 맞춤형 소분류(예: '빅테크/AI 생태계 분석', '사회·경제 이슈 브리핑' 등)로 생성하세요. '2027 수시 긴급 팩트체크' 같은 고정 문구를 절대 넣지 마세요!
- **[★팩트 준수 및 환각 엄금★]**: 기사 원문에 없는 가상의 연도(예: 2025년), 존재하지 않는 일정/타임라인, 기사에 없는 신조어(바이브 코딩 등)를 절대로 지어내지 마세요. 본문 데이터는 100% 기사 원문의 사실에만 기반해야 합니다.

[기사 원문 참고 정보]
- 기사 원제: {article_title}
- 기사 본문:
{article_content}
"""

    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=CardNewsPlanResult,
            temperature=0.5,
        ),
    )

    result = json.loads(response.text)

    # #오늘도국어 해시태그가 반드시 해시태그 목록의 맨 처음에 위치하도록 후처리 보장
    caption = result.get("instagram_caption", "")
    if caption:
        # 기존 텍스트 내 중복된 #오늘도국어 제거
        clean_caption = re.sub(r'#오늘도국어\b', '', caption).strip()
        # 해시태그 블록 탐색
        hashtag_match = re.search(r'#[\w가-힣]+', clean_caption)
        if hashtag_match:
            start_idx = hashtag_match.start()
            body_text = clean_caption[:start_idx].rstrip()
            tags_text = re.sub(r' +', ' ', clean_caption[start_idx:].strip())
            result["instagram_caption"] = f"{body_text}\n\n#오늘도국어 {tags_text}"
        else:
            result["instagram_caption"] = f"{clean_caption}\n\n#오늘도국어"

    return result


if __name__ == "__main__":
    test_title = "2027 반도체 계약학과 수시 지원자 역대 최고치"
    test_content = """
    2027학년도 대입 수시모집에서 삼성전자와 SK하이닉스 취업 연계 5개 대학 반도체 계약학과 지원자가 5992명으로 전년 대비 19.4% 증가했다.
    평균 경쟁률은 28.53대 1로 전년 23.90대 1보다 크게 올랐다.
    기업별로는 SK하이닉스 연계(고려대, 서강대, 한양대)가 3152명으로 27.3% 증가, 삼성전자 연계(연세대, 성균관대)가 2840명으로 11.7% 증가했다.
    서강대 시스템반도체공학과가 66.15대 1로 최고 경쟁률을 보였으며, 서강대 논술전형은 297.67대 1에 달했다.
    지역의사제 신설로 인한 의대 중복합격 여부가 최종 등록의 주요 변수로 꼽힌다.
    """
    if "GEMINI_API_KEY" in os.environ:
        print("[*] Gemini AI 기획 테스트 중...")
        res = plan_cardnews_and_caption(test_title, test_content)
        print(f"생성 장수: {res['total_pages']}장")
        print("1번 카드:", res['cards'][0]['title'])
    else:
        print("[!] GEMINI_API_KEY 환경변수가 설정되지 않아 단독 테스트를 건너뜁니다.")
