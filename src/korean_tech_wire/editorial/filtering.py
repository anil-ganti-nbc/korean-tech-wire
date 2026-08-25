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
SEMI_DISPLAY_SIGNAL_TERMS = THELEC_SIGNAL_TERMS + (
    "tsmc", "t-smash", "삼성전자", "sk하이닉스", "sk하이닉", "lg디스플레이", "엘지디스플레이",
    "마이크론", "인텔", "엔비디아", "amd", "퀄컴", "미쓰비시전기", "루멘스",
    "팹리스", "설비", "소부장", "에칭", "노광", "이온임플란트", "cvd", "pvd",
    "euv", "dram", "hbm4", "hbm3e", "mcp", "cis", "ddr", "gddr", "lpddr",
    "8세대", "11세대", "it디스플레이", "마이크로led", "qled", "산화물", "폴리머",
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
    if source.id in ("zdnet_korea_semi_display", "digitaltoday_semi_display"):
        title = article.title_original.casefold()
        if not any(term in title for term in SEMI_DISPLAY_SIGNAL_TERMS):
            return FilterDecision(False, "no_semiconductor_or_display_signal")
    return FilterDecision(True, "accepted")
