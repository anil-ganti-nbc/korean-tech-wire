# Korean source landscape research

Research performed 2026-08-10. The statuses below describe research maturity, not publication quality. Nothing is production-approved.

## Stage 1 selection

| Source | Why selected | Mechanism | Status |
| --- | --- | --- | --- |
| The Elec (디일렉) | High editorial fit for semiconductor, display, battery and electronics reporting; Korean index exposes article links. | HTML index | EXPERIMENTAL |
| SK hynix Newsroom Korea | Primary Korean source for memory, HBM, manufacturing and corporate technology announcements; stable Korean RSS endpoint. | RSS/XML | EXPERIMENTAL |
| Samsung Newsroom Korea | Primary Korean corporate newsroom across devices, displays and semiconductors; predictable Korean paginated index. | HTML index, independently parsed | EXPERIMENTAL |

The two HTML collectors deliberately have different URL/index conventions, while SK hynix proves the structured RSS path. All use only public endpoints and no anti-bot workarounds. Fixtures cover parsing offline; live access remains a separate smoke test.

## Candidate records

### The Elec (디일렉)

- Name: The Elec (디일렉); Domain: `thelec.kr`; Organisation: 디일렉; Source type: specialist trade publication; Primary / secondary / aggregator: secondary, with meaningful original reporting; Language: Korean.
- Main beats: semiconductors, displays, batteries, finished electronics and IT; Original reporting level: high enough to merit experimental monitoring; Potential editorial value: high for supply-chain detail.
- RSS/API/sitemap: no reliable public structured endpoint confirmed in this pass; Article index: public HTML page links using `articleView.html?idxno=`; robots/access observations: public page loaded normally in research; Rate-limit concerns: poll sparingly and fetch only unseen links.
- Date/timezone: article page validation is still required; assumed KST for eventual source-specific parsing. Canonical URL: query identifier appears stable. Structured data/paywall/login/anti-bot: index public; article-depth and subscription behaviour need repeated validation. Translation difficulty: high for component and production terminology. Likely usefulness: high. Recommended status: EXPERIMENTAL.

### SK hynix Newsroom Korea

- Name: SK hynix Newsroom Korea; Domain: `news.skhynix.co.kr`; Organisation: SK hynix; Source type: corporate newsroom; Primary / secondary / aggregator: primary; Language: Korean.
- Main beats: HBM, DRAM, NAND, fabs, manufacturing, AI memory; Original reporting level: official rather than independent; Potential editorial value: high for attributable product/corporate information.
- Live validation (2026-08-10): the original configuration, `https://news.skhynix.com/feed/`, returned RSS only after a `302` redirect to `/en/feed/`. It is technically healthy but English-language and therefore unsuitable for this Wire; this finding is retained rather than hidden.
- Korean source: `https://news.skhynix.co.kr/` is the canonical Korean newsroom on a separate `.co.kr` host. Its `https://news.skhynix.co.kr/feed/` endpoint returned `200 application/rss+xml`, Korean titles, Korean canonical article links and RFC-822 publication times; the feed is now configured experimentally. `https://news.skhynix.co.kr/wp-json/` and `wp-sitemap.xml` also returned public WordPress JSON/XML, but RSS is the smallest, sufficient Stage 1 access pattern.
- Access/structure: no login, paywall, or anti-bot challenge observed in host-side checks; use modest polling. Feed dates were emitted as UTC (`+0000`) in the observed Korean feed and are normalised to UTC by the collector. Translation difficulty remains high for memory and manufacturing terminology. Likely usefulness: high. Recommended status: EXPERIMENTAL pending fixture-backed configuration test and host-side live validation of this **Korean** endpoint.

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
| ETNews / Electronic Times | Public Korean Semiconductor taxonomy has usable sub-sections and explicit article timestamps. | EXPERIMENTAL |
| Samsung Display / Electro-Mechanics / SDI | Primary corporate sources worth cataloguing separately; no endpoint was validated in this bootstrap. | RESEARCH |
| LG Electronics / Display / Innotek | High-value primary-company leads; need Korean newsroom endpoint validation. | RESEARCH |
| Naver News / Daum / Google News Korea | Valuable discovery layers, but are aggregators and must resolve to original publisher pages before canonical ingestion. | RESEARCH |
| Korean certification and ministry databases | Potentially early product/regulatory signal, but source semantics and structured access have not yet been assessed. | RESEARCH |

## Production gate

Each source remains non-production until source research is complete, repeated live runs show access stability, article dates/timezones and canonical links are validated, Unicode and duplicates are checked, parser fixtures exist, and unexpected-empty behaviour is understood. The production allowlist began empty and changes only through an explicit documented promotion.

## Stage 2 SK hynix Korea production audit — 2026-08-10

The Korean RSS endpoint exposed a rolling window of 10 recent items during repeated host checks; this is the initial observable baseline, not a historical archive. Items were newest-first, Korean-language, and carried RFC-822 UTC timestamps, canonical Korean `.co.kr` links, and WordPress GUIDs. Multiple entries can share a headline while retaining distinct canonical URLs/GUIDs, so URL identity preserves updates/variants without collapsing them. Repeated live runs were stable and idempotent. SK hynix Korea is therefore the first **PRODUCTION** source; Samsung and The Elec remain **EXPERIMENTAL**.

## Stage 3 expansion research — 2026-08-10

| Candidate | Originality / beat value | Access evidence | Decision |
| --- | --- | --- | --- |
| ETNews | High potential for Korean electronics, semiconductor and component reporting; likely complementary to The Elec. | Public RSS guide exposes `Section901.xml` as a broad “today’s news” stream, but a reliable hardware-only feed was not validated. | DEFERRED: do not ingest the broad stream without section-level signal. |
| Digital Daily | Potentially useful IT/industry reporting. | No stable structured Korean endpoint validated in this pass. | RESEARCH |
| ZDNet Korea | Broad technology coverage; likely higher duplicate/noise risk. | Historic FeedBurner references exist, but current publisher-controlled endpoint and hardware focus were not verified. | DEFERRED |
| LG Display | High primary-source relevance for OLED, panels and manufacturing. | Publisher-rendered Korean Latest News archive has stable five-card pages and `contentId` detail identities. | EXPERIMENTAL |
| LG Electronics | Useful primary product/display source but potentially high PR volume. | Official Korean newsroom is public and Korean-language. | RESEARCH |
| DART / OpenDART | Highest primary-source proximity for filings, capex and contracts. | Official JSON/XML disclosure-list API requires a 40-character `crtfc_key`; original disclosure XML is available through the official service. | DEFERRED PENDING CREDENTIAL |

### DART feasibility

OpenDART is technically suitable for an experimental, watchlist-only collector. The official disclosure-list API supports company/date/type filters and JSON or XML responses; it requires an authentication key obtained from OpenDART. Keep the credential in an environment variable such as `KOREAN_TECH_WIRE_DART_API_KEY` or ignored local configuration—never in Git. A later collector should start with an explicit configurable watchlist (Samsung Electronics, SK hynix, LG Electronics, LG Display, Samsung SDI and selected component firms), retain filing ID/title/date/type and official reference URL, and filter metadata before fetching documents. No credential was provided, so no DART ingestion is enabled.

### Stage 3 selection rationale

No new source was enabled merely to meet a numerical quota. The current evidence supports further controlled implementation work for a Korean LG Display source and an ETNews hardware subsection only after their exact endpoints and fixtures are validated. This preserves the Wire’s information-advantage goal and avoids converting broad Korean publication volume into noise.

### ETNews hardware-section validation — 2026-08-10

ETNews is now the second independent specialist-journalism channel and is **EXPERIMENTAL** only. The broad `rss.etnews.com` “today” stream remains rejected: it is not the discovery source. The selected publisher taxonomy is the first-party Semiconductor section (`id1=10`) and its specific sub-sections: Semiconductor (`id2=061`), Display (`062`), Battery (`064`), and Materials/Equipment (`044`). Their public archive URLs accept `page=N` pagination and render current cards in `ul.news_list`, with a Korean title, first-party numeric article URL, and visible `YYYY-MM-DD HH:MM` KST date. The collector polls only the current first page of these selected sections, preserves the section provenance, and deduplicates overlapping cards by canonical numeric URL.

The parent Electronics section (`id1=06`) was rejected: recent cards were dominated by consumer appliances, retail promotions and photo duplicates. Other main sections (AI·SW, telecommunications, economy, platform/distribution, politics) were outside the intended hardware slice. `latest-news/rss`, `/rss.xml`, `/feed/`, `/wp-json/`, and `/api/` style routes were not selected; ETNews exposes an RSS link, but the previously observed RSS guide corresponds to a broad stream, not a verified hardware-section feed. The publisher site itself supplies stable structured HTML; no aggregator, XHR-only, mobile-only, or sitemap mechanism is required.

Recent first-page sampling covered 52 unique cards across the four selected sections (cross-section overlap accounts for fewer than 60): semiconductor had the strongest original-reporting density, followed by display and battery; materials/equipment had useful CPO, equipment and component stories but the highest leakage of civic, association and generic-management items. The small secondary filter rejects only explicit low-value classes leaked by those source categories (opinion, notices/photos/events, recruitment/education, civic/political, generic management/awards/IPO/MOU); it is not a broad keyword substitute for taxonomy. The final live selection was 52 discovered / 35 accepted / 17 rejected.

ETNews article detail pages provide a canonical link and Open Graph `article:published_time` such as `2026-08-10T13:13:26+09:00`; this is the authoritative source for seconds-precision extraction and UTC normalisation. The index timestamp remains as provenance/fallback only. Examples from the validation sample: **strong hits** include Sony/TSMC's JASM image-sensor investment, LX Semicon supplying a domestic automotive MCU to Hyundai/Kia, Hanmi Semiconductor's US subsidiary, CSOT's inkjet-OLED monitor/laptop push, LG Display tandem-OLED cost work, and LFP material/production developments. **Potentially useful** coverage includes memory-cycle analysis, supplier earnings, and display/battery market context. The rejected **noise** was notices, association membership, civic announcements, education, and generic-management material.

The active The Elec sample contains independent Korean supply-chain reporting such as BOE panels in Hyundai's Avante, Samsung Electro-Mechanics glass-substrate materials, and LG Energy Solution's Honda project. ETNews overlaps on broad themes (OLED, memory, Korean capex) but contributes different sources and details: TSMC/Sony investment, automotive MCU supply, Chinese panel capacity, CPO equipment, and materials/battery execution. The two sources are deliberately not globally deduplicated: separately reported coverage of one event is useful corroboration. Initial ETNews rating: **HIGH VALUE**, subject to continued experimental monitoring because Materials/Equipment has the highest residual noise.

Host-Windows validation was required because the Codex sandbox blocks outbound HTTPS before TLS/HTTP. First ETNews run: 52 discovered, 44 accepted under the initial narrow filter, 8 rejected, 44 new, 44 timestamped, no source or extraction failures. Repeat: 52/44/8, 0 new and 44 existing, no failures, zero duplicate canonical identities. After the conservative refinement: 52 discovered, 35 accepted, 17 rejected, 35 existing and timestamped, no failures. LG Display regression remained 5/4/1 with 4 existing and timestamped; `run --production` executed only SK hynix, which remained 10/10 accepted and timestamped with no failures.

### Stage 3 completion decision

Stage 3 is technically complete: it has one healthy production source (SK hynix), two high-value experimental primary sources (Samsung Newsroom Korea and LG Display), and two useful specialist-journalism channels (The Elec and ETNews), all with source-specific discovery/extraction, fixtures, failure isolation and host validation. ETNews and all other experimental sources remain outside the production allowlist; promotion is a separate quality/reliability decision. DART remains credential-dependent: `KOREAN_TECH_WIRE_DART_API_KEY` is the only planned route, with no fabricated or bypass integration. Deferred/rejected expansion paths are the broad ETNews RSS and Electronics section; Digital Daily and ZDNet Korea remain research candidates. Recommended Stage 4 scope: observe repeated multi-day source health and editorial yield, decide source promotions explicitly, and add DART only after a user-provided OpenDART key.

## Stage 4 baseline — 2026-08-10

Stage 4 adds a portable foreground soak command and SQLite-backed `health` view; promotion policy is in `docs/promotion-policy.md`, and new-item review evidence is in `docs/stage4-editorial-yield.md`. The soak command invokes the normal collector runner per source and per cycle, stores no fabricated success state, stops cleanly on interruption, and resumes through the existing database history. The documented normal interval is two hours; the short initial baseline is not represented as a multi-day soak.

The corrected health baseline reports SK hynix: 9 successful runs, latest 10/10 accepted/timestamped; LG Display: 7 successes, latest 5 discovered/4 accepted/1 rejected/4 timestamped; ETNews: 5 successes, latest 52/35/17/35; The Elec: 2 successes, latest 34/15/19/15; Samsung: 2 successes, latest 48/48/0/35. There are no source/parser failures, classified environment failures, unexpected-zero events, or duplicate canonical identities in the local current history. The initial Stage 4 cycle produced no new articles, so the yield log is intentionally empty.

Promotion decisions at the baseline are **CONTINUE EXPERIMENTAL** for LG Display, ETNews and The Elec: all are technically promising/high-value, but the current observations are a short same-day baseline rather than representative unattended operation. Samsung also remains **CONTINUE EXPERIMENTAL** because its atypical time coverage is understood but it is not a priority promotion candidate. SK hynix remains the only **PRODUCTION** control source. Stage 4 remains open pending ordinary spaced soak cycles and new-item editorial-yield evidence; no lifecycle was changed.

### LG Display Korean Latest News validation — 2026-08-10

LG Display is now the first new Stage 3 **EXPERIMENTAL** source. The selected publisher-controlled discovery URL is <https://www.lgdisplay.com/kor/company/media-center/latest-news>. It returns server-rendered Korean cards in `ul.board_col_list.type2`; the documented, working pagination is `?page=N&size=5`. Each card exposes a Korean title, a publisher date (`YYYY-MM-DD`) and a first-party detail URL of the form `...?contentId=<integer>`. The detail template repeats its title and date in `h3.tit_bv_ns` and `span.date_bv_ns`. The `contentId` is the stable source identity and the full first-party URL is canonical.

Endpoint checks were deliberately conservative. `robots.txt` allows crawling. `latest-news/rss` returned 404; `/rss.xml`, `/feed/`, `/wp-json/`, and `/api/` returned the site shell rather than a verified RSS/Atom, WordPress REST, or JSON news API. `/sitemap.xml` advertises XML but was not a dependable article-discovery source in host inspection (one request reset and the XML-named response was an HTML site page), so it is not used. The structured HTML archive is consequently the simplest reliable publisher surface; it does not depend on aggregators or browser-only application state.

The archive has one visible card flag, `PR`, across both technical and non-technical material, so it is not useful taxonomy. The experimental filter instead rejects clear classes of generic employer/CSR material: training/recruitment, social-contribution/donation, generic ESG-reporting, and employee-branding titles. It retains OLED/LCD/panel technology, monitor/TV/mobile/automotive display, manufacturing, production/capex, supply, and technology-investment announcements. This is intentionally a narrow exclusion rule rather than a large affirmative-keyword net; uncertain corporate material remains available for audit.

The publisher provides a date but no time of day. The collector records that authoritative Korean publication date at KST midnight and normalises it to UTC, retaining the raw publisher date in metadata. It does not infer a missing calendar date or borrow HTTP/sitemap time. This preserves the available source precision while making the record sortable in the current datetime-only model.

Host validation used the normal Windows network because the Codex sandbox blocks outbound HTTPS before TLS/HTTP. First live run: 5 discovered, 4 accepted, 1 rejected, 4 new, 4 timestamped, 0 source failures, 1 isolated detail-fetch failure. Second run: 5 discovered, 4 accepted, 1 rejected, 0 new, 4 existing, 4 timestamped, 0 extraction failures, 0 source failures. The four persisted canonical URLs were unique. Accepted sample and yield assessment: (1) a KRW 3 trillion OLED technology/production-infrastructure investment is a **strong hit**; (2) K-Display 2026 OLED technology exhibition is a **strong hit**; (3) a gaming-OLED monitor performance-study announcement is a **strong hit**; (4) half-year results are **potentially useful** for capacity/financial context. The generic ESG report was rejected as **noise**. Initial rating: **HIGH VALUE** as a primary display/manufacturing source, with the qualification that it is not independent journalism and remains experimental.

## Live validation record — 2026-08-10

The Elec and Samsung Newsroom Korea both passed host-Windows DNS, HTTPS GET and live discovery validation: The Elec discovered 65 references and Samsung discovered 26. This supersedes no historical data: earlier `WinError 10013` runs came from the Codex execution sandbox, where outbound HTTPS connections were blocked before TLS/HTTP, while the normal Windows host reached the same endpoints successfully. Those run records remain valid evidence of the execution environment, not source-health failures.

The same live inspection initially found no stored source publication timestamp for The Elec or Samsung, and Samsung’s generic parser had persisted category/navigation and media-library links. These findings drove the Stage 1 hardening work: Samsung now accepts only `article_lists` article cards and extracts detail-page JSON-LD; The Elec now polls only its public technology-section indexes and extracts detail-page Open Graph/JSON-LD time. Both remain experimental pending post-change live validation.

Samsung’s remaining timestamp gap was audited after hardening. The 13 active rows are not an unhandled normal-news template: 1 is a `미래동행` multimedia page with blank `NewsArticle.datePublished` and a separate `VideoObject` date; 1 is an overseas video page with only `VideoObject.datePublished`; and 11 are overseas-news pages with no detail-page article time. Their index date remains preserved as raw metadata, but no time is fabricated or borrowed from video metadata.

The Elec source taxonomy observed in the public navigation includes `반도체` (Semiconductors), `디스플레이` (Displays), `배터리` (Batteries), `완성품` (Finished Products), `금융` (Finance), `바이오` (Bio), and other broad sections. Stage 1 requests the first four, but live validation showed the returned pages can still expose broad-index links. Therefore category selection is a useful narrowing signal, not a correctness guarantee; a separate conservative hardware/manufacturing classifier rejects unrelated candidates.

## Sources consulted

- Samsung Newsroom Korea: <https://news.samsung.com/kr/> and its RSS endpoint.
- SK hynix Korean Newsroom and RSS: <https://news.skhynix.co.kr/> and <https://news.skhynix.co.kr/feed/>; the separate English feed finding is <https://news.skhynix.com/feed/>.
- The Elec Korean index: <https://www.thelec.kr/>.
- ETNews: <https://www.etnews.com/>.
- OpenDART introduction and developer guide: <https://engopendart.fss.or.kr/intro/main.do> and <https://engopendart.fss.or.kr/guide/detail.do?apiGrpCd=DE001&apiId=AE00001>.

---

## Addendum (2026-08-25): campaign P0/P1 pass — KIPOST, ZDNet Korea, Digital Today, KBench, Bloter

Live reconnaissance per candidate before any implementation decision:

### KIPOST — REJECT (source defunct)
- kipost.com serves a hugeDomains.com parking page (domain for sale).
- kipost.co.kr serves a cafe24 "site does not exist" placeholder script.
- kipost.kr and kipostnews.com are unreachable.
- No live publication remains to extract from. Re-evaluate only if the
  outlet returns under a new canonical domain.

### ZDNet Korea (semiconductor/display vertical) — ADD (EXPERIMENTAL)
- robots.txt officially declares feeds:
  Sitemap: https://zdnet.co.kr/feed/article_list.xml (+ _2).
- Feed entries carry article URLs (/view/?no=YYYYMMDDHHMMSS, the
  publisher's own KST publish instant) and lastmod; article pages
  server-render og:title. Verified live 2026-08-25.
- Extraction: feed -> newest-first by no=-derived timestamp (cap 20/run)
  -> per-article og:title. Vertical enforced downstream by signal-term
  allowlist (editorial/filtering.py SEMI_DISPLAY_SIGNAL_TERMS).
- Registered as zdnet_korea_semi_display, status EXPERIMENTAL.

### Digital Today (semiconductor/display vertical) — ADD (EXPERIMENTAL)
- robots.txt declares sitemap.xml, a Google News sitemap carrying
  news:title + news:publication_date + news:keywords per URL — title,
  timestamp and canonical URL in ONE request; lowest maintenance surface
  found in this pass.
- robots.txt disallows /news/articleList.html for User-agent: *; this
  collector reads ONLY the declared sitemap and never touches listing
  pages.
- Registered as digitaltoday_semi_display, status EXPERIMENTAL.

### KBench (P1) — DEFER (marginal value)
- ?rss endpoint returns HTML, not XML; no declared structured feed found.
- Marginal-value rule: ZDNet Korea + Digital Today already capture most of
  KBench's semiconductor/display overlap via existing The Elec/ETNews
  coverage. Revisit only if soak shows a distinct KBench-only story class.

### Bloter (P1) — DEFER (access + marginal value)
- bloter.net/rss unreachable from the recon environment (connection
  failure); semiconductor coverage overlaps heavily with ZDNet Korea's.
- Per campaign rules: no anti-bot engineering; secondary references can
  recover blocked-source stories later.

### Duplicate/overlap observation plan
During the next soak, per-source yield logs should record overlap between
zdnet_korea_semi_display, digitaltoday_semi_display, the_elec and
etnews_hardware on the same story (same company+event within 24h). If
either new source adds <10% unique stories over a full soak window, it is
a REJECT/retire candidate at its first promotion review.
