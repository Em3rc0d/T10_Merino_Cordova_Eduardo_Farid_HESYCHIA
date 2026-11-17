#!/usr/bin/env python3
"""Build a separate adjudication template from two independent review CSVs.

Original reviewer files are never modified. Disagreement is defined over the
fields that affect corpus eligibility: review_decision, purity_judgement and
main_event_audible. Cohen kappa is still calculated on original decisions
before adjudication.
"""
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

KEY_FIELDS=("review_decision","purity_judgement","main_event_audible")
OUT_FIELDS=[
 "asset_id","pcm_sha256",
 "reviewer_a_id","reviewer_a_decision","reviewer_a_purity","reviewer_a_main_event",
 "reviewer_b_id","reviewer_b_decision","reviewer_b_purity","reviewer_b_main_event",
 "adjudicated_decision","adjudicated_purity","adjudicated_main_event_audible",
 "adjudicator_id","adjudication_date_utc","adjudication_notes",
]

def load(path:Path):
    with path.open(newline="",encoding="utf-8-sig") as f:
        r=csv.DictReader(f)
        required={"asset_id","reviewer_id","pcm_sha256",*KEY_FIELDS}
        if not r.fieldnames or not required.issubset(r.fieldnames):
            raise ValueError(f"{path} missing review columns")
        rows=list(r)
    by={};reviewers=set()
    for row in rows:
        aid=row["asset_id"].strip();rid=row["reviewer_id"].strip()
        if not aid or not rid or aid in by: raise ValueError(f"invalid/duplicate row {aid}")
        by[aid]=row;reviewers.add(rid)
    if len(reviewers)!=1: raise ValueError(f"{path} must contain one reviewer_id")
    return by,next(iter(reviewers))

def build(first:Path,second:Path,out:Path):
    a,ra=load(first);b,rb=load(second)
    if ra==rb: raise ValueError("reviewers must be distinct")
    if set(a)!=set(b): raise ValueError("reviewers must cover identical asset_id set")
    disagreements=[]
    for aid in sorted(a):
        x,y=a[aid],b[aid]
        if x["pcm_sha256"].strip().lower()!=y["pcm_sha256"].strip().lower():
            raise ValueError(f"PCM mismatch between reviewers: {aid}")
        differs=any(x[k].strip().lower()!=y[k].strip().lower() for k in KEY_FIELDS)
        if differs:
            disagreements.append({
              "asset_id":aid,"pcm_sha256":x["pcm_sha256"].strip().lower(),
              "reviewer_a_id":ra,"reviewer_a_decision":x["review_decision"],
              "reviewer_a_purity":x["purity_judgement"],"reviewer_a_main_event":x["main_event_audible"],
              "reviewer_b_id":rb,"reviewer_b_decision":y["review_decision"],
              "reviewer_b_purity":y["purity_judgement"],"reviewer_b_main_event":y["main_event_audible"],
              "adjudicated_decision":"","adjudicated_purity":"","adjudicated_main_event_audible":"",
              "adjudicator_id":"","adjudication_date_utc":"","adjudication_notes":"",
            })
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=OUT_FIELDS);w.writeheader();w.writerows(disagreements)
    return {"paired_assets":len(a),"disagreements":len(disagreements),"reviewers":[ra,rb]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--first",type=Path,required=True);p.add_argument("--second",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.first,a.second,a.out),ensure_ascii=False))

if __name__=="__main__":main()
