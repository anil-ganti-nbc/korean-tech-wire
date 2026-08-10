from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


class LinkIndexParser(HTMLParser):
    def __init__(self, base_url: str, accepted_path: str):
        super().__init__(); self.base_url, self.accepted_path = base_url, accepted_path
        self.links: list[tuple[str, str]] = []; self._href: str | None = None; self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._href, self._text = urljoin(self.base_url, href), []

    def handle_data(self, data: str) -> None:
        if self._href: self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            title = " ".join("".join(self._text).split())
            if self.accepted_path in self._href and title:
                self.links.append((self._href, title))
            self._href = None
