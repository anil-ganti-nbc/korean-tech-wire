# Korean source landscape research

Research performed 2026-08-10. The statuses below describe research maturity, not publication quality. Nothing is production-approved.

## Stage 1 selection

| Source | Why selected | Mechanism | Status |
| --- | --- | --- | --- |
| The Elec (디일렉) | High editorial fit for semiconductor, display, battery and electronics reporting; Korean index exposes article links. | HTML index | EXPERIMENTAL |
| SK hynix Newsroom | Primary source for memory, HBM, manufacturing and corporate technology announcements; published RSS endpoint. | RSS/XML | EXPERIMENTAL |
| Samsung Newsroom Korea | Primary Korean corporate newsroom across devices, displays and semiconductors; predictable Korean paginated index. | HTML index, independently parsed | EXPERIMENTAL |

The two HTML collectors deliberately have different URL/index conventions, while SK hynix proves the structured RSS path. All use only public endpoints and no anti-bot workarounds. Fixtures cover parsing offline; live access remains a separate smoke test.

## Candidate records

### The Elec (디일렉)

- Name: The Elec (디일렉); Domain: `thelec.kr`; Organisation: 디일렉; Source type: specialist trade publication; Primary / secondary / aggregator: secondary, with meaningful original reporting; Language: Korean.
- Main beats: semiconductors, displays, batteries, finished electronics and IT; Original reporting level: high enough to merit experimental monitoring; Potential editorial value: high for supply-chain detail.
- RSS/API/sitemap: no reliable public structured endpoint confirmed in this pass; Article index: public HTML page links using `articleView.html?idxno=`; robots/access observations: public page loaded normally in research; Rate-limit concerns: poll sparingly and fetch only unseen links.
- Date/timezone: article page validation is still required; assumed KST for eventual source-specific parsing. Canonical URL: query identifier appears stable. Structured data/paywall/login/anti-bot: index public; article-depth and subscription behaviour need repeated validation. Translation difficulty: high for component and production terminology. Likely usefulness: high. Recommended status: EXPERIMENTAL.

### SK hynix Newsroom

- Name: SK hynix Newsroom; Domain: `news.skhynix.com`; Organisation: SK hynix; Source type: corporate newsroom; Primary / secondary / aggregator: primary; Language: Korean (with some other-language material possible).
- Main beats: HBM, DRAM, NAND, fabs, manufacturing, AI memory; Original reporting level: official rather than independent; Potential editorial value: high for attributable product/corporate information.
- RSS: `https://news.skhynix.com/feed/` responded as RSS/XML; Sitemap/API: not required for bootstrap; Article index: feed item links; robots/access: feed publicly exposed; Rate-limit: modest polling only. RSS publication dates include offsets and are normalised to UTC.
- Canonical URL/structured data: feed links are preserved; page-level metadata needs follow-up validation. Paywall/login/anti-bot: none observed for feed. Translation difficulty: technical naming is high but official English naming can assist. Likely usefulness: high. Recommended status: EXPERIMENTAL.

### Samsung Newsroom Korea

- Name: Samsung Newsroom Korea; Domain: `news.samsung.com/kr`; Organisation: Samsung Electronics; Source type: corporate newsroom; Primary / secondary /aggregator: primary; Language: Korean.
- Main beats: mobile, TV/display, consumer electronics, semiconductor announcements; Original reporting: official; Potential editorial value: high for launches and direct company claims, lower for independent supply-chain reporting.
- RSS: `https://news.samsung.com/kr/feed` exists but was not selected because the index is an independently useful HTML pattern; Sitemap/API: not confirmed; Article index: public homepage and `/kr/page/<n>` pagination with predictable Korean article slugs. Robots/access: public research result; rate-limit: low-frequency index polling.
- Date format: homepage displays `YYYY/MM/DD`; timezone KST unless a page gives an explicit offset. Canonical URL: Korean slug URL is retained. Structured data: page-level validation pending. Paywall/login/anti-bot: none observed on index. Translation difficulty: product terminology needs preservation. Likely usefulness: high. Recommended status: EXPERIMENTAL.

### DART / OpenDART

- Name: DART / OpenDART; Domain: `opendart.fss.or.kr`; Organisation: Financial Supervisory Service; Source type: public regulatory database; Primary: primary disclosure; Language: Korean, with English documentation.
- Main beats: material filings, investment, capacity, contracts, governance; Original reporting: primary; Potential editorial value: very high but substantial filtering is needed.
- API: official JSON and XML disclosure-search endpoints, authenticated with a required API key; original disclosures can be retrieved as XML. Article index: API query. Rate/access: documented authentication/usage policy; no bootstrap integration without a separate local credential. Dates use `YYYYMMDD`; Korean reporting context is KST. Recommended status: RESEARCH.

### Other researched leads

| Candidate | Finding | Status |
| --- | --- | --- |
| ETNews / Electronic Times | Public Korean technology categories include AI/software, semiconductors, electronics, mobility and telecom. Editorially useful but broad/noisy; needs article-page and access/paywall tests before parsing. | CANDIDATE |
| Samsung Display / Electro-Mechanics / SDI | Primary corporate sources worth cataloguing separately; no endpoint was validated in this bootstrap. | RESEARCH |
| LG Electronics / Display / Innotek | High-value primary-company leads; need Korean newsroom endpoint validation. | RESEARCH |
| Naver News / Daum / Google News Korea | Valuable discovery layers, but are aggregators and must resolve to original publisher pages before canonical ingestion. | RESEARCH |
| Korean certification and ministry databases | Potentially early product/regulatory signal, but source semantics and structured access have not yet been assessed. | RESEARCH |

## Production gate

Each source remains non-production until source research is complete, repeated live runs show access stability, article dates/timezones and canonical links are validated, Unicode and duplicates are checked, parser fixtures exist, and unexpected-empty behaviour is understood. The production allowlist is currently empty.

## Sources consulted

- Samsung Newsroom Korea: <https://news.samsung.com/kr/> and its RSS endpoint.
- SK hynix Newsroom RSS: <https://news.skhynix.com/feed/>.
- The Elec Korean index: <https://www.thelec.kr/>.
- ETNews: <https://www.etnews.com/>.
- OpenDART introduction and developer guide: <https://engopendart.fss.or.kr/intro/main.do> and <https://engopendart.fss.or.kr/guide/detail.do?apiGrpCd=DE001&apiId=AE00001>.
