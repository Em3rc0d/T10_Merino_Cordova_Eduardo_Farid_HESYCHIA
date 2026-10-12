from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Iterable

def schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "03_architecture" / "schema_v11.sql"

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
        with self.connect() as con:
            con.execute(
                "INSERT OR IGNORE INTO dataset(id,name,version,license) VALUES(?,?,?,?)",
                ("SYNTH-PI8", "Synthetic controlled stems", "1.0", "generated"),
            )
            for role, label in [
                ("protected", "speech_like_synthetic"),
                ("target", metrics["target_label"]),
                ("background", "background_synthetic"),
            ]:
                asset_id = f"SYNTH-PI8-{role.upper()}"
                con.execute(
                    """INSERT OR IGNORE INTO audio_asset
                    (id,dataset_id,path,checksum,role,split,fold,sr,duration_s)
                    VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        asset_id,
                        "SYNTH-PI8",
                        f"generated://{role}",
                        f"generated-{role}-v1",
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
                ("BASELINE-IRM-ORACLE", "mask", "sklearn", "1.0", "oracle-no-model", "frozen"),
            )
            con.execute(
                """INSERT OR IGNORE INTO experiment
                (id,scenario,config_json,created_at)
                VALUES(?,?,?,datetime('now'))""",
                ("EXP-PI8-DEMO", "attenuation", json.dumps(config, sort_keys=True)),
            )
            con.execute(
                """INSERT OR REPLACE INTO run
                (id,experiment_id,model_version_id,device,seed,status,started_at,ended_at)
                VALUES(?,?,?,?,?,'completed',datetime('now'),datetime('now'))""",
                (
                    run_id,
                    "EXP-PI8-DEMO",
                    "BASELINE-IRM-ORACLE",
                    "local_python_reference",
                    seed,
                ),
            )
            for role in ("protected", "target", "background"):
                con.execute(
                    """INSERT OR REPLACE INTO run_asset(run_id,asset_id,role,gain_db)
                    VALUES(?,?,?,?)""",
                    (run_id, f"SYNTH-PI8-{role.upper()}", role, 0.0),
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
                ("acoustic", "SI_SDRi_protected_db", metrics["SI_SDRi_protected_db"], "dB"),
                ("compute", "wall_time_ms", metrics.get("wall_time_ms", 0.0), "ms"),
            ]
            con.executemany(
                "INSERT INTO metric(run_id,family,name,value,unit) VALUES(?,?,?,?,?)",
                [(run_id, *row) for row in metric_rows],
            )

            con.execute("DELETE FROM artifact WHERE run_id=?", (run_id,))
            for item in artifacts:
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

    def summary(self, run_id: str) -> dict:
        with self.connect() as con:
            run = con.execute(
                "SELECT id,status,device,seed FROM run WHERE id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(run_id)
            metrics = {
                name: value
                for name, value in con.execute(
                    "SELECT name,value FROM metric WHERE run_id=?", (run_id,)
                ).fetchall()
            }
            policy = con.execute(
                "SELECT target_label,protected_set,decision,reason FROM policy_decision WHERE run_id=?",
                (run_id,),
            ).fetchone()
            artifact_count = con.execute(
                "SELECT COUNT(*) FROM artifact WHERE run_id=?", (run_id,)
            ).fetchone()[0]
        return {
            "run_id": run[0],
            "status": run[1],
            "device": run[2],
            "seed": run[3],
            "metrics": metrics,
            "policy": {
                "target_label": policy[0],
                "protected_set": json.loads(policy[1]),
                "decision": policy[2],
                "reason": policy[3],
            },
            "artifact_count": artifact_count,
        }
