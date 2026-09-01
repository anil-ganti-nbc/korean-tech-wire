"""Target-local qualification provenance and epoch projection.

The projection is deliberately separate from KTW's aggregate source-health
history: content identity is not qualification material identity, and a run's
trigger provenance must be established by the execution boundary rather than
invented by a downstream writer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class QualificationProvenance(str, Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    TEST = "TEST"
    UNKNOWN = "UNKNOWN"


def normalize_provenance(value: QualificationProvenance | str | None) -> str:
    if isinstance(value, QualificationProvenance):
        return value.value
    try:
        return QualificationProvenance(str(value or "UNKNOWN").upper()).value
    except ValueError:
        return QualificationProvenance.UNKNOWN.value


def material_identity(inputs: dict[str, Any]) -> str:
    """Hash stable qualification inputs, never runtime timestamps or run IDs."""
    payload = {str(key): inputs[key] for key in sorted(inputs)}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class QualificationContext:
    run_id: int
    source_id: str
    scope_key: str
    epoch_id: int
    material_identity: str
    provenance: str
    gate_status: str


def _gate(con, scope_key: str, epoch_id: int, material: str, provenance: str) -> dict[str, Any]:
    if provenance == QualificationProvenance.UNKNOWN.value:
        return {"eligible": False, "status": "UNKNOWN", "reason": "missing or untrusted provenance"}
    row = con.execute(
        "SELECT 1 FROM qualification_terminals WHERE scope_key=? AND epoch_id=? "
        "AND material_identity=? AND status='success' AND counts_for_qualification=1 LIMIT 1",
        (scope_key, epoch_id, material),
    ).fetchone()
    if row is None:
        return {"eligible": False, "status": "NOT_QUALIFIED", "reason": "no qualifying terminal evidence in current epoch"}
    return {"eligible": True, "status": "QUALIFIED", "reason": "current epoch has qualifying terminal evidence"}


def prepare(database, *, run_id: int, source_id: str, scope_key: str, material: str,
            provenance: QualificationProvenance | str | None,
            reset_reason: str = "material identity changed") -> QualificationContext:
    """Prepare a source scope before any qualification evidence is gated."""
    if not source_id:
        raise ValueError("qualification source_id is required")
    if not scope_key:
        raise ValueError("qualification scope_key is required")
    provenance_value = normalize_provenance(provenance)
    with database.connect() as con:
        current = con.execute(
            "SELECT epoch_id, material_identity FROM qualification_scopes WHERE scope_key=?",
            (scope_key,),
        ).fetchone()
        prior = current["material_identity"] if current else None
        if current is None or prior != material:
            next_number = con.execute(
                "SELECT COALESCE(MAX(epoch_number), 0) FROM qualification_epochs WHERE scope_key=?",
                (scope_key,),
            ).fetchone()[0] + 1
            cur = con.execute(
                "INSERT INTO qualification_epochs(scope_key, epoch_number, material_identity, "
                "prior_material_identity, reset_reason, created_at) VALUES (?,?,?,?,?,?)",
                (scope_key, next_number, material, prior,
                 None if current is None else reset_reason, database._iso()),
            )
            epoch_id = cur.lastrowid
            con.execute(
                "INSERT INTO qualification_scopes(scope_key, epoch_id, material_identity, updated_at) "
                "VALUES (?,?,?,?) ON CONFLICT(scope_key) DO UPDATE SET epoch_id=excluded.epoch_id, "
                "material_identity=excluded.material_identity, updated_at=excluded.updated_at",
                (scope_key, epoch_id, material, database._iso()),
            )
            if current is not None:
                con.execute(
                    "INSERT OR IGNORE INTO qualification_resets "
                    "(run_id, source_id, scope_key, epoch_id, prior_material_identity, "
                    "new_material_identity, reason, provenance, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (run_id, source_id, scope_key, epoch_id, prior, material,
                     reset_reason, provenance_value, database._iso()),
                )
        else:
            epoch_id = current["epoch_id"]
        gate = _gate(con, scope_key, epoch_id, material, provenance_value)
        con.execute(
            "UPDATE runs SET provenance=?, qualification_scope=?, qualification_epoch_id=?, "
            "qualification_material_identity=?, qualification_gate_status=? WHERE id=?",
            (provenance_value, scope_key, epoch_id, material, gate["status"], run_id),
        )
        con.commit()
    return QualificationContext(run_id, source_id, scope_key, epoch_id, material,
                                provenance_value, gate["status"])


def finish(database, context: QualificationContext, status: str) -> None:
    """Persist terminal evidence independently and idempotently."""
    counts = int(status == "success" and context.provenance == QualificationProvenance.SCHEDULED.value)
    with database.connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO qualification_terminals "
            "(run_id, source_id, scope_key, epoch_id, material_identity, provenance, "
            "status, counts_for_qualification, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (context.run_id, context.source_id, context.scope_key, context.epoch_id,
             context.material_identity, context.provenance, status, counts, database._iso()),
        )
        con.commit()


def gate(database, scope_key: str, *, material: str | None = None) -> dict[str, Any]:
    with database.connect() as con:
        row = con.execute(
            "SELECT epoch_id, material_identity FROM qualification_scopes WHERE scope_key=?",
            (scope_key,),
        ).fetchone()
        if row is None:
            return {"eligible": False, "status": "UNKNOWN", "reason": "scope has no qualification epoch"}
        if material is not None and row["material_identity"] != material:
            return {"eligible": False, "status": "STALE", "reason": "material identity diverges from current epoch"}
        found = con.execute(
            "SELECT 1 FROM qualification_terminals WHERE scope_key=? AND epoch_id=? "
            "AND status='success' AND counts_for_qualification=1 LIMIT 1",
            (scope_key, row["epoch_id"]),
        ).fetchone()
        return ({"eligible": True, "status": "QUALIFIED", "reason": "current epoch has qualifying terminal evidence"}
                if found else {"eligible": False, "status": "NOT_QUALIFIED", "reason": "no qualifying terminal evidence in current epoch"})


def reset_rows(database, scope_key: str) -> list:
    with database.connect() as con:
        return con.execute(
            "SELECT * FROM qualification_resets WHERE scope_key=? ORDER BY id", (scope_key,)
        ).fetchall()


def terminal_rows(database, scope_key: str) -> list:
    with database.connect() as con:
        return con.execute(
            "SELECT * FROM qualification_terminals WHERE scope_key=? ORDER BY id", (scope_key,)
        ).fetchall()


def event_rows(database, scope_key: str) -> list:
    """Return reset and terminal facts in one chronological audit view."""
    with database.connect() as con:
        resets = [dict(row) | {"event_type": "RESET"} for row in con.execute(
            "SELECT * FROM qualification_resets WHERE scope_key=?", (scope_key,)
        )]
        terminals = [dict(row) | {"event_type": "TERMINAL"} for row in con.execute(
            "SELECT * FROM qualification_terminals WHERE scope_key=?", (scope_key,)
        )]
    return sorted(resets + terminals, key=lambda row: (row["created_at"], row["id"]))
