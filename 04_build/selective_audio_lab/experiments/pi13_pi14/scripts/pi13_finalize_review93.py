#!/usr/bin/env python3
"""Create the final 93-row consensus review from immutable A/B reviews + adjudication.

Agreed rows are copied directly. Any disagreement in decision, purity or main
-event audibility MUST have a completed adjudication row. Original reviewer
files remain immutable evidence.
"""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path

VALID_DECISIONS={"eligible","restricted","reject"}
VALID_PURITY={"isolated","minor_contamination","mixed","undetermined"}
VALID_AUDIBLE={"yes","no","uncertain"}

def rows(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))

def index_review(path):
    data=rows(path);by={}
    reviewer=set()
    for r in data:
        aid=r.get("asset_id","").strip();rid=r.get("reviewer_id","").strip()
        if not aid or not rid or aid in by: raise ValueError(f"invalid/duplicate {aid} in {path}")
        by[aid]=r;reviewer.add(rid)
    if len(reviewer)!=1:raise ValueError("each review file must contain one reviewer")
    return by,next(iter(reviewer))

def canonical_sha(out_rows):
    lines=[f"{r['asset_id']}|{r['pcm_sha256']}|{r['review_decision']}|{r['purity_judgement']}|{r['main_event_audible']}"
           for r in sorted(out_rows,key=lambda x:x["asset_id"])]
    return hashlib.sha256(("\n".join(lines)+"\n").encode()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--first",type=Path,required=True);p.add_argument("--second",type=Path,required=True)
    p.add_argument("--adjudication",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or a.report.exists():raise ValueError("refusing overwrite")
    A,ra=index_review(a.first);B,rb=index_review(a.second)
    if ra==rb or set(A)!=set(B) or len(A)!=93:raise ValueError("need same 93 assets from two distinct reviewers")
    adj={r["asset_id"].strip():r for r in rows(a.adjudication)}
    out=[];disagreements=0
    for aid in sorted(A):
        x,y=A[aid],B[aid]
        if x["pcm_sha256"].strip().lower()!=y["pcm_sha256"].strip().lower():
            raise ValueError(f"PCM mismatch: {aid}")
        keys=("review_decision","purity_judgement","main_event_audible")
        same=all(x[k].strip().lower()==y[k].strip().lower() for k in keys)
        if same:
            decision=x["review_decision"].strip().lower();purity=x["purity_judgement"].strip().lower()
            audible=x["main_event_audible"].strip().lower();note="A/B agreement"
        else:
            disagreements+=1
            if aid not in adj:raise ValueError(f"missing adjudication for {aid}")
            z=adj[aid]
            decision=z.get("adjudicated_decision","").strip().lower()
            purity=z.get("adjudicated_purity","").strip().lower()
            audible=z.get("adjudicated_main_event_audible","").strip().lower()
            if not z.get("adjudicator_id","").strip() or not z.get("adjudication_date_utc","").strip():
                raise ValueError(f"incomplete adjudication metadata for {aid}")
            note=f"adjudicated by {z['adjudicator_id'].strip()}: {z.get('adjudication_notes','').strip()}"
        if decision not in VALID_DECISIONS or purity not in VALID_PURITY or audible not in VALID_AUDIBLE:
            raise ValueError(f"invalid final decision for {aid}")
        speech=x.get("speech_present","").strip().lower()
        if speech!=y.get("speech_present","").strip().lower():speech="uncertain"
        alarm=x.get("alarm_present","").strip().lower()
        if alarm!=y.get("alarm_present","").strip().lower():alarm="uncertain"
        out.append({
          "asset_id":aid,"reviewer_id":"double_review_consensus",
          "review_date_utc":max(x.get("review_date_utc",""),y.get("review_date_utc","")),
          "pcm_sha256":x["pcm_sha256"].strip().lower(),"main_event_audible":audible,
          "secondary_events":x.get("secondary_events","").strip() if x.get("secondary_events","").strip()==y.get("secondary_events","").strip() else "reviewers_differ",
          "speech_present":speech,"alarm_present":alarm,"purity_judgement":purity,
          "review_decision":decision,"review_notes":note,
        })
    fields=list(out[0])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    report={"schema":"hesychia.pi15-final-review93.v1","rows":93,"reviewers":[ra,rb],
            "disagreements_adjudicated":disagreements,"canonical_final_decision_sha256":canonical_sha(out),
            "note":"Original A/B review files remain the source evidence; this file is consensus/adjudication output."}
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":main()
