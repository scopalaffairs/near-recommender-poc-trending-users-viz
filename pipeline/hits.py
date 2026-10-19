import json
import numpy as np
def load(label):
    return json.load(open(f'data/raw/follows_{label}.json'))['follows']
def hits(follows,iters=500,tol=1e-12):
    """Kleinberg HITS on 'i follows j' edges. hub = follows good authorities, authority = followed by good hubs."""
    nodes=sorted({a for a in follows}|{t for ts in follows.values() for t in ts});ix={n:i for i,n in enumerate(nodes)}
    r=np.array([ix[s] for s,ts in follows.items() for t in ts if t!=s]);c=np.array([ix[t] for s,ts in follows.items() for t in ts if t!=s])
    n=len(nodes);h=np.ones(n)/np.sqrt(n);a=h
    for _ in range(iters):
        a=np.zeros(n);np.add.at(a,c,h[r]);a/=np.linalg.norm(a)
        hn=np.zeros(n);np.add.at(hn,r,a[c]);hn/=np.linalg.norm(hn)
        if np.abs(hn-h).sum()<tol: h=hn;break
        h=hn
    return nodes,h,a
