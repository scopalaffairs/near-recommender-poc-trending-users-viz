import json,sys,time,os,threading,urllib.error
sys.path.insert(0,'.')
import socialdb as S
from concurrent.futures import ThreadPoolExecutor
accts=sorted(json.load(open('data/follow_keys_now.json')))
SNAPS=[('2023-04-15',89599925),('2023-10-31',104573607),('2024-01-15',110424804)]
BS=50;WORKERS=2;MIN_GAP=0.6   # ~1.7 req/s overall
gap_lock=threading.Lock();last=[0.0]
def throttled(accounts,block):
    while True:
        with gap_lock:
            w=last[0]+MIN_GAP-time.time()
            if w>0: time.sleep(w)
            last[0]=time.time()
        try: return S.follows(accounts,block,tries=3)
        except Exception as e:
            pause=90 if '429' in str(e) else 15
            print('retry after',pause,'s:',str(e)[:80],flush=True);time.sleep(pause)
for label,block in SNAPS:
    out_f=f'data/raw/follows_{label}.json';ck_f=f'data/raw/ck_{label}.json'
    if os.path.exists(out_f): continue
    done=json.load(open(ck_f)) if os.path.exists(ck_f) else {}
    todo=[accts[i:i+BS] for i in range(0,len(accts),BS) if accts[i] not in done]
    print(label,block,len(todo),'chunks to do',flush=True);n=[0];lk=threading.Lock();t0=time.time()
    def work(c):
        r=throttled(c,block)
        with lk:
            done[c[0]]=r;n[0]+=1
            if n[0]%50==0:
                json.dump(done,open(ck_f,'w'));print(f'{label} {n[0]}/{len(todo)} chunks, {round(time.time()-t0)}s',flush=True)
    with ThreadPoolExecutor(WORKERS) as ex: list(ex.map(work,todo))
    g={a:f for r in done.values() for a,f in r.items() if f}
    json.dump({'block':block,'label':label,'follows':g},open(out_f,'w'))
    os.remove(ck_f) if os.path.exists(ck_f) else None
    print('DONE',label,block,len(g),'accounts,',sum(map(len,g.values())),'edges',round(time.time()-t0),'s',flush=True)
