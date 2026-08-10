from .base import Collector, CollectorError
from .rss import RssCollector
from .samsung import SamsungNewsroomCollector
from .thelec import TheElecCollector

COLLECTORS = {
    "rss": RssCollector,
    "samsung_html": SamsungNewsroomCollector,
    "thelec_html": TheElecCollector,
}

__all__ = ["COLLECTORS", "Collector", "CollectorError"]
