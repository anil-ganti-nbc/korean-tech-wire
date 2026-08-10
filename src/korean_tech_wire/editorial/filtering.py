from __future__ import annotations

from dataclasses import dataclass

from ..models import DiscoveredArticle, Source

THELEC_SIGNAL_TERMS = (
    "반도체", "메모리", "hbm", "dram", "d램", "nand", "낸드", "파운드리", "패키징", "후공정", "웨이퍼", "수율", "팹", "생산", "공급", "oled", "디스플레이", "패널", "배터리", "양극재", "음극재", "lfp", "스마트폰", "갤럭시", "노트북", "태블릿", "모니터", "tv", "전자", "부품", "센서", "칩", "gpu", "cpu", "apu", "ssd", "저장장치", "ai pc",
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
    return FilterDecision(True, "accepted")
