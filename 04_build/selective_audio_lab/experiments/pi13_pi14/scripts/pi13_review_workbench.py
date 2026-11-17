#!/usr/bin/env python3
"""Local, offline human-listening workbench for HESYCHIA's archived corpus.

Requires explicit human choices; never auto-approves audio. Non-network audio
is served only from an allowlisted corpus PCM directory, after SHA-256 check.
Different reviewer IDs use separate, blind review files.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

DECISIONS = ('eligible', 'restricted', 'reject')
PURITY = ('isolated', 'minor_contamination', 'mixed', 'undetermined')
YESNO = ('yes', 'no', 'unsure')
FIELDS = ('asset_id', 'reviewer_id', 'review_date_utc', 'review_decision',
          'purity_judgement', 'main_event_audible', 'secondary_events',
          'speech_present', 'alarm_present', 'review_notes', 'pcm_sha256')

def digest(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def load_manifest(path: Path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        needed = {'asset_id', 'pcm_sha256', 'acoustic_class', 'split'}
        if not reader.fieldnames or not needed.issubset(reader.fieldnames):
            raise ValueError('Manifest missing required columns: '+repr(needed))
        rows = list(reader)
    if len({r['asset_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicated asset_id in manifest')
    for r in rows:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', r['asset_id']):
            raise ValueError('Unsafe asset_id: '+r['asset_id'])
        if not re.fullmatch('[0-9a-fA-F]{64}', r['pcm_sha256']):
            raise ValueError('Invalid PCM SHA for: '+r['asset_id'])
    return rows

def load_reviews(path: Path, reviewer: str, assets: set):
    if not path.exists():
        return {}
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    result={}
    for r in rows:
        aid=r.get('asset_id','')
        if aid not in assets or aid in result or r.get('reviewer_id') != reviewer:
            raise ValueError('Invalid or duplicate review record: '+aid)
        result[aid]=r
    return result

def validate_choice(row: dict):
    for field, choices in [('review_decision', DECISIONS),('purity_judgement',PURITY),
         ('main_event_audible',YESNO),('speech_present',YESNO),('alarm_present',YESNO)]:
        if row.get(field) not in choices:
            raise ValueError(f'Invalid {field}={row.get(field)}')
    if row['review_decision']=='eligible' and (row['purity_judgement']!='isolated' or row['main_event_audible']!='yes'):
        raise ValueError('Eligible requires isolated main event audible=yes')
    if len(row.get('review_notes','')) > 1500 or len(row.get('secondary_events','')) > 500:
        raise ValueError('Notes too long')

def atomic_reviews_write(path: Path, rows: dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.review-',suffix='.csv',dir=path.parent)
    try:
        with os.fdopen(fd,'w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');w.writeheader()
            for aid in sorted(rows): w.writerow(rows[aid])
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def merge_primary_manifest(manifest: Path, review_path: Path, reviewer: str, output: Path):
    rows=load_manifest(manifest)
    reviews=load_reviews(review_path, reviewer, {r['asset_id'] for r in rows})
    if output.resolve()==manifest.resolve() or output.resolve()==review_path.resolve():
        raise ValueError('Refusing to overwrite source files')
    updated=[]
    for r in rows:
        r=r.copy();v=reviews.get(r['asset_id'])
        if v:
            if r['pcm_sha256'].lower()!=v['pcm_sha256'].lower():
                raise ValueError('PCM SHA changed since review: '+r['asset_id'])
            r.update({k:v[k] for k in FIELDS if k not in ('asset_id','pcm_sha256')})
        updated.append(r)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(updated[0]),extrasaction='ignore')
        w.writeheader();w.writerows(updated)
    return len(reviews),len(rows)

def combine_double_reviews(paths: list[Path], out: Path):
    if len(paths)!=2: raise ValueError('Exactly two reviewers required')
    all_rows=[];sets=[];reviewers=[]
    for path in paths:
        with path.open(newline='',encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
        reviewers.append({r['reviewer_id'] for r in rows})
        sets.append({r['asset_id'] for r in rows})
        all_rows.append({r['asset_id']:r for r in rows})
    if len(reviewers[0])!=1 or len(reviewers[1])!=1 or reviewers[0]==reviewers[1]:
        raise ValueError('Require two distinct reviewer IDs')
    both=sorted(sets[0] & sets[1])
    if not both: raise ValueError('No shared reviewed assets')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=('asset_id','reviewer_id','review_decision'))
        w.writeheader()
        for aid in both:
            for data in all_rows:w.writerow({k:data[aid][k] for k in w.fieldnames})
    return {'paired_assets':len(both),'reviewers':[next(iter(x)) for x in reviewers],
            'assets_only_first':len(sets[0]-sets[1]),'assets_only_second':len(sets[1]-sets[0])}

class Workbench:
    def __init__(self,manifest:Path,audio_root:Path,output_dir:Path,reviewer:str, sample_manifest:Path|None=None):
        if not re.fullmatch(r'[A-Za-z0-9_-]{2,60}',reviewer):raise ValueError('Invalid reviewer ID')
        self.manifest=manifest
        self.rows=load_manifest(manifest)
        if sample_manifest is not None:
            sample=load_manifest(sample_manifest)
            original={r['asset_id']:r for r in self.rows}
            for entry in sample:
                aid=entry['asset_id']
                if aid not in original or original[aid]['pcm_sha256'] != entry['pcm_sha256']:
                    raise ValueError('Double-review sample does not match pinned manifest: '+aid)
            ids={r['asset_id'] for r in sample}
            self.rows=[r for r in self.rows if r['asset_id'] in ids]
        self.index={r['asset_id']:r for r in self.rows}
        self.audio_root=audio_root.resolve()
        self.reviewer=reviewer
        self.output=output_dir/f'{reviewer}.csv'
        self.reviews=load_reviews(self.output,reviewer,set(self.index))
        self.manifest_sha256=digest(manifest)

    def audio_for(self,aid):
        if aid not in self.index: raise KeyError('Unknown asset')
        path=(self.audio_root / (aid+'.wav')).resolve()
        if not path.is_relative_to(self.audio_root) or not path.is_file():
            raise FileNotFoundError('Missing audio for '+aid)
        if digest(path).lower() != self.index[aid]['pcm_sha256'].lower():
            raise ValueError('Audio checksum mismatch for '+aid)
        return path

    def save(self,data):
        aid=data.get('asset_id','')
        if aid not in self.index:raise ValueError('Unknown asset_id')
        if data.get('manifest_sha256')!=self.manifest_sha256:raise ValueError('Manifest changed during review')
        row={k:str(data.get(k,'')).strip() for k in FIELDS}
        row['asset_id']=aid
        row['reviewer_id']=self.reviewer
        row['pcm_sha256']=self.index[aid]['pcm_sha256']
        row['review_date_utc']=datetime.now(timezone.utc).isoformat()
        validate_choice(row)
        self.audio_for(aid)  # Recorded only if actual PCM is available and matches pinned hash.
        self.reviews[aid]=row
        atomic_reviews_write(self.output,self.reviews)
        return row

def page(wb:Workbench,i:int):
    i=max(0,min(len(wb.rows)-1,i));asset=wb.rows[i]
    aid=asset['asset_id']; old=wb.reviews.get(aid,{})
    def esc(x):return html.escape(str(x),quote=True)
    def opts(name, values):
        return ''.join(f'<option value="{esc(v)}" {"selected" if old.get(name)==v else ""}>{esc(v)}</option>' for v in values)
    n=len(wb.reviews);total=len(wb.rows)
    return f'''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>HESYCHIA · Auditoría humana</title>
<style>body{{font:16px system-ui;background:#f4f6f9;color:#172333;margin:0}}main{{max-width:790px;margin:28px auto;padding:24px;background:white;border-radius:16px;box-shadow:0 8px 32px #0001}}label{{display:block;margin:15px 0 5px;font-weight:600}}select,textarea,button{{width:100%;padding:12px;border:1px solid #bdc5d1;border-radius:9px;font:inherit}}textarea{{min-height:70px}}button{{background:#133e6a;color:white;cursor:pointer;margin-top:20px}}a{{color:#205a9a}}audio{{width:100%}}header{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}small{{color:#5a6675}}.pill{{background:#e7eef8;padding:7px 10px;border-radius:8px}}nav{{display:flex;justify-content:space-between}}nav a{{padding:12px}}#status{{color:#0b6534;font-weight:700}}.warn{{color:#9e4b16}}</style>
<main><header><strong>HESYCHIA · Revisión auditiva</strong><span class="pill">{esc(wb.reviewer)} · {n}/{total} guardados</span></header>
<p><small>Archivo {i+1}/{total} · {esc(aid)} · {esc(asset['split'])} · {esc(asset['acoustic_class'])}</small></p>
<p><strong>Escucha real obligatoria.</strong> Se verifica el SHA-256 original antes de reproducir y guardar.</p>
<audio controls preload="none" src="/audio/{esc(aid)}"></audio><p id="audiofail" class="warn"></p>
<form id="review"><input type="hidden" name="asset_id" value="{esc(aid)}"/><input type="hidden" name="manifest_sha256" value="{wb.manifest_sha256}"/>
<label>¿Se escucha el evento principal?</label><select required name="main_event_audible"><option value="">Seleccionar…</option>{opts('main_event_audible',YESNO)}</select>
<label>Pureza acústica</label><select required name="purity_judgement"><option value="">Seleccionar…</option>{opts('purity_judgement',PURITY)}</select>
<label>¿Hay voz presente?</label><select required name="speech_present"><option value="">Seleccionar…</option>{opts('speech_present',YESNO)}</select>
<label>¿Hay alarma o sirena presente?</label><select required name="alarm_present"><option value="">Seleccionar…</option>{opts('alarm_present',YESNO)}</select>
<label>Eventos secundarios audibles</label><textarea name="secondary_events" placeholder="Describir sin inferir lo que no se escuchó">{esc(old.get('secondary_events',''))}</textarea>
<label>Decisión</label><select required name="review_decision"><option value="">Seleccionar…</option>{opts('review_decision',DECISIONS)}</select>
<label>Observaciones</label><textarea name="review_notes">{esc(old.get('review_notes',''))}</textarea><button>Guardar revisión verificada</button></form>
<p id="status"></p><nav><a href="/?i={max(0,i-1)}">← Anterior</a><a href="/?i={min(total-1,i+1)}">Siguiente →</a></nav>
<p><small>Revisiones separadas por evaluador; nunca se muestran decisiones de otros evaluadores. La concordancia κ se calcula posteriormente.</small></p></main>
<script>const frm=document.querySelector('#review');frm.addEventListener('submit',async e=>{{e.preventDefault();const data=Object.fromEntries(new FormData(frm));const res=await fetch('/save',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});const ans=await res.json();document.querySelector('#status').textContent=ans.error||'Revisión guardada';if(res.ok){{setTimeout(()=>location.href='/?i={min(total-1,i+1)}',500)}}}});
const player=document.querySelector('audio');player.addEventListener('error',()=>{{document.querySelector('#audiofail').textContent='Audio faltante o hash incorrecto. No se puede guardar.'}});</script></html>'''

def serve(wb:Workbench,port:int):
    class Handler(BaseHTTPRequestHandler):
        def json(self,obj,code=200):
            raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            p=urlparse(self.path)
            if p.path=='/':
                try:i=int(parse_qs(p.query).get('i',['0'])[0])
                except ValueError:i=0
                body=page(wb,i).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            elif p.path.startswith('/audio/'):
                aid=p.path[len('/audio/'):]
                try:
                    path=wb.audio_for(aid)
                    data=path.read_bytes()
                    self.send_response(200);self.send_header('Content-Type','audio/wav');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                except (KeyError,FileNotFoundError,ValueError) as e:self.json({'error':str(e)},404)
            else:self.json({'error':'not found'},404)
        def do_POST(self):
            if self.path!='/save':return self.json({'error':'not found'},404)
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<20000:raise ValueError('Invalid payload size')
                data=json.loads(self.rfile.read(n))
                self.json({'status':'saved','asset_id':wb.save(data)['asset_id']})
            except (ValueError,KeyError,TypeError,FileNotFoundError) as e:self.json({'error':str(e)},400)
    http=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Revisor {wb.reviewer} · {len(wb.rows)} items · http://127.0.0.1:{port} · salida {wb.output}',flush=True)
    try:http.serve_forever()
    finally:http.server_close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='mode',required=True)
    s=sub.add_parser('serve');s.add_argument('--manifest',type=Path,required=True);s.add_argument('--audio-root',type=Path,required=True);s.add_argument('--out-dir',type=Path,required=True);s.add_argument('--reviewer',required=True);s.add_argument('--sample-manifest',type=Path);s.add_argument('--port',type=int,default=8765)
    e=sub.add_parser('export-primary');e.add_argument('--manifest',type=Path,required=True);e.add_argument('--review-csv',type=Path,required=True);e.add_argument('--reviewer',required=True);e.add_argument('--out',type=Path,required=True)
    d=sub.add_parser('export-double');d.add_argument('--first',type=Path,required=True);d.add_argument('--second',type=Path,required=True);d.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='serve': serve(Workbench(a.manifest,a.audio_root,a.out_dir,a.reviewer,a.sample_manifest),a.port)
    if a.mode=='export-primary':
        n,total=merge_primary_manifest(a.manifest,a.review_csv,a.reviewer,a.out)
        print(json.dumps({'reviewed':n,'total':total,'output':str(a.out)}))
    if a.mode=='export-double':print(json.dumps(combine_double_reviews([a.first,a.second],a.out)))
if __name__=='__main__':main()
