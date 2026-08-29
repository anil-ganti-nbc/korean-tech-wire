"""Source-specific editorial filtering: samsung_newsroom_kr first-valid branch
and ZDNet Korea / Digital Today leakage repair.

Regression titles are REAL titles that the deployed (125c39c) filter accepted,
pulled read-only from the production DB history (2026-08-25..29). Off-beat
ones are pinned as must-reject; clearly on-beat ones are pinned as must-accept
so the tightened verticals do not silently lose real yield.
"""

from __future__ import annotations

from datetime import datetime, timezone

from korean_tech_wire.editorial import classify
from korean_tech_wire.models import DiscoveredArticle, Source

NOW = datetime.now(timezone.utc)

SAMSUNG = Source("samsung_newsroom_kr", "Samsung Newsroom Korea", "EXPERIMENTAL", True, "samsung_html", "https://news.samsung.com/kr/")
ZDNET = Source("zdnet_korea_semi_display", "ZDNet Korea", "EXPERIMENTAL", True, "zdnet_feed", "https://zdnet.co.kr/feed/article_list.xml")
DIGITALTODAY = Source("digitaltoday_semi_display", "Digital Today", "EXPERIMENTAL", True, "gnews_sitemap", "https://www.digitaltoday.co.kr/sitemap.xml")


def art(title: str, metadata: dict | None = None, category: str | None = None) -> DiscoveredArticle:
    return DiscoveredArticle("s", "u", "u", title, None, NOW, metadata=metadata if metadata is not None else {}, category=category)


def decision_for(source: Source, title: str, metadata: dict | None = None):
    return classify(source, art(title, metadata))


# -- samsung_newsroom_kr ---------------------------------------------------------

def test_samsung_accepts_real_semiconductor_display_manufacturing_titles():
    # All four are real accepted rows from the stored history that remain on-beat.
    assert decision_for(SAMSUNG, "삼성전자, FMS 2026서 차세대 3D 메모리 비전 제시").accepted
    assert decision_for(SAMSUNG, "삼성전자, 인도에 플랙트그룹 신규 생산라인 준공…AI 데이터센터 공략 강화").accepted
    assert decision_for(SAMSUNG, "삼성전자, 광주사업장에 플랙트그룹 신규 HVAC 생산라인 구축").accepted
    assert decision_for(SAMSUNG, "삼성전자, 차세대 포터블 SSD 2종 P9, P7 공개").accepted


def test_samsung_acceptlist_is_casefolded_and_unicode_safe():
    assert decision_for(SAMSUNG, "삼성전자, 300mm 웨이퍼 라인 증설…평택 팹 투자 확대").accepted
    assert decision_for(SAMSUNG, "삼성전자 OLED 패널 양산 체제 가동").accepted  # OLED casefolds to oled
    assert decision_for(SAMSUNG, "삼성전자, 獨에 HBM4 생산능력 확대").accepted  # Hanja prefix tolerated


def test_samsung_rejects_real_marketing_csr_entertainment_leakage():
    # Real accepted titles from production history (2026-08-27..29 index pages).
    no_signal = [
        "삼성, 경상 지역 수해 복구에 30억원 지원",
        "삼성전자, ‘디지털고객경험지수’ 종합가전 4년 연속 1위…구매 과정 전반 디지털 경험 강화",
        "삼성전자, ‘게임스컴 2026’서 오디세이 게이밍 모니터 신제품 공개",
        "삼성전자, 원스톱 혼수 특화 매장 ‘삼성스토어 청담점’ 전면 리뉴얼 오픈",
        "삼성 아트 스토어에 ‘빈 미술사 박물관’ 대표 소장품 43점 공개",
        "삼성, 국제올림피아드 수상자에게 장학금… 이공계 인재 육성에 기여",
        "삼성전자, 액티비전 블리자드와 ‘콜 오브 듀티: 모던 워페어 4’ 파트너십 체결",
        "삼성전자, 베트남 하노이에 ‘비즈니스 익스피리언스 스튜디오’ 개관…기업 디지털 전환 지원",
        "화질, 사운드, 게이밍 성능까지… 삼성전자 2026년형 TV·오디오, 글로벌 매체서 대거 수상",
        "삼성전자, 베트남 최초 태양광 DPPA 통해 재생에너지 공급 개시",
        "올해 여름에도 삼성전자 에어컨 ‘청.정.확.인’!",
        "삼성전자, 삼성 월렛에 코레일(Korail) ‘종이 없는 승차권’ 서비스 출시",
    ]
    for title in no_signal:
        decision = decision_for(SAMSUNG, title)
        assert not decision.accepted, title
        assert decision.reason == "no_semiconductor_or_display_signal", title
    # These carry PR markers/company brand nouns (갤럭시) and are denied by the
    # PR-format stage before the allowlist is even consulted.
    pr_stories = [
        "삼성전자, 갤럭시 프리미엄 기능을 담은 ‘갤럭시 S26 FE’ 공개",
        "새로운 갤럭시 폴드8으로의 전환, 더 쉽고 간편하게",
        "삼성전자 ‘갤럭시 버즈4 프로’, ‘EISA 어워드’서 최고 제품으로 선정",
        "삼성전자, 사상 최대 주주환원 실시… 2026년 약 90조~110조원 예상",
    ]
    for title in pr_stories:
        decision = decision_for(SAMSUNG, title)
        assert not decision.accepted, title
        assert decision.reason in ("newsroom_pr_or_corporate_story", "no_semiconductor_or_display_signal"), title


def test_samsung_rejects_real_media_sponsorship_campaign_leakage():
    must_reject = [
        "삼성전자, 영화 ‘스파이더맨: 브랜드 뉴 데이’ 신규 캠페인 영상 공개",
        "삼성전자, 英 축구 전설 조 콜과 ‘레이즈 더 바’ 캠페인… “지역 펍 시청 환경 혁신”",
        "폴란드 최초 ‘더 스피드 프로젝트’ 참가팀, 삼성 갤럭시와 함께 데스밸리 코스 완주",
        "삼성전자, 두바이 상공에서 갤럭시 Z 폴드8 출시 기념 스카이다이빙 퍼포먼스 진행",
        "삼성전자, 멕시코 피트니스 트래커 시장 최고 성장 브랜드 선정",
        "기술을 넘어 패션으로…삼성전자X도미니코, 080 바르셀로나 패션쇼서 협업 컬렉션 공개",
        "삼성전자, 독일 ‘게임스컴 2026’ 참가… 풀스택 게이밍 경험 제시",
    ]
    for title in must_reject:
        assert not decision_for(SAMSUNG, title).accepted, title


def test_samsung_rejects_real_pr_format_markers_even_with_signal_terms():
    # Deny-first matters: these carry allow-list vocabulary (디스플레이, 8세대)
    # inside marketing-format cards and must be rejected by the PR stage.
    decision = decision_for(SAMSUNG, "[영상] “공용 디스플레이도 개인 기기처럼” 삼성 전자칠판, 계정 관리 솔루션으로 교사 개인별 수업 환경 제공")
    assert not decision.accepted and decision.reason == "newsroom_pr_or_corporate_story"
    decision = decision_for(SAMSUNG, "삼성전자, 8세대 갤럭시 폴더블 기술 혁신 담은 ‘폴더블 헤리티지’ 전시")
    assert not decision.accepted and decision.reason == "newsroom_pr_or_corporate_story"
    decision = decision_for(SAMSUNG, "[인터뷰] [갤럭시 언팩 2026] “소재부터 사용자 경험까지”…갤럭시 Z 시리즈 하드웨어 혁신 비하인드")
    assert not decision.accepted and decision.reason == "newsroom_pr_or_corporate_story"
    # '전시관' (exhibition hall) carries the 전시 noun, not an 8세대 display fab.
    decision = decision_for(SAMSUNG, "獨 ‘게임스컴 2026’ 삼성전자 전시관 이모저모")
    assert not decision.accepted and decision.reason == "newsroom_pr_or_corporate_story"


def test_samsung_rejects_real_card_news_video_invitation_sections():
    must_reject = [
        "[영상] 펼치지 않아도 OK, 갤럭시 Z 플립8 ‘플렉스 윈도우’와 함께한 하루",
        "[초대장] 디자인 마이애미 서울 2026: ‘디자인은 사랑의 표현(Design is an Act of Love)’ 개최",
        "[초대장] 삼성 갤럭시 이벤트",
        "[카드뉴스] 얼음, 다 같은 얼음이 아니다? 삼성 제빙 기술이 만드는 얼음의 차이",
        "[카드뉴스] [갤럭시 언팩 2026] “새로운 갤럭시, 먼저 써봤어요”… 삼성 멤버스가 뽑은 최고의 기능",
        "[인터뷰] “우리 집 터줏대감이자 든든한 조력자”… 배우 한가인이 전하는 삼성 냉장고 이야기",
        "[영상] 삼성 AI 어시스턴트, 학습 몰입도와 접근성을 높이는 미래형 교실을 제안하다",
        "[영상] [갤럭시 언팩 2026] 삼성 헬스가 그리는 AI 기반 커넥티드 케어의 미래",
    ]
    for title in must_reject:
        decision = decision_for(SAMSUNG, title)
        assert not decision.accepted and decision.reason == "newsroom_pr_or_corporate_story", title


def test_samsung_borderline_corporate_items_fail_closed():
    # Ambiguous corporate content fails closed, per the beat contract
    # (semiconductor/display/hardware-manufacturing material only).
    borderline = [
        "삼성전자-NTT 도코모, AI-RAN 기반 통신 서비스 품질 최적화 기술 검증",
        "삼성리서치, 헬스 파운데이션 모델 기반 웨어러블 AI 연구 공개",
        "삼성전자, 아마존 프라임 비디오에 ‘HDR10+ 어드밴스드’ 기술 선보여",
        "삼성전자, ‘EHS 히트펌프 보일러’ 국내서 9월 생산…韓 난방 전기화 대중화 동참",
        "삼성전자, 2026년 2분기 실적 발표",
        "삼성전자, 美 에너지부 산하 국립연구소와 차세대 난방 기술 개발 박차",
    ]
    for title in borderline:
        assert not decision_for(SAMSUNG, title).accepted, title


def test_samsung_rejects_legacy_index_noise_rows():
    # record_status='legacy_unverified' rows from the pre-hardening collector.
    for title in ["Vision AI", "6G", "AI", "스마트싱스", "비스포크", "갤럭시 Z 시리즈", "삼성 아트 스토어", "밀라노 디자인위크", "영상기사"]:
        assert not decision_for(SAMSUNG, title).accepted, title


def test_samsung_empty_or_malformed_metadata_is_safe():
    assert not decision_for(SAMSUNG, "").accepted
    article = art("삼성전자, FMS 2026서 차세대 3D 메모리 비전 제시", metadata={"index_date": "2026/08/10", "index_container": "article_lists"}, category="프레스센터")
    assert classify(SAMSUNG, article).accepted
    article = art("삼성전자, 차세대 포터블 SSD 2종 P9, P7 공개", metadata={}, category=None)
    assert classify(SAMSUNG, article).accepted


# -- zdnet_korea_semi_display ----------------------------------------------------

def test_zdnet_keeps_real_onbeat_titles():
    must_accept = [
        "SK하이닉스, &#34;美인디애나 패키징팹서 HBM4E 양산…2029년 3분기 목표&#34;",
        "&#34;LG디스플레이, 상반기 아이폰 OLED 3150만대 출하...21.6% 상승&#34;",
        "삼성디스플레이, 제네시스 GV90에 투 탠덤 OLED 공급",
        "인도 데이터센터 회사, 엔비디아 루빈 GPU 9000개 발주",
        "삼성, 갤럭시A1 DDI 후공정 LB세미콘→대만 칩본드 변경...원가 절감 차원",
        "인텔, 256코어",
        "이재명 대통령, 이재용 회장 만나 서남권 반도체 투자 현안 푼다",
        "&#34;폴더블 OLED, 애플 덕에 3년 정체 끝…연평균 12.2% 성장&#34;",
    ]
    for title in must_accept:
        assert decision_for(ZDNET, title).accepted, title


def test_zdnet_rejects_real_leakage_including_substring_collisions():
    cases = {
        # 'tv' matched inside 연합뉴스TV
        "YTN·연합뉴스TV 승인기간 3개월 단축…사장추천위 구성 재명령": "no_semiconductor_or_display_signal",
        # '전자' matched inside 운전자
        "화물차 화재 목격한 우편 집배원, 운전자 구하고 불 껐다": "no_semiconductor_or_display_signal",
        # '인텔' matched inside 인텔리전스 (threat-intelligence vendors)
        "그룹아이비, 위협 인텔리전스 솔루션 AWS 마켓플레이스 등록": "threat_intelligence_item",
        "&#34;AI발 보안리스크 관리 이렇게&#34;...에임인텔리전스, 내달 7일 컨퍼런스": "threat_intelligence_item",
        # bare 공급/생산/설비 matched non-tech supply stories and events
        "수요는 줄고 공급은 넘치고…중국 태양광업계 적자 심화": "no_semiconductor_or_display_signal",
        "넵튠, 카카오페이에 H5게임 공급...미니게임 사업 강화": "no_semiconductor_or_display_signal",
        "KCA, 수해 입은 거제·통영 선박 통신설비 무상점검": "no_semiconductor_or_display_signal",
        "&#34;C레벨에 SW 공급망 보안 강조&#34;...스패로우, 연례 행사 개최": "no_semiconductor_or_display_signal",
        "무뇨스 현대차 사장 &#34;중국 누구와도 경쟁&#34;…로봇 年 3만대 생산체제 구축": "no_semiconductor_or_display_signal",
        "아톤, 나이스디앤에스에 악성문자 사전차단 플랫폼 공급": "no_semiconductor_or_display_signal",
        # consumer product launch scope creep
        "한국레노버, 리전 게이밍 모니터 신제품 4종 출시": "no_semiconductor_or_display_signal",
        # generic '전자' company-name match, truncated recycling story
        "LG전자, 폐가전서": "no_semiconductor_or_display_signal",
    }
    for title, reason in cases.items():
        decision = decision_for(ZDNET, title)
        assert not decision.accepted, title
        assert decision.reason == reason, title


def test_zdnet_borderline_items_remain_accepted_by_design():
    # GPU/AI-infrastructure interviews, truncated company op-eds and battery
    # research stay inside the vertical; they are documented borderline yield.
    for title in [
        "[AI 리더스] 엘리스그룹 &#34;GPU 확보 넘어",
        "[기고] LG디스플레이는 왜",
        "에너지연 &#34;전기차 폐배터리 30분이면 완벽 재생&#34;",
    ]:
        assert decision_for(ZDNET, title).accepted, title


def test_zdnet_empty_title_and_empty_metadata_are_safe():
    assert not decision_for(ZDNET, "").accepted
    assert decision_for(ZDNET, "TSMC 2나노 파운드리 수율 60% 돌파").accepted


# -- digitaltoday_semi_display ---------------------------------------------------

def test_digitaltoday_source_keyword_taxonomy_rejects_finance_crypto_chatbot_entertainment():
    # NOTE: Digital Today's news:keywords embed the outlet name and the full
    # headline before its taxonomy tags ("디지털투데이 (DigitalToday), <headline>,
    # <tags>"), so these are the exact stored keyword strings from production.
    cases = {
        # securities/disclosure actions (source's own taxonomy keywords)
        "성호전자, 14회차 신주인수권부사채 행사로 신주 39만6640주 발행":
            "디지털투데이 (DigitalToday), 성호전자, 14회차 신주인수권부사채 행사로 신주 39만6640주 발행, 성호전자,전자부품 제조업,코스닥,신주인수권행사,부채·채권,AI공시",
        "센서뷰 김병남 대표이사, 소유 특정증권등 수량 452만9454주 보고…소유 비율 6.41%":
            "디지털투데이 (DigitalToday), 센서뷰 김병남 대표이사, 소유 특정증권등 수량 452만9454주 보고…소유 비율 6.41%, 센서뷰,전자부품 제조업,코스닥,임원ㆍ주요주주특정증권등소유상황보고서,지배구조·경영권,AI공시",
        "엣지파운드리, 제15회차 전환사채 100억원 만기 전 취득…소각 예정":
            "디지털투데이 (DigitalToday), 엣지파운드리, 제15회차 전환사채 100억원 만기 전 취득…소각 예정, 엣지파운드리,전자부품 제조업,코스닥,전환사채(해외전환사채포함)발행후만기전사채취득,투자판단·경영,AI공시",
        "제일기획, 최대주주 삼성전자 등 주식 1만1320주 감소…계열사 삼성생명보험 특별계정 장내매도 영향":
            "디지털투데이 (DigitalToday), 제일기획, 최대주주 삼성전자 등 주식 1만1320주 감소…계열사 삼성생명보험 특별계정 장내매도 영향, 제일기획,광고업,코스피,최대주주등소유주식변동신고서,지배구조·경영권,AI공시",
        "세방전지, 자회사 세방리튬배터리에 600억원 채무보증 결정":
            "디지털투데이 (DigitalToday), 세방전지, 자회사 세방리튬배터리에 600억원 채무보증 결정, 세방전지,일차전지 및 이차전지 제조업,코스피,타인에대한채무보증결정,부채·채권,AI공시",
        "아비코전자, 자회사 아비코테크에 70억원 금전대여 연장 결정":
            "디지털투데이 (DigitalToday), 아비코전자, 자회사 아비코테크에 70억원 금전대여 연장 결정, 아비코전자,전자부품 제조업,코스닥,금전대여결정(자율공시),부채·채권,AI공시",
        "유니슨, 단일판매공급계약으로 주권 매매거래 정지":
            "디지털투데이 (DigitalToday), 유니슨, 단일판매공급계약으로 주권 매매거래 정지, 유니슨,일반 목적용 기계 제조업,코스닥,주권매매거래정지(단일판매공급계약),투자판단·경영,AI공시",
        "SK이노, SKIET 흡수합병…&quot;배터리 사업 리스크 차단&quot;":
            "디지털투데이 (DigitalToday), SK이노, SKIET 흡수합병…&quot;배터리 사업 리스크 차단&quot;, SK이노베이션,SKIET",
        # crypto / market chatter
        "비트코인 공급량 69% 수익권 진입…투입 자본 6170억달러는 아직 손실":
            "디지털투데이 (DigitalToday), 비트코인 공급량 69% 수익권 진입…투입 자본 6170억달러는 아직 손실, 암호화폐,비트코인",
        "[데일리픽] XRP 외면하는 블랙록?…스마트폰·PC 얼마나 더 오르나":
            "디지털투데이 (DigitalToday), [데일리픽] XRP 외면하는 블랙록?…스마트폰·PC 얼마나 더 오르나, 데일리픽,블랙록,XRP,비트코인,크립토,ETF,파생상품,글래스노드,창펑자오,스마트폰,컴퓨터,메모리,D램,육군,마이크로원자로,오픈AI,보안,넥슨,던파",
        # chatbot-product features ('메모리 공유' is an AI memory, not DRAM)
        "클로드, 채팅 기억 바로 작업에 반영…코워크와 메모리 공유":
            "디지털투데이 (DigitalToday), 클로드, 채팅 기억 바로 작업에 반영…코워크와 메모리 공유, 클로드,앤트로픽,코워크,메모리,통합,공유",
        # entertainment/production industry label
        "키이스트, KBS 사극 문무 제작 공급 계약 체결…225억4000만원 규모":
            "디지털투데이 (DigitalToday), 키이스트, KBS 사극 문무 제작 공급 계약 체결…225억4000만원 규모, 키이스트,영화 비디오물 방송프로그램 제작 및 배급업,코스닥,단일판매ㆍ공급계약체결,공급계약,AI공시",
    }
    for title, keywords in cases.items():
        decision = decision_for(DIGITALTODAY, title, metadata={"keywords": keywords})
        assert not decision.accepted, title
        assert decision.reason == "offbeat_source_keyword", title


def test_digitaltoday_keyword_stage_is_noop_without_keywords_metadata():
    # Without keywords the allowlist alone still rejects these (they carry no
    # vertical signal once the unanchored generic terms are gone).
    decision = decision_for(DIGITALTODAY, "성호전자, 14회차 신주인수권부사채 행사로 신주 39만6640주 발행")
    assert not decision.accepted
    assert decision.reason == "no_semiconductor_or_display_signal"


def test_digitaltoday_malformed_keyword_values_are_skipped_safely():
    assert decision_for(DIGITALTODAY, "와이씨, 삼성전자에 반도체 검사장비 1621억5000만원 규모 공급 계약", metadata={"keywords": 12345}).accepted
    assert decision_for(DIGITALTODAY, "와이씨, 삼성전자에 반도체 검사장비 1621억5000만원 규모 공급 계약", metadata={"keywords": None}).accepted
    assert decision_for(DIGITALTODAY, "와이씨, 삼성전자에 반도체 검사장비 1621억5000만원 규모 공급 계약", metadata={}).accepted


def test_digitaltoday_rejects_real_leakage():
    must_reject = [
        "애플, 미국서 애플TV 월 14.99달러로 인상",  # 'tv' inside 애플TV
        "우편 배달 중 불붙은 화물차 발견…집배원이 운전자 구했다",  # '전자' inside 운전자
        "금호건설, 평택고덕 STV 2차 지식산업센터 수분양자 중도금 대출 연대보증 271억원 결정",  # 'tv' inside STV
        "앤트로픽, 피지컬 AI로 확장...하드웨어판 MCP 'MHS' 공개",  # 'mcp' = Model Context Protocol
        "구글, 제미나이 노트북에 구매 도서 연동…책 내용으로 질문·생성 지원",
        "엔비디아, 어닝 서프라이즈에도 주가 하락...AI 과잉 투자 불안 반영",
        "엔비디아 지포스 나우, 연내 스팀 컨트롤러·스팀 머신 공식 지원",
        "삼성전자, 경상 수해 복구에 30억원 지원",
        "&quot;언제 어디서나 게이밍&quot; 삼성전자, 게임스컴서 '기기 연결' 전략 강조",
        "2분기 스마트폰 판매 톱10 &quot;아이폰 5종·갤럭시 5종&quot;",
        "삼성 '갤럭시 S26 FE' 출격…104만원대에 플래그십 성능 무장",
        "레인지로버 새 전기 GT 윤곽 드러나…2027년 상반기 생산 예정",
        "테슬라, 네바다 세미 공장 9월 개장식…연 5만대 생산 시험대",
        "서호전기, 중국 중공업사에 크레인 제어 시스템 137억원 규모 공급 계약",
        "유니슨, 동촌풍력발전에 고창해상풍력 풍력발전기 공급 계약…992억8700만원 규모",
        "한국정밀기계, 터키 TEI에 CNC VTL 78억원 규모 공급계약 체결",
        "유진테크놀로지, 헝가리 각형 자동차용 노칭금형 공급계약 48억원 수주",
        "아진전자부품, 한온시스템에 차량용 발향유닛 2028년부터 공급",
        "스패로우, 애플리케이션 시큐리티 서밋 2026 개최...C레벨 대상 SW 공급망 보안 전략 공유.",
        "넵튠, 카카오페이 미니게임 파트너사 선정…H5 게임 공급",
        "엔비디아·스트라이프가 노린 오픈웨이트 AI…빅테크 인수전 확산",
        "엔비디아, 18조원에 허깅페이스 인수 추진…오픈소스 AI 심장부까지 삼킨다",
        "리퀴드 AI, 스마트폰용 AI 벤치마크 앱 '피펫' 출시…무료 이용 가능",
        "모두싸인, 경남교육청 ‘고입전형 지원 온라인시스템’에 공공용 전자서명 제공",
        "엔비디아, AI 클라우드 매출 배분 프로그램 일부 거래 중단",
        "엔비디아, 美 규제에도 中과 손잡았다…딥시크·큐웬 지원 확대",
        "엔비디아 &quot;매출 70% 뛴다&quot;…애플·알파벳 제치고 아마존까지 넘보나",
    ]
    for title in must_reject:
        assert not decision_for(DIGITALTODAY, title).accepted, title


def test_digitaltoday_keeps_real_onbeat_titles():
    must_accept = [
        "디에스앤지, 네이버클라우드에 엔비디아 B300 GPU서버 389대 공급 계약",
        "와이씨, 삼성전자에 반도체 검사장비 1621억5000만원 규모 공급 계약",
        "피덜릭스, Alliance Memory에 메모리반도체 공급 계약 체결…계약금액 123억9217만원",
        "씨이랩, 한국인프라에 NVIDIA H200 NVL 38억9250만원 규모 공급 계약 체결",
        "엔비디아, 'NVHBM' 공개...HBM 컨트롤러 직접 설계",
        "빨라지는 SK하이닉스 메모리 시간표…팹 인프라 준공·착공 '착착'",
        "SK하이닉스, 미국 인디애나 패키징 팹 기공식 라이브 중계",
        "스마트폰·PC 원가 15~40% 오른다…범용 D램 부족發 악순환",
        "中 CXMT 생산 한계 도달…D램 공급난 완화 기대 꺾였다",
        "中 CXMT·YMTC 물량공세 예고…D램·낸드 공급 판도 바뀌나",
        "AI 메모리 호황이 바꾼 美 지방 도시…마이크론 500억달러 증설에 지역경제 '들썩'",
        "엔비디아보다 빠르고 효율적?…오픈AI, 자체 AI칩 '할라피뇨' 성능 공개",
        "IBM, Z 메인프레임·리눅스원용 Arm 듀얼 아키텍처 칩 개발",
        "당정, AI·3대 메가프로젝트 투자 총력…반도체 특별회계도 신설",
        "호남 반도체·AI 데이터센터 '예타 면제'…3대 메가 프로젝트 속도",
        "스페이스XAI, 엔비디아 '베라 CPU' 대규모 도입…2027년 우주 AI 시스템 구축",
        "애플 M6, 기본형 첫 3종 CPU 코어 구성 적용",
        "AMD, 모바일·데스크톱 CPU 점유율 사상 첫 30% 돌파…'인텔 천하' 흔든다",
        "1년 걸리던 반도체 칩 설계, 단 2주 만에…아키텍트랩스 '레드우드' 공개",
        "하나마이크론 &quot;시스템 반도체·패키징 경쟁력 높이겠다&quot;",
        "美 상무부, 중국 AI 기업 겨냥 반도체 우회 접근 차단 추진",
        "삼성전자,  세계 첫 360Hz OLED 게이밍모니터 공개",
        "톱텍, 모비스 북미 전동화 법인에 각형 REEV 배터리 조립라인 211억원 규모 공급 계약",
        "이노메트리, 미국에 ESS용 2차전지 검사장비 49억원 규모 공급 계약",
        "[모빌리티핫이슈] 로보택시 삼국지…中 전고체 배터리 상용화 질주",
        "마니커에프앤지, 용인 반도체 클러스터 조성에 토지 수용…556억2391만원 규모",
    ]
    for title in must_accept:
        assert decision_for(DIGITALTODAY, title).accepted, title


def test_digitaltoday_documented_residual_battery_polysemy():
    # Accepted trade-off: '배터리' stays in scope (editorial policy lists
    # relevant batteries), so two consumer-advice headlines in four days of
    # history still pass. Pinned here so the residual is explicit, not silent.
    for title in [
        "디지털 키 탑재 스마트폰, 배터리 방전되면 어떻게?",
        "전기차 교체 기준 달라졌다…배터리보다 '승하차 편의'가 변수",
    ]:
        assert decision_for(DIGITALTODAY, title).accepted, title


def test_digitaltoday_empty_title_rejected():
    assert not decision_for(DIGITALTODAY, "").accepted
