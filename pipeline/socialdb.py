import json,urllib.request,base64,time,threading
from concurrent.futures import ThreadPoolExecutor
RPCS=['https://archival-rpc.mainnet.fastnear.com','https://archival-rpc.mainnet.near.org']
_gate=threading.Semaphore(3)  # global cap on concurrent RPC calls
def _call(args,block,rpc,timeout=90):
    p={"request_type":"call_function","block_id":block,"account_id":"social.near","method_name":"get","args_base64":base64.b64encode(json.dumps(args).encode()).decode()}
    req=urllib.request.Request(rpc,json.dumps({"jsonrpc":"2.0","id":1,"method":"query","params":p}).encode(),{'content-type':'application/json','user-agent':'Mozilla/5.0'})
    with _gate: r=json.load(urllib.request.urlopen(req,timeout=timeout))
    if 'error' in r: raise RuntimeError(str(r['error'])[:200])
    if 'error' in r['result']: raise RuntimeError(r['result']['error'][:200])
    return json.loads(bytes(r['result']['result']))
def follows(accounts,block,tries=12):
    """-> {account: [followed,...]} at block; splits batch on gas errors, retries on transport errors"""
    for t in range(tries):
        try:
            res=_call({"keys":[f"{a}/graph/follow/*" for a in accounts]},block,RPCS[t%2])
            return {a:list(res.get(a,{}).get('graph',{}).get('follow',{})) for a in accounts}
        except RuntimeError as e:
            if 'GasLimit' in str(e) and len(accounts)>1:
                h=len(accounts)//2;o=follows(accounts[:h],block);o.update(follows(accounts[h:],block));return o
            if t==tries-1: raise
        except Exception as e:
            if t==tries-1: raise
            time.sleep(min(60,3*(t+1)**1.5) if '429' in str(e) else 2*(t+1))
def fetch_all(accounts,block,bs=50,workers=8,progress=None):
    chunks=[accounts[i:i+bs] for i in range(0,len(accounts),bs)];out={};lock=threading.Lock();done=[0]
    def work(c):
        r=follows(c,block)
        with lock:
            out.update(r);done[0]+=1
            if progress and done[0]%progress==0: print(f'{done[0]}/{len(chunks)} chunks',flush=True)
    with ThreadPoolExecutor(workers) as ex: list(ex.map(work,chunks))
    return out
