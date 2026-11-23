#!/usr/bin/env python3
"""Create the final external target manifest from prepared PCM + human review.

Selection is based ONLY on human target-purity criteria fixed before model
inference. Model outputs are neither accepted nor read by this script.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from collections import Counter
from pathlib import Path

def read(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))

def canon(rows):
    lines=[f"{r['candidate_id']}|{r['target_class']}|{r['source_group']}|{r['pcm_sha256']}"
           for r in sorted(rows,key=lambda x:x["candidate_id"])]
    return hashlib.sha256(("\n".join(lines)+"\n").encode()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prepared",type=Path,required=True);p.add_argument("--human-review",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or a.report.exists():raise ValueError("refusing overwrite")
    prepared={r["candidate_id"].strip():r for r in read(a.prepared)}
    reviews=read(a.human_review);by={}
    for r in reviews:
        aid=r.get("asset_id","").strip()
        if not aid or aid in by:raise ValueError(f"invalid/duplicate human review {aid}")
        by[aid]=r
    eligible=[];rejected=[]
    for cid,r in sorted(prepared.items()):
        if r.get("prep_status","").strip()!="READY_FOR_HUMAN_REVIEW":continue
        if cid not in by:raise ValueError(f"missing human review for prepared candidate {cid}")
        h=by[cid]
        if h.get("pcm_sha256","").strip().lower()!=r.get("pcm_sha256","").strip().lower():
            raise ValueError(f"PCM hash mismatch for {cid}")
        ok=(h.get("review_decision","").strip().lower()=="eligible" and
            h.get("purity_judgement","").strip().lower()=="isolated" and
            h.get("main_event_audible","").strip().lower()=="yes")
        if ok:
            x=dict(r);x["human_audit_status"]="ELIGIBLE";eligible.append(x)
        else:rejected.append(cid)
    groups={r["source_group"] for r in eligible}
    counts=Counter(r["target_class"] for r in eligible)
    if len(groups)<20 or len(groups)!=len(eligible) or set(counts)!={"Chainsaw","Vacuum_cleaner"}:
        raise ValueError(f"external target gate failed: groups={len(groups)}, class_counts={dict(counts)}")
    fields=list(eligible[0])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(eligible)
    report={"schema":"hesychia.pi15-final-external-targets.v1","eligible":len(eligible),
            "class_counts":dict(counts),"rejected":rejected,"source_groups":len(groups),
            "canonical_identity_sha256":canon(eligible),
            "selection_rule":"eligible + isolated + main_event_audible=yes; no model outputs used"}
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
