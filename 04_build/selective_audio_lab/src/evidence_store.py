from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable


def schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "03_architecture" / "schema_v13.sql"


class EvidenceStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        con = sqlite3.connect(self.db_path)
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def initialize(self):
        with self.connect() as con:
            con.executescript(schema_path().read_text(encoding="utf-8"))

    def persist_demo(
        self,
        *,
        run_id: str,
        seed: int,
        metrics: dict,
        artifacts: Iterable[dict],
        policy: dict,
        config: dict,
    ):
        self.initialize()
        artifact_rows = [dict(item) for item in artifacts]
        by_name = {item["artifact"]: item for item in artifact_rows}

        required_inputs = {
            "protected": "protected.wav",
            "target": "target.wav",
            "background": "background.wav",
        }
        missing_inputs = [
            filename for filename in required_inputs.values() if filename not in by_name
        ]
        if missing_inputs:
            raise ValueError(
                "Input audio evidence missing from artifacts: "
                + ", ".join(sorted(missing_inputs))
            )

        input_assets = {}
        for role, filename in required_inputs.items():
            item = by_name[filename]
            checksum = str(item.get("sha256", "")).strip().lower()
            if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
                raise ValueError(f"Invalid SHA-256 for {filename}")
            input_assets[role] = {
                "asset_id": f"SYNTH-PI8-{role.upper()}-{checksum[:16]}",
                "path": str(item["path"]),
                "checksum": checksum,
            }

        experiment_id = f"EXP-{run_id}"
        model = config.get("model")
        executed = config.get("executed_engine", "oracle")
        if model:
            model_row = (model["id"] + "-" + model["sha256"], "mask", model["format"],
                         "experimental-v1", model["sha256"], "candidate")
        elif executed == "bypass":
            model_row = ("POLICY-BYPASS", "mask", "baseline", "1.0", "no-model-bypass", "frozen")
        else:
            model_row = ("BASELINE-IRM-ORACLE", "mask", "baseline", "1.0", "oracle-no-model", "frozen")

        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO dataset(id,name,version,license) VALUES(?,?,?,?)",
                ("SYNTH-PI8", "Synthetic controlled stems", "1.0", "generated"),
            )

            for role, asset in input_assets.items():
                con.execute(
                    """INSERT OR IGNORE INTO audio_asset
                    (id,dataset_id,path,checksum,role,split,fold,sr,duration_s)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        asset["asset_id"],
                        "SYNTH-PI8",
                        asset["path"],
                        asset["checksum"],
                        role,
                        "test",
                        None,
                        int(metrics["sr"]),
                        float(metrics["duration_s"]),
                    ),
                )

            con.execute(
                """INSERT OR IGNORE INTO model_version
                (id,task,format,version,checksum,status)
                VALUES(?,?,?,?,?,?)""",
                model_row,
            )
            con.execute(
                """INSERT INTO experiment
                (id,scenario,config_json,created_at)
                VALUES(?,?,?,datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                  scenario=excluded.scenario,
                  config_json=excluded.config_json""",
                (
                    experiment_id,
                    "attenuation",
                    json.dumps(config, sort_keys=True),
                ),
            )
            con.execute(
                """INSERT INTO run
                (id,experiment_id,model_version_id,device,seed,status,started_at,ended_at)
                VALUES(?,?,?,?,?,'completed',datetime('now'),datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                  experiment_id=excluded.experiment_id,
                  model_version_id=excluded.model_version_id,
                  device=excluded.device,
                  seed=excluded.seed,
                  status='completed',
                  ended_at=datetime('now')""",
                (
                    run_id,
                    experiment_id,
                    model_row[0],
                    "local_python_reference",
                    seed,
                ),
            )

            con.execute("DELETE FROM run_asset WHERE run_id=?", (run_id,))
            for role, asset in input_assets.items():
                con.execute(
                    """INSERT INTO run_asset(run_id,asset_id,role,gain_db)
                    VALUES(?,?,?,?)""",
                    (run_id, asset["asset_id"], role, 0.0),
                )

            con.execute("DELETE FROM policy_decision WHERE run_id=?", (run_id,))
            con.execute(
                """INSERT INTO policy_decision
                (run_id,target_label,protected_set,decision,reason)
                VALUES(?,?,?,?,?)""",
                (
                    run_id,
                    policy["target_label"],
                    json.dumps(policy["protected_set"]),
                    policy["decision"],
                    policy["reason"],
                ),
            )

            con.execute("DELETE FROM metric WHERE run_id=?", (run_id,))
            metric_rows = [
                ("acoustic", "A_target_db", metrics["A_target_db"], "dB"),
                ("acoustic", "A_protected_db", metrics["A_protected_db"], "dB"),
                (
                    "acoustic",
                    "SI_SDRi_protected_db",
                    metrics["SI_SDRi_protected_db"],
                    "dB",
                ),
                ("compute", "wall_time_ms", metrics.get("wall_time_ms", 0.0), "ms"),
            ]
            con.executemany(
                "INSERT INTO metric(run_id,family,name,value,unit) VALUES(?,?,?,?,?)",
                [(run_id, *row) for row in metric_rows],
            )

            con.execute("DELETE FROM artifact WHERE run_id=?", (run_id,))
            for item in artifact_rows:
                con.execute(
                    """INSERT INTO artifact(id,run_id,kind,path,checksum)
                    VALUES(?,?,?,?,?)""",
                    (
                        f"{run_id}:{item['artifact']}",
                        run_id,
                        item.get("kind", "report"),
                        item["path"],
                        item["sha256"],
                    ),
                )

    def audit_snapshot(self, run_id: str) -> dict:
        with self.connect() as con:
            run = con.execute(
                """SELECT id,experiment_id,model_version_id,device,seed,status
                FROM run WHERE id=?""",
                (run_id,),
            ).fetchone()
            if not run:
                raise KeyError(run_id)

            experiment = con.execute(
                "SELECT scenario,config_json FROM experiment WHERE id=?",
                (run[1],),
            ).fetchone()
            model = con.execute(
                """SELECT id,task,format,version,checksum,status
                FROM model_version WHERE id=?""",
                (run[2],),
            ).fetchone()
            policy = con.execute(
                """SELECT target_label,protected_set,decision,reason
                FROM policy_decision WHERE run_id=?""",
                (run_id,),
            ).fetchone()

            metric_rows = con.execute(
                """SELECT family,name,value,unit
                FROM metric WHERE run_id=? ORDER BY family,name""",
                (run_id,),
            ).fetchall()
            artifact_rows = con.execute(
                """SELECT kind,path,checksum
                FROM artifact WHERE run_id=? ORDER BY path""",
                (run_id,),
            ).fetchall()
            asset_rows = con.execute(
                """SELECT ra.role,aa.id,aa.path,aa.checksum,ra.gain_db,aa.sr,aa.duration_s
                FROM run_asset ra
                JOIN audio_asset aa ON aa.id=ra.asset_id
                WHERE ra.run_id=?
                ORDER BY ra.role""",
                (run_id,),
            ).fetchall()

        return {
            "run": {
                "id": run[0],
                "experiment_id": run[1],
                "model_version_id": run[2],
                "device": run[3],
                "seed": run[4],
                "status": run[5],
            },
            "experiment": {
                "scenario": experiment[0],
                "config": json.loads(experiment[1]),
            },
            "model": {
                "id": model[0],
                "task": model[1],
                "format": model[2],
                "version": model[3],
                "checksum": model[4],
                "status": model[5],
            },
            "policy": {
                "target_label": policy[0],
                "protected_set": json.loads(policy[1]),
                "decision": policy[2],
                "reason": policy[3],
            },
            "metrics": {
                name: {
                    "family": family,
                    "value": value,
                    "unit": unit,
                }
                for family, name, value, unit in metric_rows
            },
            "artifacts": [
                {"kind": kind, "path": path, "checksum": checksum}
                for kind, path, checksum in artifact_rows
            ],
            "assets": [
                {
                    "role": role,
                    "asset_id": asset_id,
                    "path": path,
                    "checksum": checksum,
                    "gain_db": gain_db,
                    "sr": sr,
                    "duration_s": duration_s,
                }
                for role, asset_id, path, checksum, gain_db, sr, duration_s in asset_rows
            ],
        }

    def summary(self, run_id: str) -> dict:
        snap = self.audit_snapshot(run_id)
        return {
            "run_id": snap["run"]["id"],
            "status": snap["run"]["status"],
            "device": snap["run"]["device"],
            "seed": snap["run"]["seed"],
            "metrics": {
                name: item["value"] for name, item in snap["metrics"].items()
            },
            "policy": snap["policy"],
            "artifact_count": len(snap["artifacts"]),
            "asset_count": len(snap["assets"]),
        }
