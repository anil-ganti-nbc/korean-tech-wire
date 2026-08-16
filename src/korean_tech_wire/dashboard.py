"""Local Korean-language newsroom for owner field testing only."""
from __future__ import annotations

import html
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .config import load_settings, load_sources
from .runtime import revision
from .storage import Database


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "config.example.yaml"
SOURCES = ROOT / "config" / "sources.yaml"
OUTCOMES = ("USEFUL", "NOT_USEFUL", "DUPLICATE", "OFF_TOPIC", "NEEDS_REVIEW")


def e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def external(url: str | None) -> str:
    return f'<a class=external href="{e(url)}" target="_blank" rel="noreferrer">Original ↗</a>' if url else "—"


def badge(value: str) -> str:
    return f'<span class="badge {e(value.lower().replace("_", "-"))}">{e(value.replace("_", " "))}</span>'


def table(headers: tuple[str, ...], rows: list[tuple[str, ...]], empty_title: str, empty_detail: str) -> str:
    if not rows:
        return f'<div class=empty><b>{e(empty_title)}</b><span>{e(empty_detail)}</span></div>'
    head = "".join(f"<th>{e(column)}</th>" for column in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<div class=scroll><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _source_map() -> dict[str, object]:
    return {source.id: source for source in load_sources(SOURCES)}


def _database() -> tuple[Database, dict[str, object]]:
    settings = load_settings(CONFIG)
    database = Database(settings.database_path)
    database.migrate()
    sources = _source_map()
    database.sync_sources(sources.values())
    return database, sources


def _article_rows(database: Database, sources: dict[str, object], channel: str = "", source_filter: str = "") -> list[dict]:
    with database.connect() as con:
        rows = con.execute("SELECT * FROM articles WHERE record_status='valid' ORDER BY COALESCE(published_at, discovered_at) DESC, id DESC LIMIT 200").fetchall()
        feedback = con.execute("SELECT article_id,outcome,created_at FROM article_feedback ORDER BY created_at DESC").fetchall()
    latest_feedback = {}
    for item in feedback:
        latest_feedback.setdefault(item["article_id"], item["outcome"])
    result = []
    for row in rows:
        source = sources.get(row["source_id"])
        source_channel = source.status if source else "UNKNOWN"
        if channel and source_channel != channel:
            continue
        if source_filter and row["source_id"] != source_filter:
            continue
        item = dict(row)
        item["source_name"] = source.name if source else row["source_id"]
        item["channel"] = source_channel
        item["feedback"] = latest_feedback.get(row["id"])
        result.append(item)
    return result


def _style() -> str:
    return """<style>
:root{--bg:#08111d;--nav:#0c1727;--card:#111f31;--line:#26374d;--text:#e9eef7;--muted:#9baac0;--blue:#74b7ff;--green:#65df91;--amber:#f2bd4f;--red:#ff7770}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Segoe UI",sans-serif}a{color:#80bfff;text-decoration:none}.app{min-height:100vh;display:grid;grid-template-columns:210px 1fr;grid-template-rows:68px 1fr}header{grid-column:1/3;display:flex;align-items:center;gap:14px;padding:0 20px;background:#0b1524;border-bottom:1px solid var(--line)}.brand{font-size:17px;font-weight:760}.brand small,.muted,small{display:block;color:var(--muted);font-size:11px;font-weight:400}.pill,.badge{display:inline-block;border-radius:5px;font-size:10px;font-weight:800;letter-spacing:.04em;padding:4px 7px}.pill{color:#d5c2ff;background:#25235c;border:1px solid #4842a2}.provenance{color:var(--muted);max-width:460px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.spacer{flex:1}button{border:1px solid #3d4c66;background:#1a2b42;color:#eaf2ff;border-radius:5px;padding:7px 10px;font-weight:700;cursor:pointer}aside{background:var(--nav);border-right:1px solid var(--line);padding:12px}.navtitle{font-size:10px;color:var(--muted);letter-spacing:.08em;margin:15px 8px 5px}.nav{display:block;color:#d6dfed;padding:8px 10px;border-radius:5px;margin:2px 0}.nav.active{background:#302d80;color:#fff;font-weight:700}main{width:100%;max-width:1650px;margin:auto;padding:16px 20px}.summary{display:grid;grid-template-columns:1.35fr repeat(5,1fr);gap:10px}.metric,.card{background:var(--card);border:1px solid var(--line);border-radius:8px}.metric{min-height:87px;padding:12px}.label{font-size:10px;color:var(--muted);font-weight:800;letter-spacing:.06em}.number{font-size:25px;font-weight:780;margin:3px 0}.overall{border-color:#315173}.overall .number{color:var(--blue)}.grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(260px,1fr);gap:13px;margin-top:13px}.card{padding:13px}h2{font-size:15px;margin:0 0 10px}.sub{color:var(--muted);font-size:12px;margin:-5px 0 10px}.lead{padding:11px 0;border-bottom:1px solid #22324a}.lead:last-child{border:0}.headline{display:block;color:#f3f7fe;font-size:15px;font-weight:710;line-height:1.35;margin:4px 0 5px}.lead-meta{display:flex;gap:7px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:11px}.snippet{color:#bbc8da;font-size:12px;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.badge.production{background:#133f2c;color:var(--green)}.badge.experimental{background:#433514;color:var(--amber)}.badge.healthy,.badge.useful{background:#133f2c;color:var(--green)}.badge.failed,.badge.not-useful,.badge.off-topic{background:#4b252b;color:#ff9a93}.badge.needs-review,.badge.duplicate{background:#453713;color:var(--amber)}.badge.unknown{background:#29364a;color:#cbd6e6}.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.filters select{color:var(--text);background:#0d1a2b;border:1px solid #34465e;border-radius:5px;padding:7px}.source-health{margin-top:13px}.two{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:13px}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:var(--muted);font-size:10px;letter-spacing:.05em;padding:7px;border-bottom:1px solid var(--line)}td{padding:8px 7px;border-bottom:1px solid #213047;vertical-align:top}.empty{min-height:110px;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;color:var(--muted)}.empty b{color:#e2eaf5}.detail-title{font-size:22px;line-height:1.36;margin:4px 0 10px}.evidence{white-space:pre-wrap;color:#cad5e5;line-height:1.55;background:#0d1a2b;border:1px solid #26374d;border-radius:6px;padding:12px}.feedback{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.feedback button{font-size:11px}.footer{color:var(--muted);font-size:11px;text-align:center;margin:16px}@media(max-width:1000px){.app{grid-template-columns:1fr;grid-template-rows:68px auto 1fr}header{grid-column:1}.provenance{max-width:170px}aside{display:flex;overflow:auto;border-right:0;border-bottom:1px solid var(--line);padding:7px}.navtitle{display:none}.nav{white-space:nowrap}.summary,.grid,.two{grid-template-columns:1fr}}</style>"""


def render_overview(database: Database, sources: dict[str, object], query: dict[str, list[str]]) -> str:
    channel = query.get("channel", [""])[0].upper()
    source_filter = query.get("source", [""])[0]
    articles = _article_rows(database, sources, channel, source_filter)
    health_map = {item["source_id"]: item for item in database.health_summary(sources)}
    feedback = database.feedback_history()
    prod = sum(source.status == "PRODUCTION" for source in sources.values())
    experimental = sum(source.status == "EXPERIMENTAL" for source in sources.values())
    failed = sum(1 for item in health_map.values() if item["last_failure"] and not item["last_success"])
    lead_rows = []
    for article in articles[:40]:
        excerpt = (article["body_original"] or "").replace("\n", " ").strip()
        lead_rows.append(f'''<article class=lead><div class=lead-meta>{badge(article["channel"])} <b>{e(article["source_name"])}</b> <span>{e(article["published_at"] or article["discovered_at"])}</span> {badge(article["feedback"]) if article["feedback"] else ""}</div><a class=headline href="/articles/{article["id"]}">{e(article["title_original"])}</a><div class=lead-meta>{e(article["category"] or "Uncategorised")} · {external(article["canonical_url"])}</div>{f"<div class=snippet>{e(excerpt)}</div>" if excerpt else ""}</article>''')
    health_rows = []
    review_rows = []
    for source_id, source in sources.items():
        item = health_map.get(source_id, {})
        status = "HEALTHY" if item.get("last_success") else ("FAILED" if item.get("last_failure") else "UNKNOWN")
        note = "; ".join(item.get("recent_notes", [])[:1]) or "—"
        health_rows.append((f"<b>{e(source.name)}</b><small>{e(source_id)}</small>", badge(source.status), badge(status), e(item.get("last_success") or "—"), e(item.get("latest_accepted") if item.get("latest_accepted") is not None else "—"), e(note)))
        source_feedback = [row for row in feedback if row["source_id"] == source_id]
        useful = sum(row["outcome"] == "USEFUL" for row in source_feedback)
        negative = sum(row["outcome"] in {"NOT_USEFUL", "OFF_TOPIC", "DUPLICATE"} for row in source_feedback)
        review_rows.append((e(source.name), badge(source.status), e(item.get("last_success") or "—"), e(len([a for a in articles if a["source_id"] == source_id])), e(useful), e(negative)))
    with database.connect() as con:
        runs = con.execute("SELECT source_id,started_at,finished_at,status,summary_json FROM runs ORDER BY id DESC LIMIT 20").fetchall()
    run_rows = []
    for run in runs:
        summary = json.loads(run["summary_json"] or "{}")
        run_rows.append((e(sources.get(run["source_id"]).name if run["source_id"] in sources else run["source_id"] or "all"), e(run["started_at"]), badge((run["status"] or "UNKNOWN").upper()), e(summary.get("discovered", "—")), e(summary.get("new", "—"))))
    options = "".join(f'<option value="{e(key)}" {"selected" if source_filter == key else ""}>{e(value.name)}</option>' for key, value in sources.items())
    return f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Korean Tech Wire</title>{_style()}</head><body><div class=app><header><div class=brand>◈ Korean Tech Wire<small>Korean technology newsroom intelligence</small></div><span class=pill>FIELD TEST</span><span class=provenance title="{e(str(database.path.resolve()))}">Revision: {e(revision())}　|　Local DB: {e(database.path.name)}</span><span class=spacer></span><button onclick="location.reload()">↻ Refresh</button></header><aside><a class="nav active" href=/>▤　Overview</a><div class=navtitle>NEWSROOM</div><a class=nav href=#latest>◉　Latest Leads</a><div class=navtitle>SOURCES</div><a class=nav href="/?channel=PRODUCTION">●　Production</a><a class=nav href="/?channel=EXPERIMENTAL">◌　Experimental</a><a class=nav href=#health>♜　Source Health</a><div class=navtitle>REVIEW</div><a class=nav href=#review>✓　Source Review</a><a class=nav href=#feedback>✦　Feedback</a><div class=navtitle>SYSTEM</div><a class=nav href=#runs>◷　Run History</a><a class=nav href=#about>ⓘ　About</a></aside><main><section class=summary><div class="metric overall"><div class=label>OVERALL HEALTH</div><div class=number>{"ATTENTION" if failed else "LOCAL READY"}</div><small>{"Recorded source failure needs review" if failed else "Operational and editorial signals remain separate"}</small></div><div class=metric><div class=label>RECENT LEADS</div><div class=number>{len(articles)}</div><small>Filtered local view</small></div><div class=metric><div class=label>PRODUCTION</div><div class=number>{prod}</div><small>Operational maturity channel</small></div><div class=metric><div class=label>EXPERIMENTAL</div><div class=number>{experimental}</div><small>Under editorial evaluation</small></div><div class=metric><div class=label>NEEDS REVIEW</div><div class=number>{sum(a["feedback"] == "NEEDS_REVIEW" for a in articles)}</div><small>Owner feedback</small></div><div class=metric><div class=label>LATEST RUN</div><div class=number>{e(runs[0]["status"] if runs else "—")}</div><small>{e(runs[0]["started_at"] if runs else "No run recorded")}</small></div></section><section class=grid id=latest><div class=card><h2>Latest Leads</h2><p class=sub>Original Korean titles and evidence are preserved exactly. Production and experimental are source channels, not article-quality labels.</p><form class=filters method=get><select name=channel><option value="">All channels</option><option value=PRODUCTION {"selected" if channel == "PRODUCTION" else ""}>Production</option><option value=EXPERIMENTAL {"selected" if channel == "EXPERIMENTAL" else ""}>Experimental</option></select><select name=source><option value="">All sources</option>{options}</select><button type=submit>Filter</button><a href=/>Clear</a></form>{"".join(lead_rows) if lead_rows else '<div class=empty><b>No leads yet</b><span>Collected Korean technology leads will appear here.</span></div>'}</div><div class=card><h2>Editorial field test</h2><p class=sub>Mark usefulness without changing or deleting the underlying article. Source health is distinct from editorial quality.</p><p><b>Production</b><br><span class=muted>SK hynix Korea is the current approved channel.</span></p><p><b>Experimental</b><br><span class=muted>Samsung, The Elec, LG Display and ETNews are being evaluated for editorial precision.</span></p><p id=about class=muted>Local field-test state only. No collector, delivery, or production control is exposed here.</p></div></section><section class="card source-health" id=health><h2>Source Health</h2>{table(("Source","Channel","Health","Latest success","Accepted","Warning / evidence"),health_rows,"No source runs recorded","Collector health will appear after a local or scheduled run.")}</section><section class=two><section class=card id=review><h2>Source Review</h2>{table(("Source","Channel","Latest success","Visible leads","Useful","Negative"),review_rows,"No source review data","Owner feedback will accumulate here without changing source channels.")}</section><section class=card id=runs><h2>Run History</h2>{table(("Source","Started","Status","Discovered","New"),run_rows,"No runs recorded yet","Run history will appear after collector execution.")}</section></section><section class="card source-health" id=feedback><h2>Recent Editorial Feedback</h2>{table(("Article","Source","Outcome","When"),[(f'<a href="/articles/{row["article_id"]}">{e(row["title_original"])}</a>',e(sources.get(row["source_id"]).name if row["source_id"] in sources else row["source_id"]),badge(row["outcome"]),e(row["created_at"])) for row in feedback[:20]],"No feedback yet","Owner review history will appear as leads are evaluated.")}</section><div class=footer>Field Test Mode · Local data only · Korean text is shown without automatic translation</div></main></div></body></html>'''


def render_detail(database: Database, sources: dict[str, object], article_id: int) -> tuple[int, str]:
    with database.connect() as con:
        row = con.execute("SELECT * FROM articles WHERE id=? AND record_status='valid'", (article_id,)).fetchone()
    if not row:
        return 404, "<h1>Lead not found</h1>"
    article = dict(row)
    source = sources.get(article["source_id"])
    feedback = database.feedback_history(article_id)
    history = table(("Outcome", "Note", "Recorded"), [(badge(item["outcome"]), e(item["note"] or "—"), e(item["created_at"])) for item in feedback], "No feedback yet", "Use an explicit owner outcome below.")
    buttons = "".join(f'<button name=outcome value="{outcome}">{outcome.replace("_", " ")}</button>' for outcome in OUTCOMES)
    return 200, f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{e(article["title_original"])} · Korean Tech Wire</title>{_style()}</head><body><div class=app><header><div class=brand>◈ Korean Tech Wire<small>Lead evidence</small></div><span class=pill>FIELD TEST</span><span class=provenance>Revision: {e(revision())}　|　Local DB: {e(database.path.name)}</span><span class=spacer></span><a href="/">← Newsroom</a></header><aside><a class="nav active" href="/">▤　Overview</a><div class=navtitle>LEAD</div><a class=nav href="#evidence">▤　Evidence</a><a class=nav href="#feedback">✓　Feedback</a></aside><main><section class=card><div class=lead-meta>{badge(source.status if source else "UNKNOWN")} <b>{e(source.name if source else article["source_id"])}</b> <span>Published: {e(article["published_at"] or "—")}</span><span>Observed: {e(article["discovered_at"])}</span></div><h1 class=detail-title>{e(article["title_original"])}</h1><p class=muted>Category: {e(article["category"] or "—")}　·　Canonical identity: {e(article["source_id"])} / {e(article["canonical_url"])}</p>{external(article["canonical_url"])}</section><section class="card source-health" id=evidence><h2>Original Korean evidence</h2><p class=sub>Stored original-language content; no automatic transliteration or machine translation.</p><div class=evidence>{e(article["body_original"] or article["title_original"])}</div></section><section class="card source-health" id=feedback><h2>Editorial Feedback</h2><p class=sub>Records structured review history without mutating the article or source channel.</p><form method=post action=/feedback><input type=hidden name=article_id value="{article_id}"><div class=feedback>{buttons}</div></form><div class=source-health>{history}</div></section></main></div></body></html>'''


def serve(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    database, sources = _database()
    class Handler(BaseHTTPRequestHandler):
        def _html(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                body = json.dumps({"application": "KoreanTechWire", "status": "ok", "database": str(database.path.resolve()), "revision": revision()}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if parsed.path == "/": self._html(200, render_overview(database, sources, parse_qs(parsed.query))); return
            if parsed.path.startswith("/articles/"):
                try: article_id = int(parsed.path.rsplit("/", 1)[1])
                except ValueError: self.send_error(404); return
                status, body = render_detail(database, sources, article_id); self._html(status, body); return
            self.send_error(404)
        def do_POST(self) -> None:
            if self.path != "/feedback": self.send_error(404); return
            try:
                length = int(self.headers.get("Content-Length", "0")); form = parse_qs(self.rfile.read(length).decode("utf-8")); article_id = int(form.get("article_id", [""])[0]); outcome = form.get("outcome", [""])[0]
                if outcome not in OUTCOMES: raise ValueError("invalid outcome")
                database.add_feedback(article_id, outcome)
            except (ValueError, UnicodeDecodeError): self.send_error(400); return
            self.send_response(303); self.send_header("Location", f"/articles/{article_id}"); self.end_headers()
        def log_message(self, *_: object) -> None: pass
    return ThreadingHTTPServer((host, port), Handler)
