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


