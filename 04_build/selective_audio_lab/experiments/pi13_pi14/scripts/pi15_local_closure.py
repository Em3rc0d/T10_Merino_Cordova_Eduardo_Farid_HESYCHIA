#!/usr/bin/env python3
"""Local PI15 closure helper for HESYCHIA.

This wrapper does not create scientific evidence by itself. It orchestrates the
versioned scripts and fails closed when human/physical artifacts are absent.
Run from 04_build/selective_audio_lab.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parents[2]
EXP = LAB / "experiments/pi13_pi14"
SCRIPTS = EXP / "scripts"
CHECKPOINT = LAB / "models/m4_sci_real_candidate_v1/selected/candidate.pt"


def run(args, *, allow_fail=False):
    print("+", " ".join(str(x) for x in args), flush=True)
    p = subprocess.run([str(x) for x in args])
    if p.returncode and not allow_fail:
        raise SystemExit(p.returncode)
    return p.returncode


def audit_status(a):
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not Path(a.reviewer_a).is_file() or not Path(a.reviewer_b).is_file():
        print("BLOCKED: faltan reviewer_A.csv y/o reviewer_B.csv")
        return 2
    run([sys.executable, SCRIPTS/"pi13_review_workbench.py", "export-double",
         "--first", a.reviewer_a, "--second", a.reviewer_b,
         "--out", out/"double_review_93.csv"])
    run([sys.executable, SCRIPTS/"pi13_agreement.py",
         "--reviews", out/"double_review_93.csv", "--out", out/"kappa_93.json"])
    run([sys.executable, SCRIPTS/"pi13_adjudication_template.py",
         "--first", a.reviewer_a, "--second", a.reviewer_b,
         "--out", out/"adjudication_disagreements.csv"])
    k=json.loads((out/"kappa_93.json").read_text(encoding="utf-8"))
    print(json.dumps({"pairs":k.get("pairs"),"cohen_kappa":k.get("cohen_kappa"),
                      "adjudication":str(out/"adjudication_disagreements.csv")},indent=2))
    if not Path(a.final_review).is_file():
        print("BLOCKED: completa adjudicación y proporciona final_review_93.csv para contaminación IC95%.")
        return 2
    run([sys.executable, SCRIPTS/"pi13_contamination_ci.py",
         "--reviewed-csv", a.final_review, "--expected-n", "93",
         "--out", out/"contamination_93.json"])
    return 0


def benchmark_acer(a):
    out=Path(a.out).resolve()
    return run([
        sys.executable, SCRIPTS/"pi14_m4_forward_benchmark.py",
        "--checkpoint", CHECKPOINT,
        "--model-src", LAB/"src",
        "--out", out,
        "--runs", str(a.runs),
        "--warmup", str(a.warmup),
        "--hops", "16",
        "--seconds", "2",
        "--device", "cpu",
        "--threads", str(a.threads),
        "--min-samples", "1000",
        "--device-label", "Acer Nitro 5",
    ])


def jury_status(a):
    cmd=[sys.executable,SCRIPTS/"pi15_jury_readiness.py","--lab",LAB,
         "--audit-sample",a.audit_sample,
         "--kappa",a.kappa,
         "--corpus-review-report",a.corpus_review_report,
         "--freeze-report",a.freeze_report,
         "--confirmatory-analysis",a.confirmatory_analysis,
         "--cp02-report",a.cp02_report,
         "--acer-benchmark",a.acer_benchmark,
         "--out",a.out]
    return run(cmd, allow_fail=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="cmd",required=True)

    x=sub.add_parser("audit-status")
    x.add_argument("--reviewer-a",required=True)
    x.add_argument("--reviewer-b",required=True)
    x.add_argument("--final-review",required=True)
    x.add_argument("--out",default="experiments/pi13_pi14/outputs/reviews")
    x.set_defaults(fn=audit_status)

    x=sub.add_parser("benchmark-acer")
    x.add_argument("--out",default="experiments/pi13_pi14/outputs/m4_forward_acer")
    x.add_argument("--runs",type=int,default=100)
    x.add_argument("--warmup",type=int,default=8)
    x.add_argument("--threads",type=int,default=4)
    x.set_defaults(fn=benchmark_acer)

    x=sub.add_parser("jury-status")
    for name in ("audit-sample","kappa","corpus-review-report","freeze-report",
                 "confirmatory-analysis","cp02-report","acer-benchmark"):
        x.add_argument("--"+name,required=True)
    x.add_argument("--out",default="experiments/pi13_pi14/outputs/jury_readiness.json")
    x.set_defaults(fn=jury_status)

    a=p.parse_args()
    raise SystemExit(a.fn(a))


if __name__=="__main__":
    main()
