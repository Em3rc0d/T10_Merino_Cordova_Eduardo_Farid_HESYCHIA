#!/usr/bin/env python3
"""Fail-closed readiness gate for HESYCHIA thesis/jury evidence.

This script never manufactures evidence. It only inspects expected artifacts and
returns READY when all mandatory closure artifacts exist and satisfy structural
checks. Paths can be overridden through CLI arguments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_CHECKPOINT_SHA256 = "c0b34027fe1d4165b062f4145ca7173b3d547cedc39846e17298295e99fb1966"
EXPECTED_AUDIT93_SHA256 = "f0266f300f1c3eb12ef6d3a20b49ed61f6b7ea79f739b8d1febc03a1cfa11abb"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--lab", type=Path, default=Path("."))
    p.add_argument("--audit-sample", type=Path)
    p.add_argument("--kappa", type=Path)
    p.add_argument("--corpus-review-report", type=Path)
    p.add_argument("--freeze-report", type=Path)
    p.add_argument("--confirmatory-analysis", type=Path)
    p.add_argument("--cp02-report", type=Path)
    p.add_argument("--acer-benchmark", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args()

    lab = args.lab.resolve()
    blockers = []
    checks = {}

    checkpoint = lab / "models/m4_sci_real_candidate_v1/selected/candidate.pt"
    if not checkpoint.is_file():
        blockers.append("checkpoint real no disponible")
    else:
        digest = sha256(checkpoint)
        checks["checkpoint_sha256"] = digest
        if digest != EXPECTED_CHECKPOINT_SHA256:
            blockers.append("checkpoint SHA-256 no coincide con el candidato seleccionado")

    for rel, label in [
        ("src/dsp_class_template.py", "baseline DSP code"),
        ("configs/dsp_class_template_v1.json", "baseline DSP config"),
        ("experiments/pi13_pi14/scripts/pi14_analysis_v2.py", "analysis v2"),
        ("experiments/pi13_pi14/scripts/pi14_m4_forward_benchmark.py", "OE3 benchmark"),
    ]:
        path = lab / rel
        checks[label] = path.is_file()
        if not path.is_file():
            blockers.append(f"falta {label}")

    if args.audit_sample:
        if not args.audit_sample.is_file():
            blockers.append("muestra audit_93 no encontrada")
        else:
            d = sha256(args.audit_sample)
            checks["audit_93_sha256"] = d
            if d != EXPECTED_AUDIT93_SHA256:
                blockers.append("SHA-256 de audit_93 no coincide con la selección preespecificada")
    else:
        blockers.append("no se indicó --audit-sample")

    if not args.kappa or not args.kappa.is_file():
        blockers.append("reporte Cohen kappa no disponible")
    else:
        k = load_json(args.kappa)
        checks["kappa_report"] = k
        candidate = k.get("kappa", k.get("cohen_kappa"))
        if candidate is None:
            blockers.append("reporte kappa sin valor identificable")
        elif float(candidate) < 0.60:
            blockers.append(f"kappa={candidate} < 0.60; requiere adjudicación/justificación")

    if not args.corpus_review_report or not args.corpus_review_report.is_file():
        blockers.append("reporte final de auditoría/contaminación no disponible")
    else:
        checks["corpus_review_report_sha256"] = sha256(args.corpus_review_report)

    if not args.freeze_report or not args.freeze_report.is_file():
        blockers.append("freeze_preflight.json no disponible")
    else:
        freeze = load_json(args.freeze_report)
        checks["freeze"] = freeze
        if freeze.get("status") not in ("READY_FOR_HUMAN_VERIFICATION", "READY", "PASS"):
            blockers.append(f"freeze no está listo: {freeze.get('status')}")
        if freeze.get("blockers"):
            blockers.append("freeze todavía reporta bloqueadores")

    if not args.confirmatory_analysis or not args.confirmatory_analysis.is_file():
        blockers.append("análisis confirmatorio CNN-DSP-Oracle no disponible")
    else:
        analysis = load_json(args.confirmatory_analysis)
        checks["confirmatory"] = {
            "schema": analysis.get("schema"),
            "scene_count": analysis.get("scene_count"),
            "source_group_count": analysis.get("source_group_count"),
            "speaker_group_count": analysis.get("speaker_group_count"),
            "joint_decision": analysis.get("joint_decision"),
        }
        if analysis.get("source_group_count", 0) < 20:
            blockers.append("campaña confirmatoria tiene <20 source_group")
        if analysis.get("speaker_group_count", 0) < 4:
            blockers.append("campaña confirmatoria tiene <4 speaker_group")
        if analysis.get("paired_mix_sha256_verified") is not True:
            blockers.append("CP10/mix_sha256 pareado no verificado")
        if not analysis.get("joint_decision"):
            blockers.append("H1/H0 no tiene decisión conjunta")

    if not args.cp02_report or not args.cp02_report.is_file():
        blockers.append("reporte CP02 correcta-vs-permutada no disponible")
    else:
        cp02 = load_json(args.cp02_report)
        checks["cp02"] = cp02
        if cp02.get("pass") is not True:
            blockers.append("CP02 no está marcado PASS")

    if not args.acer_benchmark or not args.acer_benchmark.is_file():
        blockers.append("benchmark oficial Acer Nitro 5 no disponible")
    else:
        bench = load_json(args.acer_benchmark)
        checks["acer_benchmark"] = {
            "samples": bench.get("samples"),
            "block_ms": bench.get("block_ms"),
            "model_only_rtf": bench.get("model_only_rtf"),
            "checkpoint_sha256": bench.get("checkpoint_sha256"),
            "platform": bench.get("platform"),
            "cpu_model": bench.get("cpu_model"),
            "physical_memory_bytes": bench.get("physical_memory_bytes"),
        }
        if int(bench.get("samples", 0)) < 1000:
            blockers.append("benchmark Acer tiene <1000 bloques")
        if bench.get("checkpoint_sha256") != EXPECTED_CHECKPOINT_SHA256:
            blockers.append("benchmark Acer no usa el checkpoint congelado")
        for key in ("p50", "p95", "p99"):
            if key not in (bench.get("block_ms") or {}):
                blockers.append(f"benchmark Acer no reporta {key}")

    result = {
        "schema": "hesychia.jury-readiness.v1",
        "status": "READY" if not blockers else "BLOCKED",
        "blockers": blockers,
        "checks": checks,
        "note": "READY means structural evidence closure; it does not imply clinical efficacy or physical ANC.",
    }

    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    raise SystemExit(0 if not blockers else 2)


if __name__ == "__main__":
    main()
