from .base import Collector, CollectorError
from .lgdisplay import LGDisplayCollector
from .rss import RssCollector
from .samsung import SamsungNewsroomCollector
from .thelec import TheElecCollector

COLLECTORS = {
    "rss": RssCollector,
    "lgdisplay_html": LGDisplayCollector,
    "samsung_html": SamsungNewsroomCollector,
    "thelec_html": TheElecCollector,
}

__all__ = ["COLLECTORS", "Collector", "CollectorError"]
