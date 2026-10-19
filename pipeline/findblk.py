import json,urllib.request,datetime,time
RPCS=['https://archival-rpc.mainnet.fastnear.com','https://archival-rpc.mainnet.near.org']
def ts(h):
    for t in range(10):
        try:
            req=urllib.request.Request(RPCS[t%2],json.dumps({"jsonrpc":"2.0","id":1,"method":"block","params":{"block_id":h}}).encode(),{'content-type':'application/json','user-agent':'Mozilla/5.0'})
            r=json.load(urllib.request.urlopen(req,timeout=40))
            if 'result' in r: return datetime.datetime.fromtimestamp(r['result']['header']['timestamp']/1e9,datetime.UTC).replace(tzinfo=None)
            h+=1  # skipped block
        except Exception: time.sleep(3*(t+1))
    raise SystemExit('rpc fail')
def find(target,lo,hi):
    while hi-lo>300:
        m=(lo+hi)//2
        if ts(m)<target: lo=m
        else: hi=m
    return hi
for d,lo,hi in [('2023-10-31',100_000_000,106_000_000)]:
    b=find(datetime.datetime.fromisoformat(d),lo,hi);print(d,b,ts(b),flush=True)
