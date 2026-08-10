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
    return FilterDecision(True, "accepted")
