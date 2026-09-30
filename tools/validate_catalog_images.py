#!/usr/bin/env python3
"""Auditoría global del manifiesto y mediciones comparables de los derivados."""
from __future__ import annotations
import argparse, hashlib, json, statistics, time
from pathlib import Path
from PIL import Image

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def inspect(path):
    reads=[]
    for _ in range(3):
        t=time.perf_counter(); data=path.read_bytes(); reads.append((time.perf_counter()-t)*1000)
    t=time.perf_counter()
    with Image.open(path) as im:
        im.verify()
    with Image.open(path) as im:
        im.load(); width,height,fmt=im.width,im.height,im.format
    return {'bytes':len(data),'width':width,'height':height,'format':fmt,
            'read_ms_median':round(statistics.median(reads),3),'decode_ms':round((time.perf_counter()-t)*1000,3)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo',type=Path,default=Path.cwd()); args=ap.parse_args(); repo=args.repo.resolve()
    root=repo/'catalogo-fotos'; inv=json.loads((root/'inventario-catalogo.json').read_text(encoding='utf-8')); man=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    usage={x['url']:x for x in inv['url_usage']}; images=man['images']; errors=[]; originals={}; remote_originals={}; variants={'card':{},'gallery':{}}
    if set(usage)!=set(images): errors.append({'coverage':{'missing':sorted(set(usage)-set(images)),'extra':sorted(set(images)-set(usage))}})
    for url,item in usage.items():
        entry=images.get(url)
        if not entry: continue
        if entry.get('original_file')!=item['original_file']: errors.append({'url':url,'error':'original_file mismatch'})
        if item.get('original_file'):
            original=repo/item['original_file']; oi=originals.setdefault(item['original_file'],inspect(original)); digest=sha(original)
            if entry.get('original_sha256')!=digest: errors.append({'url':url,'error':'original hash mismatch'})
        elif item.get('match_status')=='remote_url':
            oi=item.get('metadata') or {}
            if not oi.get('width') or not oi.get('height') or not oi.get('sha256'):
                errors.append({'url':url,'error':'remote source metadata missing'}); continue
            remote_originals[url]=oi
            if entry.get('original_url')!=url or entry.get('original_sha256')!=oi['sha256']:
                errors.append({'url':url,'error':'remote source mismatch'})
        else:
            errors.append({'url':url,'error':'unresolved original'}); continue
        for variant,limit in (('card',480),('gallery',1200)):
            path=repo/entry[variant]
            try: vi=variants[variant].setdefault(entry[variant],inspect(path))
            except Exception as exc: errors.append({'url':url,'variant':variant,'error':str(exc)}); continue
            if max(vi['width'],vi['height'])>min(limit,max(oi['width'],oi['height'])): errors.append({'url':url,'variant':variant,'error':'upscaled or oversized'})
    original_total=sum(x['bytes'] for x in originals.values())+sum(x['bytes'] for x in remote_originals.values())
    result={'status':'ok' if not errors else 'error','catalog_products':inv['summary']['catalog_products'],'catalog_urls':len(usage),
      'unique_original_files':len(originals),'remote_original_urls':len(remote_originals),'manifest_entries':len(images),'errors':errors,
      'original_total_bytes':original_total,
      'card_unique_files':len(variants['card']),'card_total_bytes':sum(x['bytes'] for x in variants['card'].values()),
      'gallery_unique_files':len(variants['gallery']),'gallery_total_bytes':sum(x['bytes'] for x in variants['gallery'].values()),
      'card_reduction_percent':round((1-sum(x['bytes'] for x in variants['card'].values())/original_total)*100,2),
      'gallery_reduction_percent':round((1-sum(x['bytes'] for x in variants['gallery'].values())/original_total)*100,2),
      'reused_repo_webp_urls':sum(1 for e in images.values() if not e['card'].startswith('catalogo-fotos/') or not e['gallery'].startswith('catalogo-fotos/')),
      'generated_unique_files':len(set(e[v] for e in images.values() for v in ('card','gallery') if e[v].startswith('catalogo-fotos/'))),
      'generated_total_bytes':sum((repo/p).stat().st_size for p in set(e[v] for e in images.values() for v in ('card','gallery') if e[v].startswith('catalogo-fotos/'))),
      'measurement':'lectura y decodificación local controlada; no equivale a transferencia por Internet',
      'original_read_ms_total':round(sum(x['read_ms_median'] for x in originals.values()),2),
      'original_decode_ms_total':round(sum(x['decode_ms'] for x in originals.values()),2),
      'card_read_ms_total':round(sum(x['read_ms_median'] for x in variants['card'].values()),2),
      'card_decode_ms_total':round(sum(x['decode_ms'] for x in variants['card'].values()),2),
      'gallery_read_ms_total':round(sum(x['read_ms_median'] for x in variants['gallery'].values()),2),
      'gallery_decode_ms_total':round(sum(x['decode_ms'] for x in variants['gallery'].values()),2)}
    (root/'validacion-imagenes.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['status']=='ok' else 1)
if __name__=='__main__': main()
