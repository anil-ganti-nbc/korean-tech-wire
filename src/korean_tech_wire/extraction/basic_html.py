from html.parser import HTMLParser

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts: list[str] = []; self._ignore = 0
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer"}: self._ignore += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer"}: self._ignore = max(0, self._ignore - 1)
    def handle_data(self, data):
        if not self._ignore: self.parts.append(data)

def extract_text(html: str) -> str | None:
    """A conservative fallback for experimental sources, not a site-specific parser."""
    parser = _TextParser(); parser.feed(html)
    text = " ".join(" ".join(parser.parts).split())
    return text or None
