from .base import Collector, CollectorError
from .digitaltoday import GoogleNewsSitemapCollector
from .etnews import ETNewsCollector
from .lgdisplay import LGDisplayCollector
from .rss import RssCollector
from .samsung import SamsungNewsroomCollector
from .thelec import TheElecCollector
from .zdnet import ZdnetCollector

COLLECTORS = {
    "rss": RssCollector,
    "lgdisplay_html": LGDisplayCollector,
    "etnews_html": ETNewsCollector,
    "samsung_html": SamsungNewsroomCollector,
    "thelec_html": TheElecCollector,
    "zdnet_feed": ZdnetCollector,
    "gnews_sitemap": GoogleNewsSitemapCollector,
}

__all__ = ["COLLECTORS", "Collector", "CollectorError"]
