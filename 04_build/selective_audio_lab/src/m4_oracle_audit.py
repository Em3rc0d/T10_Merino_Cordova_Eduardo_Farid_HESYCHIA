"""Auditoría de criterios acústicos para resultados M4 con máscara Oracle.

Lee real_mixture_runs.csv generado por real_mixture_oracle_batch.py.
No entrena un modelo, ni convierte una línea base oracle en evidencia aprendida.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

REQUIRED = {"mix_id", "cap_db", "A_target_db", "A_protected_db"}


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rows(csv_path: Path) -> tuple[list[dict], list[float]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            missing = REQUIRED - set(reader.fieldnames or [])
            raise ValueError(f"Faltan columnas contractuales: {sorted(missing)}")
        rows = []
        seen = set()
        cap_sets = defaultdict(set)
        for line, raw in enumerate(reader, start=2):
            try:
                mix_id = int(raw["mix_id"])
                cap = float(raw["cap_db"])
                target = float(raw["A_target_db"])
                protected = float(raw["A_protected_db"])
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError(f"Fila {line}: dato inválido") from exc
            if mix_id < 0 or not all(map(math.isfinite, (cap, target, protected))):
                raise ValueError(f"Fila {line}: valor negativo de ID o no finito")
            if cap < 0:
                raise ValueError(f"Fila {line}: cap negativo")
            key = (mix_id, cap)
            if key in seen:
                raise ValueError(f"Duplicado mix_id/cap_db: {key}")
            seen.add(key)
            cap_sets[cap].add(mix_id)
            rows.append({
                "mix_id": mix_id,
                "cap_db": cap,
                "A_target_db": target,
                "A_protected_db": protected,
            })
    if not rows:
        raise ValueError("CSV sin mediciones")
    caps = sorted(cap_sets)
    if any(cap_sets[cap] != cap_sets[caps[0]] for cap in caps[1:]):
        raise ValueError("Sweep incompleto: cada cap debe evaluar las mismas mezclas")
    return rows, caps


def audit(
    csv_path: str | Path,
    out_dir: str | Path,
    *,
    min_target_db: float = 6.0,
    max_protected_db: float = 1.0,
    primary_cap_db: float = 12.0,
    min_mixtures: int = 100,
) -> dict:
    src = Path(csv_path)
    if not all(math.isfinite(x) for x in (
        min_target_db, max_protected_db, primary_cap_db
    )):
        raise ValueError("Los umbrales deben ser finitos")
    if min_mixtures < 1:
        raise ValueError("min_mixtures debe ser positivo")
    rows, caps = load_rows(src)
    if primary_cap_db not in caps:
        raise ValueError(f"No existe cap primario {primary_cap_db} en {caps}")
    n_mixtures = len({row["mix_id"] for row in rows})
    if n_mixtures < min_mixtures:
        raise ValueError(
            f"Solo hay {n_mixtures} mezclas; protocolo exige al menos {min_mixtures}"
        )

    evaluated = []
    grouped = defaultdict(list)
    for row in rows:
        target_ok = row["A_target_db"] >= min_target_db
        protected_ok = row["A_protected_db"] <= max_protected_db
        item = {
            **row,
            "target_ok": target_ok,
            "protected_ok": protected_ok,
            "both_ok": target_ok and protected_ok,
        }
        evaluated.append(item)
        grouped[row["cap_db"]].append(item)

    per_cap = []
    for cap in caps:
        subset = grouped[cap]
        def count(key: str) -> int:
            return sum(bool(r[key]) for r in subset)
        target_vals = [r["A_target_db"] for r in subset]
        protected_vals = [r["A_protected_db"] for r in subset]
        both = count("both_ok")
        per_cap.append({
            "cap_db": cap,
            "mixtures": len(subset),
            "target_pass": count("target_ok"),
            "protected_pass": count("protected_ok"),
            "joint_pass": both,
            "joint_fail": len(subset) - both,
            "joint_pass_fraction_descriptive": both / len(subset),
            "A_target_mean_db": mean(target_vals),
            "A_target_median_db": median(target_vals),
            "A_protected_mean_db": mean(protected_vals),
            "A_protected_median_db": median(protected_vals),
            "A_protected_max_db": max(protected_vals),
        })

    primary = next(r for r in per_cap if r["cap_db"] == primary_cap_db)
    summary = {
        "evidence_type": "offline_oracle_known_stems_not_learned_M4",
        "source_csv": src.name,
        "source_sha256": file_sha256(src),
        "thresholds_preexisting_not_reestimated": {
            "A_target_min_db": min_target_db,
            "A_protected_max_db": max_protected_db,
        },
        "n_distinct_mixtures": n_mixtures,
        "n_rows": len(rows),
        "caps_db": caps,
        "primary_cap_db": primary_cap_db,
        "primary_gate": (
            "MET_FOR_ALL_MIXTURES" if primary["joint_fail"] == 0
            else "NOT_MET_FOR_ALL_MIXTURES"
        ),
        "primary_result": primary,
        "by_cap": per_cap,
        "interpretation": (
            "Los conteos son descriptivos del lote; no son eficacia clínica "
            "ni garantías de uso en vivo. El ensayo Oracle utiliza stems "
            "privilegiados, no una red neuronal entrenada. Ningún valor "
            "de este reporte debe atribuirse a M4 aprendido."
        ),
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "m4_oracle_per_mix_audit.csv").open(
        "w", newline="", encoding="utf-8"
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(evaluated[0]))
        writer.writeheader()
        writer.writerows(sorted(evaluated, key=lambda r: (r["cap_db"], r["mix_id"])))
    (out / "m4_oracle_audit_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="real_mixture_runs.csv")
    parser.add_argument("--out", required=True)
    parser.add_argument("--min-target-db", type=float, default=6.0)
    parser.add_argument("--max-protected-db", type=float, default=1.0)
    parser.add_argument("--primary-cap-db", type=float, default=12.0)
    parser.add_argument("--min-mixtures", type=int, default=100)
    args = parser.parse_args()
    result = audit(
        args.input, args.out,
        min_target_db=args.min_target_db,
        max_protected_db=args.max_protected_db,
        primary_cap_db=args.primary_cap_db,
        min_mixtures=args.min_mixtures,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
