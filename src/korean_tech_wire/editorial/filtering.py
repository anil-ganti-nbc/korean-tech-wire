from __future__ import annotations

from dataclasses import dataclass

from ..models import DiscoveredArticle, Source

THELEC_SIGNAL_TERMS = (
    "반도체", "메모리", "hbm", "dram", "d램", "nand", "낸드", "파운드리", "패키징", "후공정", "웨이퍼", "수율", "팹", "생산", "공급", "oled", "디스플레이", "패널", "배터리", "양극재", "음극재", "lfp", "스마트폰", "갤럭시", "노트북", "태블릿", "모니터", "tv", "전자", "부품", "센서", "칩", "gpu", "cpu", "apu", "ssd", "저장장치", "ai pc",
)

LGDISPLAY_LOW_VALUE_TERMS = (
    "교육생 모집", "채용", "채용연계", "직무교육", "아카데미", "인재 양성",
    "사회공헌", "봉사", "기부", "esg 리포트", "지속가능경영", "임직원",
)

ETNEWS_LOW_VALUE_TERMS = (
    "[et톡]", "[알림]", "[포토]", "교육생", "모집", "마라톤", "희망박스", "기부",
    "취임", "공동대표 체제", "대학", "전문대학원", "정책 전환", "격려", "[et시론]",
    "연회비", "시장,", "ai 행정", "ipo", "mou", "디스플레이 스쿨", "신용등급", "증권신고서", "인허가",
)

# ZDNet Korea and Digital Today are general-IT outlets: the campaign admits
# them ONLY as narrow semiconductor/display verticals, so the filter is a
# signal-term ALLOWLIST (same mechanism as The Elec) rather than a low-value
# denylist. A title with no semiconductor/display signal is rejected.
#
# Replay against 2026-08-25..29 accepted history showed the first-generation
# term list leaked ~50% off-beat via unanchored generic vocabulary:
#   - "전자" matched inside "운전자"/"안전자산"; "tv" inside "연합뉴스TV"/"STV";
#     "인텔" inside "인텔리전스"; "mcp" matched Model Context Protocol.
#   - bare "공급"/"생산"/"설비" matched crane/wind-turbine/CNC supply
#     disclosures, games and security-event stories.
#   - consumer-product nouns ("스마트폰", "갤럭시", "노트북", "모니터", "tv")
#     admitted launch-PR and market-ranking scope creep.
#   - semiconductor company names alone admitted CSR, donations, stock chatter
#     and games-com marketing (e.g. 엔비디아 주가, 삼성전자 수해 기부).
# The terms below keep the process/memory/display vocabulary and drop the
# unanchored generics; compounds ("생산라인", "설비투자", "2차전지", "ai칩",
# "데이터센터") carry the manufacturing-capacity signal instead.
SEMI_DISPLAY_SIGNAL_TERMS = (
    "반도체", "메모리", "hbm", "dram", "d램", "nand", "낸드", "파운드리", "패키징",
    "후공정", "웨이퍼", "수율", "팹", "팹리스", "양산", "준공", "착공", "증설",
    "생산라인", "생산능력", "설비투자",
    "oled", "디스플레이", "패널", "qled", "마이크로led", "it디스플레이", "8세대", "11세대",
    "산화물", "폴리머", "에칭", "노광", "이온임플란트", "cvd", "pvd", "euv", "소부장",
    "칩", "gpu", "cpu", "apu", "ssd", "저장장치", "코어", "ddr", "gddr", "lpddr", "cis",
    "배터리", "2차전지", "양극재", "음극재", "lfp", "센서", "ai pc",
    "ai칩", "데이터센터", "엑시노스",
    "tsmc", "t-smash", "sk하이닉스", "sk하이닉", "lg디스플레이", "엘지디스플레이",
    "마이크론", "인텔", "amd", "퀄컴", "미쓰비시전기", "루멘스", "nvidia",
)

# Pure corporate-finance actions and crypto/chatbot markets leak through any
# company or memory vocabulary, so Digital Today's own Google-News sitemap
# ``news:keywords`` (its standard disclosure/industry taxonomy) is checked
# FIRST and rejects those outright. ZDNet Korea carries no keywords metadata,
# so for it this stage is a no-op. Terms are the source's own taxonomy labels,
# not an open-ended denylist.
SEMI_DISPLAY_OFFBEAT_KEYWORD_TERMS = (
    # securities/disclosure actions (전환사채·BW·주주보고·거래정지·보증·대여·합병)
    "전환사채", "신주인수권", "채무보증", "금전대여", "매매거래정지",
    "소유상황보고서", "소유주식변동", "대량보유상황보고서", "흡수합병",
    # crypto/market chatter
    "비트코인", "암호화폐", "크립토",
    # chatbot-product features ("메모리 공유" is an AI memory, not DRAM)
    "클로드", "챗봇", "챗gpt",
    # entertainment/production industry label
    "영화 비디오물", "방송프로그램",
)

# "인텔리전스" (threat-intelligence vendors) must not satisfy the "인텔"
# company term; ZDNet accepted two such stories in four days.
THREAT_INTELLIGENCE_TERMS = ("인텔리전스",)

# Samsung Newsroom Korea is the company's own PR outlet: the homepage index
# mixes genuine semiconductor/display/manufacturing disclosures with a
# dominant stream of product marketing, CSR, entertainment and sports. The
# branch is fail-closed in two stages: Samsung's own PR-format section
# markers and campaign/exhibition nouns reject FIRST (so "[영상] 공용
# 디스플레이도…" style classroom marketing cannot ride the "디스플레이"
# signal term), then a semiconductor/display/manufacturing-capacity
# allowlist must still match. Samsung company names (삼성전자, 삼성…) are
# deliberately NOT signal terms — nearly every headline contains one.
SAMSUNG_NEWSROOM_PR_TERMS = (
    "[영상]", "[초대장]", "[카드뉴스]", "[인터뷰]",
    "갤럭시", "전시", "캠페인", "후원", "스폰서",
)
SAMSUNG_NEWSROOM_SIGNAL_TERMS = (
    "반도체", "메모리", "hbm", "dram", "d램", "nand", "낸드", "파운드리", "패키징",
    "후공정", "웨이퍼", "수율", "팹", "칩", "ssd", "저장장치", "엑시노스",
    "oled", "디스플레이", "패널", "qled", "마이크로led",
    "생산라인", "생산능력", "양산", "준공", "착공", "증설", "설비투자",
    "데이터센터", "ai칩", "gpu", "cpu",
)

@dataclass(frozen=True, slots=True)
class FilterDecision:
    accepted: bool
    reason: str

def classify(source: Source, article: DiscoveredArticle) -> FilterDecision:
    """Editorial relevance is intentionally separate from collector HTML rules."""
    if source.id == "the_elec":
        title = article.title_original.casefold()
        if not any(term in title for term in THELEC_SIGNAL_TERMS):
            return FilterDecision(False, "no_hardware_or_manufacturing_signal")
    if source.id == "lg_display_newsroom":
        title = article.title_original.casefold()
        if any(term in title for term in LGDISPLAY_LOW_VALUE_TERMS):
            return FilterDecision(False, "low_value_corporate_or_employer_pr")
    if source.id == "etnews_hardware":
        title = article.title_original.casefold()
        if any(term in title for term in ETNEWS_LOW_VALUE_TERMS):
            return FilterDecision(False, "low_value_section_item")
    if source.id == "samsung_newsroom_kr":
        title = article.title_original.casefold()
        if any(term in title for term in SAMSUNG_NEWSROOM_PR_TERMS):
            return FilterDecision(False, "newsroom_pr_or_corporate_story")
        if not any(term in title for term in SAMSUNG_NEWSROOM_SIGNAL_TERMS):
            return FilterDecision(False, "no_semiconductor_or_display_signal")
    if source.id in ("zdnet_korea_semi_display", "digitaltoday_semi_display"):
        title = article.title_original.casefold()
        keywords = article.metadata.get("keywords") if isinstance(article.metadata, dict) else None
        keyword_text = keywords.casefold() if isinstance(keywords, str) else ""
        if any(term in keyword_text for term in SEMI_DISPLAY_OFFBEAT_KEYWORD_TERMS):
            return FilterDecision(False, "offbeat_source_keyword")
        if any(term in title for term in THREAT_INTELLIGENCE_TERMS):
            return FilterDecision(False, "threat_intelligence_item")
        if not any(term in title for term in SEMI_DISPLAY_SIGNAL_TERMS):
            return FilterDecision(False, "no_semiconductor_or_display_signal")
    return FilterDecision(True, "accepted")
