"""Local Korean-language newsroom for owner field testing only."""
from __future__ import annotations

import html
import ipaddress
import json
import os
import secrets
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from .config import load_settings, load_sources
from .discovery import run_collectors
from .locking import LockUnavailable, RunLock
from .runtime import revision
from .storage import Database
from .storage.qc_archive import QC_DECISIONS, AlreadyDecided, QCArchive


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parents[2]
# KOREAN_TECH_WIRE_CONFIG lets a native launcher point the dashboard at the
# same local config it already validated (e.g. config/config.local.yaml on
# Windows) instead of silently falling back to the tracked example config.
# Without this, editing config.local.yaml (database_path, timeouts, user
# agent) would have no effect on the dashboard even though the CLI health
# check and `run` command both honour it.
CONFIG = Path(os.environ["KOREAN_TECH_WIRE_CONFIG"]) if os.environ.get("KOREAN_TECH_WIRE_CONFIG") else ROOT / "config" / "config.example.yaml"
SOURCES = ROOT / "config" / "sources.yaml"
OUTCOMES = ("USEFUL", "NOT_USEFUL", "DUPLICATE", "OFF_TOPIC", "NEEDS_REVIEW")


class CollectionController:
    """One manual local run at a time, using the canonical collector core."""

    def __init__(self, database: Database, sources: dict[str, object]):
        self.database = database
        self.sources = sources
        self._guard = threading.Lock()
        self._state: dict[str, object] = {"status": "IDLE", "running": False, "sources": {}}

    def snapshot(self) -> dict[str, object]:
        with self._guard:
            state = json.loads(json.dumps(self._state))
        if state.get("running") and state.get("started_monotonic"):
            state["elapsed_seconds"] = round(time.monotonic() - float(state["started_monotonic"]), 1)
        state.pop("started_monotonic", None)
        return state

    def start(self, source_id: str | None = None) -> bool:
        with self._guard:
            if self._state.get("running"):
                return False
            self._state = {
                "status": "STARTING", "running": True, "current_source": None,
                "started_monotonic": time.monotonic(), "sources": {}, "error": None,
            }
        threading.Thread(target=self._run, args=(source_id,), name="ktw-local-collection", daemon=True).start()
        return True

    def _progress(self, event: str, source: object, detail: dict[str, object]) -> None:
        source_id = source.id
        with self._guard:
            self._state["current_source"] = source_id if event == "started" else None
            self._state["status"] = "RUNNING"
            self._state["sources"][source_id] = {"name": source.name, "status": event.upper(), **detail}

    def _run(self, source_id: str | None) -> None:
        try:
            settings = load_settings(CONFIG)
            lock_path = settings.database_path.with_name(settings.database_path.name + ".lock")
            # "Run all collectors" (source_id is None) never silently includes
            # EXPERIMENTAL/soak sources -- explicitly targeting one source by
            # id (the individual per-collector control) is the only way to
            # run an EXPERIMENTAL collector from the dashboard.
            with RunLock(lock_path):
                summary = run_collectors(list(self.sources.values()), settings, self.database, source_id=source_id, production_only=(source_id is None), progress=self._progress)
            with self._guard:
                self._state.update({"status": "COMPLETED" if not summary.failed else "COMPLETED_WITH_ERRORS", "running": False, "current_source": None, "summary": asdict(summary)})
        except LockUnavailable as error:
            with self._guard:
                self._state.update({"status": "LOCKED", "running": False, "current_source": None, "error": str(error)})
        except Exception as error:
            with self._guard:
                self._state.update({"status": "FAILED", "running": False, "current_source": None, "error": f"{type(error).__name__}: {error}"})


def e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def external(url: str | None) -> str:
    return f'<a class=external href="{e(url)}" target="_blank" rel="noreferrer">Original ↗</a>' if url else "—"


def badge(value: str) -> str:
    return f'<span class="badge {e(value.lower().replace("_", "-"))}">{e(value.replace("_", " "))}</span>'


# Fleet Law 3 (health honesty): HTTP success without useful output is not
# healthy after policy cycles, and a badge must not stay HEALTHY forever
# off an ancient success. STALE_AFTER bounds how old the last success may
# be while still counting as HEALTHY; it deliberately exceeds the backoff
# ceiling (24h) so a HOST-BLOCKED lane in deep backoff shows as BLOCKED,
# not as a flapping failure.
STALE_AFTER = timedelta(hours=48)
_BLOCKED_TOKENS = ("403", "forbidden", "blocked", "cloudflare", "rate limit")


def health_state(item: dict[str, object], now: datetime | None = None) -> str:
    """Recency-aware, block-aware source health state.

    HEALTHY  — a success exists and is recent enough.
    STALE    — a success exists but is older than STALE_AFTER (green-process
               / dead-source drift becomes visible instead of hiding).
    BLOCKED  — failure notes indicate host/edge blocking and the success is
               missing or stale; surfaced distinctly from generic failure
               (SK hynix AWS-ELB specimen).
    FAILED   — failures exist and no success ever recorded.
    UNKNOWN  — nothing recorded either way.
    """
    now = now or datetime.now(timezone.utc)

    def _parse(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    last_success = _parse(item.get("last_success"))
    last_failure = _parse(item.get("last_failure"))
    notes = " ".join(item.get("recent_notes") or []).lower()
    blocked_signal = any(token in notes for token in _BLOCKED_TOKENS)
    fresh_success = last_success is not None and (now - last_success) <= STALE_AFTER

    if blocked_signal and not fresh_success:
        return "BLOCKED"
    if fresh_success:
        return "HEALTHY"
    if last_success is not None:
        return "STALE"
    if last_failure is not None:
        return "FAILED" if not blocked_signal else "BLOCKED"
    return "UNKNOWN"


def table(headers: tuple[str, ...], rows: list[tuple[str, ...]], empty_title: str, empty_detail: str) -> str:
    if not rows:
        return f'<div class=empty><b>{e(empty_title)}</b><span>{e(empty_detail)}</span></div>'
    head = "".join(f"<th>{e(column)}</th>" for column in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<div class=scroll><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _source_map() -> dict[str, object]:
    return {source.id: source for source in load_sources(SOURCES)}


def _qc_archive_path(database: Database) -> Path:
    return database.path.with_name("qc_archive.db")


def _database() -> tuple[Database, dict[str, object], QCArchive]:
    settings = load_settings(CONFIG)
    database = Database(settings.database_path)
    database.migrate()
    sources = _source_map()
    database.sync_sources(sources.values())
    # QC decisions live in their own on-disk file, never in the live
    # collector database -- see storage/qc_archive.py for why. This never
    # migrates or mutates korean_tech_wire.db's own schema.
    archive = QCArchive(_qc_archive_path(database))
    archive.migrate()
    return database, sources, archive


def _article_rows(database: Database, sources: dict[str, object], channel: str = "", source_filter: str = "", archive: QCArchive | None = None) -> list[dict]:
    with database.connect() as con:
        rows = con.execute("SELECT * FROM articles WHERE record_status='valid' ORDER BY COALESCE(published_at, discovered_at) DESC, id DESC LIMIT 200").fetchall()
        feedback = con.execute("SELECT article_id,outcome,created_at FROM article_feedback ORDER BY created_at DESC").fetchall()
    latest_feedback = {}
    for item in feedback:
        latest_feedback.setdefault(item["article_id"], item["outcome"])
    # A QC decision removes an article from the active/default queue
    # immediately. This never touches the live DB row -- it's a read-side
    # filter against the separate QC archive's ledger, so it's always
    # consistent with what actually got archived (no partial-state window).
    decided_ids = archive.decided_article_ids() if archive is not None else set()
    result = []
    for row in rows:
        if row["id"] in decided_ids:
            continue
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
:root{--bg:#08111d;--nav:#0c1727;--card:#111f31;--line:#26374d;--text:#e9eef7;--muted:#9baac0;--blue:#74b7ff;--green:#65df91;--amber:#f2bd4f;--red:#ff7770}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.45 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic","Segoe UI",sans-serif}a{color:#80bfff;text-decoration:none}.app{min-height:100vh;display:grid;grid-template-columns:210px 1fr;grid-template-rows:68px 1fr}header{grid-column:1/3;display:flex;align-items:center;gap:14px;padding:0 20px;background:#0b1524;border-bottom:1px solid var(--line)}.brand{font-size:17px;font-weight:760}.brand small,.muted,small{display:block;color:var(--muted);font-size:11px;font-weight:400}.pill,.badge{display:inline-block;border-radius:5px;font-size:10px;font-weight:800;letter-spacing:.04em;padding:4px 7px}.pill{color:#d5c2ff;background:#25235c;border:1px solid #4842a2}.provenance{color:var(--muted);max-width:460px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.spacer{flex:1}button{border:1px solid #3d4c66;background:#1a2b42;color:#eaf2ff;border-radius:5px;padding:7px 10px;font-weight:700;cursor:pointer}aside{background:var(--nav);border-right:1px solid var(--line);padding:12px}.navtitle{font-size:10px;color:var(--muted);letter-spacing:.08em;margin:15px 8px 5px}.nav{display:block;color:#d6dfed;padding:8px 10px;border-radius:5px;margin:2px 0}.nav.active{background:#302d80;color:#fff;font-weight:700}main{width:100%;max-width:1650px;margin:auto;padding:16px 20px}.summary{display:grid;grid-template-columns:1.35fr repeat(5,1fr);gap:10px}.metric,.card{background:var(--card);border:1px solid var(--line);border-radius:8px}.metric{min-height:87px;padding:12px}.label{font-size:10px;color:var(--muted);font-weight:800;letter-spacing:.06em}.number{font-size:25px;font-weight:780;margin:3px 0}.overall{border-color:#315173}.overall .number{color:var(--blue)}.grid{display:grid;grid-template-columns:minmax(0,3fr) minmax(260px,1fr);gap:13px;margin-top:13px}.card{padding:13px}h2{font-size:15px;margin:0 0 10px}.sub{color:var(--muted);font-size:12px;margin:-5px 0 10px}.lead{padding:11px 0;border-bottom:1px solid #22324a}.lead:last-child{border:0}.headline{display:block;color:#f3f7fe;font-size:15px;font-weight:710;line-height:1.35;margin:4px 0 5px}.lead-meta{display:flex;gap:7px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:11px}.snippet{color:#bbc8da;font-size:12px;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.badge.production{background:#133f2c;color:var(--green)}.badge.experimental{background:#433514;color:var(--amber)}.badge.healthy,.badge.useful{background:#133f2c;color:var(--green)}.badge.failed,.badge.not-useful,.badge.off-topic{background:#4b252b;color:#ff9a93}.badge.needs-review,.badge.duplicate{background:#453713;color:var(--amber)}.badge.unknown{background:#29364a;color:#cbd6e6}.badge.stale{background:#453713;color:var(--amber)}.badge.blocked{background:#4b252b;color:#ff9a93}.filters{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.filters select{color:var(--text);background:#0d1a2b;border:1px solid #34465e;border-radius:5px;padding:7px}.source-health{margin-top:13px}.two{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin-top:13px}table{width:100%;border-collapse:collapse;font-size:12px}th{text-align:left;color:var(--muted);font-size:10px;letter-spacing:.05em;padding:7px;border-bottom:1px solid var(--line)}td{padding:8px 7px;border-bottom:1px solid #213047;vertical-align:top}.empty{min-height:110px;display:flex;align-items:center;justify-content:center;flex-direction:column;text-align:center;color:var(--muted)}.empty b{color:#e2eaf5}.detail-title{font-size:22px;line-height:1.36;margin:4px 0 10px}.evidence{white-space:pre-wrap;color:#cad5e5;line-height:1.55;background:#0d1a2b;border:1px solid #26374d;border-radius:6px;padding:12px}.feedback{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.feedback button{font-size:11px}.footer{color:var(--muted);font-size:11px;text-align:center;margin:16px}@media(max-width:1000px){.app{grid-template-columns:1fr;grid-template-rows:68px auto 1fr}header{grid-column:1}.provenance{max-width:170px}aside{display:flex;overflow:auto;border-right:0;border-bottom:1px solid var(--line);padding:7px}.navtitle{display:none}.nav{white-space:nowrap}.summary,.grid,.two{grid-template-columns:1fr}}</style>"""


def _collection_panel(state: dict[str, object], sources: dict[str, object], empty: bool = False) -> str:
    message = "No local leads yet." if empty else "Collection disabled"
    return f'''<div class="{'empty ' if empty else ''}collect"><b>{message}</b><span>This Phase 0 dashboard is read-only. No authenticated mutation profile exists; use the approved CLI workflow.</span></div>'''


def token_authorizer(headers) -> bool:
    """Bearer-token mutation_authorizer for serve(). The Windows native launcher
    generates a fresh per-process KOREAN_TECH_WIRE_DASHBOARD_AUTH_TOKEN and wires
    this in; nothing else does, so the dashboard stays read-only (POST /collect
    403s) everywhere else -- e.g. the macOS launcher, which passes no authorizer."""
    token = os.environ.get("KOREAN_TECH_WIRE_DASHBOARD_AUTH_TOKEN", "")
    if not token:
        return False
    supplied = headers.get("Authorization", "") or ""
    return secrets.compare_digest(supplied, f"Bearer {token}")


def _collection_status_card(state: dict[str, object], can_collect: bool) -> str:
    if not can_collect:
        return f'{_collection_panel(state, {})}<p class=muted>Manual collection is disabled in the Phase 0 dashboard. Use the approved CLI workflow.</p>'
    running = bool(state.get("running"))
    summary = state.get("summary") or {}
    detail = ""
    if not running and summary:
        detail = f'<div class="run-status">Last run: discovered {e(summary.get("discovered", "—"))}, new {e(summary.get("new", "—"))}, failed {e(summary.get("failed", "—"))}.</div>'
    error = state.get("error")
    if error and not running:
        detail += f'<div class="run-status" style="color:var(--red)">Error: {e(error)}</div>'
    status_label = e(state.get("status", "IDLE")) if running else ""
    return f'''<div class=collect><b>Run all collectors</b><span>Runs the same local collector core the CLI uses, against every PRODUCTION source, and writes straight into this local database. Launching the dashboard never starts this on its own -- EXPERIMENTAL sources are never included here; use an individual collector control in Source Health to run one on purpose.</span><div style="margin-top:10px;display:flex;align-items:center;gap:8px"><button type=button class=run-btn id=run-now-btn data-source="" {"disabled" if running else ""}>&#9654; Run all collectors</button><span id=run-now-status class=muted>{status_label}</span></div><div id=run-now-detail>{detail}</div></div>'''


def _collection_script(can_collect: bool, token: str) -> str:
    if not can_collect:
        return ""
    return f'''<script>
(function(){{
  var token = {json.dumps(token)};
  var statusEl = document.getElementById('run-now-status');
  var detailEl = document.getElementById('run-now-detail');
  function poll(){{
    fetch('/collection-status', {{cache: 'no-store'}}).then(function(r){{ return r.json(); }}).then(function(state){{
      document.querySelectorAll('.run-btn').forEach(function(b){{ b.disabled = !!state.running; }});
      if (state.running) {{
        if (statusEl) statusEl.textContent = state.status + (state.current_source ? (' — ' + state.current_source) : '');
        setTimeout(poll, 1000);
      }} else {{
        if (statusEl) statusEl.textContent = '';
        if (state.status === 'COMPLETED' || state.status === 'COMPLETED_WITH_ERRORS') {{
          location.reload();
        }} else if (state.error && detailEl) {{
          detailEl.textContent = 'Error: ' + state.error;
        }}
      }}
    }});
  }}
  document.querySelectorAll('.run-btn').forEach(function(btn){{
    btn.addEventListener('click', function(){{
      document.querySelectorAll('.run-btn').forEach(function(b){{ b.disabled = true; }});
      if (statusEl) statusEl.textContent = 'Starting…';
      fetch('/collect', {{
        method: 'POST',
        headers: {{'Authorization': 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'source=' + encodeURIComponent(btn.getAttribute('data-source') || '')
      }}).then(function(r){{
        if (r.status === 202) {{ setTimeout(poll, 800); }}
        else {{ document.querySelectorAll('.run-btn').forEach(function(b){{ b.disabled = false; }}); if (statusEl) statusEl.textContent = 'Failed to start (HTTP ' + r.status + ')'; }}
      }});
    }});
  }});
  document.querySelectorAll('.qc-btn').forEach(function(btn){{
    btn.addEventListener('click', function(){{
      document.querySelectorAll('.qc-btn').forEach(function(b){{ b.disabled = true; }});
      fetch('/qc', {{
        method: 'POST',
        headers: {{'Authorization': 'Bearer ' + token, 'Content-Type': 'application/x-www-form-urlencoded'}},
        body: 'article_id=' + encodeURIComponent(btn.getAttribute('data-article')) + '&decision=' + encodeURIComponent(btn.getAttribute('data-decision'))
      }}).then(function(r){{
        if (r.ok) {{ location.href = '/'; }}
        else {{ document.querySelectorAll('.qc-btn').forEach(function(b){{ b.disabled = false; }}); alert('QC decision failed (HTTP ' + r.status + ')'); }}
      }});
    }});
  }});
}})();
</script>'''


def render_overview(database: Database, sources: dict[str, object], query: dict[str, list[str]], collection: dict[str, object] | None = None, can_collect: bool = False, archive: QCArchive | None = None, show_experimental: bool = False) -> str:
    state = collection or {"status": "IDLE", "running": False, "sources": {}}
    channel, source_filter = query.get("channel", [""])[0].upper(), query.get("source", [""])[0]
    articles = _article_rows(database, sources, channel, source_filter, archive=archive)
    health_map, feedback = {item["source_id"]: item for item in database.health_summary(sources)}, database.feedback_history()
    lead_rows = []
    for article in articles[:40]:
        excerpt = (article["body_original"] or "").replace("\n", " ").strip()
        qc_buttons = ""
        if can_collect:
            qc_buttons = "".join(f'<button type=button class=qc-btn data-article="{article["id"]}" data-decision="{d}">{e(d.replace("_", " ").title())}</button>' for d in QC_DECISIONS)
            qc_buttons = f'<div class="lead-meta qc-actions">{qc_buttons}</div>'
        lead_rows.append(f'''<article class=lead><div class=lead-meta>{badge(article["channel"])} <b>{e(article["source_name"])}</b> <span>{e(article["published_at"] or article["discovered_at"])}</span> {badge(article["feedback"]) if article["feedback"] else ""}</div><a class=headline href="/articles/{article["id"]}">{e(article["title_original"])}</a><div class=lead-meta>{e(article["category"] or "Uncategorised")} · {external(article["canonical_url"])}</div>{f"<div class=snippet>{e(excerpt)}</div>" if excerpt else ""}{qc_buttons}</article>''')
    health_rows, review_rows = [], []
    for source_id, source in sources.items():
        item = health_map.get(source_id, {}); status = health_state(item)
        link = f'/?source={quote(source_id)}'
        # Individual per-collector run control. EXPERIMENTAL sources only get
        # one when show_experimental_sources is on (config-gated re-enable);
        # PRODUCTION sources always get one when mutation is authorized.
        # "Run all collectors" above never includes EXPERIMENTAL sources --
        # this is the only path that can trigger one, and it's deliberate.
        if can_collect and (source.status == "PRODUCTION" or show_experimental):
            run_control = f'<button type=button class=run-btn data-source="{e(source_id)}">&#9654; Run</button>'
        elif source.status == "EXPERIMENTAL":
            run_control = '<span class=muted>hidden (enable in config)</span>'
        else:
            run_control = ""
        health_rows.append((f'<a class=clickable href="{link}#health">{e(source.name)}<small>{e(source_id)}</small></a>', badge(source.status), badge(status), e(item.get("last_success") or "—"), e(item.get("latest_accepted") if item.get("latest_accepted") is not None else "—"), e("; ".join(item.get("recent_notes", [])[:1]) or "—"), run_control))
        sf = [row for row in feedback if row["source_id"] == source_id]
        review_rows.append((f'<a class=clickable href="{link}#latest">{e(source.name)}</a>', badge(source.status), e(item.get("last_success") or "—"), e(len([a for a in articles if a["source_id"] == source_id])), e(sum(r["outcome"] == "USEFUL" for r in sf)), e(sum(r["outcome"] in {"NOT_USEFUL", "OFF_TOPIC", "DUPLICATE"} for r in sf))))
    with database.connect() as con: runs = con.execute("SELECT source_id,started_at,status,summary_json FROM runs ORDER BY id DESC LIMIT 20").fetchall()
    run_rows = [(e(sources.get(r["source_id"]).name if r["source_id"] in sources else r["source_id"] or "all"), e(r["started_at"]), badge((r["status"] or "UNKNOWN").upper()), e(json.loads(r["summary_json"] or "{}").get("discovered", "—")), e(json.loads(r["summary_json"] or "{}").get("new", "—"))) for r in runs]
    qc_rows = []
    if archive is not None:
        for item in archive.recent(20):
            qc_rows.append((e(item["title_original"]), e(sources.get(item["source_id"]).name if item["source_id"] in sources else item["source_id"]), badge(item["decision"]), e(item["decided_at"])))
    options = "".join(f'<option value="{e(k)}" {"selected" if source_filter == k else ""}>{e(v.name)}</option>' for k, v in sources.items())
    leads = "".join(lead_rows) if lead_rows else _collection_panel(state, sources, empty=True)
    style = _style().replace("</style>", ".collect{border:1px solid #514ba8;border-radius:7px;padding:12px;background:#151c3d}.collect form{margin-top:10px}.collect button{background:#554bc4}.collect button:disabled{opacity:.55}.run-status{margin-top:8px}.clickable{display:block;color:#f2f6fc;font-weight:700}.headline:hover,.clickable:hover{text-decoration:underline}.lead:hover{background:#13243a}.qc-actions{margin-top:8px}.qc-actions button{font-size:11px;margin-right:6px;padding:5px 8px}</style>")
    return f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Korean Tech Wire</title>{style}</head><body><div class=app><header><div class=brand>◈ Korean Tech Wire<small>Korean technology newsroom intelligence</small></div><span class=pill>LOCAL FIELD TEST</span><span class=provenance title="{e(database.path.resolve())}">Revision: {e(revision())} · Local database only · No external delivery</span><span class=spacer></span><button onclick="location.reload()">↻ Refresh</button></header><aside><a class="nav active" href=/>▤ Overview</a><div class=navtitle>NEWSROOM</div><a class=nav href=#latest>◉ Latest Leads</a><div class=navtitle>SOURCES</div><a class=nav href="/?channel=PRODUCTION">● Production</a><a class=nav href="/?channel=EXPERIMENTAL">◌ Experimental</a><a class=nav href=#health>♜ Source Health</a><div class=navtitle>REVIEW</div><a class=nav href=#review>✓ Source Review</a><a class=nav href=#feedback>✦ Feedback</a><a class=nav href=#qc>◈ Recently QCed</a><div class=navtitle>SYSTEM</div><a class=nav href=#runs>◷ Run History</a></aside><main><section class=summary><div class="metric overall"><div class=label>OVERALL HEALTH</div><div class=number>LOCAL READY</div><small>Isolated field-test state</small></div><div class=metric><div class=label>RECENT LEADS</div><div class=number>{len(articles)}</div></div><div class=metric><div class=label>PRODUCTION</div><div class=number>{sum(s.status == "PRODUCTION" for s in sources.values())}</div></div><div class=metric><div class=label>EXPERIMENTAL</div><div class=number>{sum(s.status == "EXPERIMENTAL" for s in sources.values())}</div></div><div class=metric><div class=label>NEEDS REVIEW</div><div class=number>{sum(a["feedback"] == "NEEDS_REVIEW" for a in articles)}</div></div><div class=metric><div class=label>LATEST RUN</div><div class=number>{e(runs[0]["status"] if runs else "—")}</div></div></section><section class=grid id=latest><div class=card><h2>Latest Leads</h2><p class=sub>Click a headline for original evidence, article link and feedback.</p><form class=filters method=get><select name=channel><option value="">All channels</option><option value=PRODUCTION>Production</option><option value=EXPERIMENTAL>Experimental</option></select><select name=source><option value="">All sources</option>{options}</select><button>Filter</button><a href=/>Clear</a></form>{leads}</div><div class="card collect"><h2>COLLECTION STATUS</h2>{_collection_status_card(state, can_collect)}</div></section><section class="card source-health" id=health><h2>Source Health</h2>{table(("Source","Channel","Health","Latest success","Accepted","Warning / evidence","Run"),health_rows,"No source runs recorded","Collection remains disabled in this dashboard.")}</section><section class=two><section class=card id=review><h2>Source Review</h2>{table(("Source","Channel","Latest success","Visible leads","Useful","Negative"),review_rows,"No source review data","Feedback accumulates locally.")}</section><section class=card id=runs><h2>Run History</h2>{table(("Source","Started","Status","Discovered","New"),run_rows,"No runs recorded yet","Run history appears after collection.")}</section></section><section class="card source-health" id=feedback><h2>Recent Editorial Feedback</h2>{table(("Article","Source","Outcome","When"),[(f'<a href="/articles/{r["article_id"]}">{e(r["title_original"])}</a>',e(sources.get(r["source_id"]).name if r["source_id"] in sources else r["source_id"]),badge(r["outcome"]),e(r["created_at"])) for r in feedback[:20]],"No feedback yet","Open a lead to review it.")}</section><section class="card source-health" id=qc><h2>Recently QCed</h2><p class=sub>Every QC decision archives the full item + provenance into a separate on-disk ledger and removes it from the active queue immediately.</p>{table(("Article","Source","Decision","Decided"),qc_rows,"No QC decisions yet","Decide Useful / Not useful / False positive / Duplicate on a lead to archive it here.")}</section><div class=footer>LOCAL FIELD TEST · Local database only · No external delivery</div></main></div>{_collection_script(can_collect, os.environ.get("KOREAN_TECH_WIRE_DASHBOARD_AUTH_TOKEN", ""))}</body></html>'''


def render_detail(database: Database, sources: dict[str, object], article_id: int, can_collect: bool = False, archive: QCArchive | None = None) -> tuple[int, str]:
    with database.connect() as con:
        row = con.execute("SELECT * FROM articles WHERE id=? AND record_status='valid'", (article_id,)).fetchone()
    if not row:
        return 404, "<h1>Lead not found</h1>"
    article = dict(row)
    source = sources.get(article["source_id"])
    feedback = database.feedback_history(article_id)
    history = table(("Outcome", "Note", "Recorded"), [(badge(item["outcome"]), e(item["note"] or "—"), e(item["created_at"])) for item in feedback], "No feedback yet", "Use an explicit owner outcome below.")
    buttons = "<span class=muted>Feedback mutation is disabled during Phase 0.</span>"
    existing_decision = archive.decision_for(article_id) if archive is not None else None
    if existing_decision is not None:
        qc_section = f'<p class=muted>QC decision recorded: {badge(existing_decision["decision"])} at {e(existing_decision["decided_at"])}. Archived into the separate QC ledger; this lead is no longer in the active queue.</p>'
    elif can_collect:
        qc_buttons = "".join(f'<button type=button class=qc-btn data-article="{article_id}" data-decision="{d}">{e(d.replace("_", " ").title())}</button>' for d in QC_DECISIONS)
        qc_section = f'<div class="feedback qc-actions">{qc_buttons}</div>'
    else:
        qc_section = "<span class=muted>QC decisions are disabled: no authenticated mutation profile for this session.</span>"
    return 200, f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{e(article["title_original"])} · Korean Tech Wire</title>{_style()}</head><body><div class=app><header><div class=brand>◈ Korean Tech Wire<small>Lead evidence</small></div><span class=pill>FIELD TEST</span><span class=provenance>Revision: {e(revision())}　|　Local DB: {e(database.path.name)}</span><span class=spacer></span><a href="/">← Newsroom</a></header><aside><a class="nav active" href="/">▤　Overview</a><div class=navtitle>LEAD</div><a class=nav href="#evidence">▤　Evidence</a><a class=nav href="#feedback">✓　Feedback</a><a class=nav href="#qc">◈　QC decision</a></aside><main><section class=card><div class=lead-meta>{badge(source.status if source else "UNKNOWN")} <b>{e(source.name if source else article["source_id"])}</b> <span>Published: {e(article["published_at"] or "—")}</span><span>Observed: {e(article["discovered_at"])}</span></div><h1 class=detail-title>{e(article["title_original"])}</h1><p class=muted>Category: {e(article["category"] or "—")}　·　Canonical identity: {e(article["source_id"])} / {e(article["canonical_url"])}</p>{external(article["canonical_url"])}</section><section class="card source-health" id=evidence><h2>Original Korean evidence</h2><p class=sub>Stored original-language content; no automatic transliteration or machine translation.</p><div class=evidence>{e(article["body_original"] or article["title_original"])}</div></section><section class="card source-health" id=qc><h2>QC decision</h2><p class=sub>Useful / Not useful / False positive / Duplicate. Archives the full item + provenance into the separate QC ledger and removes it from the active queue immediately; a repeated decision is refused (409), never duplicated.</p>{qc_section}</section><section class="card source-health" id=feedback><h2>Editorial Feedback</h2><p class=sub>Records structured review history without mutating the article or source channel.</p><form method=post action=/feedback><input type=hidden name=article_id value="{article_id}"><div class=feedback>{buttons}</div></form><div class=source-health>{history}</div></section></main></div>{_collection_script(can_collect, os.environ.get("KOREAN_TECH_WIRE_DASHBOARD_AUTH_TOKEN", ""))}</body></html>'''


def require_loopback_host(host: str) -> None:
    try:
        loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    if not loopback:
        raise ValueError("Korean Tech Wire has no authenticated remote profile; host must be loopback")


def serve(host: str = "127.0.0.1", port: int = 0, mutation_authorizer=None) -> ThreadingHTTPServer:
    require_loopback_host(host)
    database, sources, archive = _database()
    show_experimental = load_settings(CONFIG).show_experimental_sources
    collection = CollectionController(database, sources)
    class Handler(BaseHTTPRequestHandler):
        def _html(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                body = json.dumps({"application": "KoreanTechWire", "status": "ok", "database": str(database.path.resolve()), "qc_archive": str(archive.path.resolve()), "revision": revision()}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if parsed.path == "/collection-status":
                body = json.dumps(collection.snapshot(), ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if parsed.path == "/": self._html(200, render_overview(database, sources, parse_qs(parsed.query), collection.snapshot(), can_collect=mutation_authorizer is not None, archive=archive, show_experimental=show_experimental)); return
            if parsed.path.startswith("/articles/"):
                try: article_id = int(parsed.path.rsplit("/", 1)[1])
                except ValueError: self.send_error(404); return
                status, body = render_detail(database, sources, article_id, can_collect=mutation_authorizer is not None, archive=archive); self._html(status, body); return
            self.send_error(404)
        def do_POST(self) -> None:
            if mutation_authorizer is None or not mutation_authorizer(self.headers):
                self.send_error(403, "authenticated profile required; dashboard is read-only"); return
            if self.path == "/collect":
                length = int(self.headers.get("Content-Length", "0")); form = parse_qs(self.rfile.read(length).decode("utf-8")); source_id = form.get("source", [""])[0] or None
                if source_id and source_id not in sources:
                    self.send_error(400, "unknown source"); return
                started = collection.start(source_id)
                body = json.dumps(collection.snapshot(), ensure_ascii=False).encode("utf-8")
                self.send_response(202 if started else 409); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if self.path == "/qc":
                try:
                    length = int(self.headers.get("Content-Length", "0")); form = parse_qs(self.rfile.read(length).decode("utf-8"))
                    article_id = int(form.get("article_id", [""])[0]); decision = form.get("decision", [""])[0]
                    if decision not in QC_DECISIONS: raise ValueError("invalid QC decision")
                except (ValueError, UnicodeDecodeError): self.send_error(400); return
                with database.connect() as con:
                    row = con.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
                if row is None: self.send_error(404, "article not found"); return
                try:
                    archive.decide(row, decision)
                except AlreadyDecided:
                    self.send_error(409, "article already has a QC decision"); return
                body = json.dumps({"article_id": article_id, "decision": decision}, ensure_ascii=False).encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
            if self.path != "/feedback": self.send_error(404); return
            try:
                length = int(self.headers.get("Content-Length", "0")); form = parse_qs(self.rfile.read(length).decode("utf-8")); article_id = int(form.get("article_id", [""])[0]); outcome = form.get("outcome", [""])[0]
                if outcome not in OUTCOMES: raise ValueError("invalid outcome")
                database.add_feedback(article_id, outcome)
            except (ValueError, UnicodeDecodeError): self.send_error(400); return
            self.send_response(303); self.send_header("Location", f"/articles/{article_id}"); self.end_headers()
        def log_message(self, *_: object) -> None: pass
    return ThreadingHTTPServer((host, port), Handler)
