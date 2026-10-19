"""Hold-out evaluation: how well do the recommendation ideas of the original near_recommender repository
predict the follow edges that really appeared afterwards?

For a window (T0, T1] the graph at T0 is rebuilt from edge creation block heights, each method recommends
K accounts per user from that graph, and a user counts as a hit if at least one recommended account was
followed within the window. Methods (all from the original repository, recomputed here):

  popularity    most followed accounts the user does not follow yet
  hits          highest HITS authority, same exclusion
  friends       friends of friends: most followed by the accounts the user already follows
  trending      random trending hubs (the 20-hub cohort), preferring communities the user does not follow yet
  stored        the saved HITS recommendations of 2023-04-26 (near_recommender, matrix_intersection_05.json)
  random        random accounts that are followed by anyone (reference level)

Needs data/edges_bh_2024-01-15.json and data/raw/stored_recommendations_2023-04-26.json; run from the repo root.
K is the number of recommendations per user (5 as in the original top_k, and 15 as in the stored list).
Only edges that still exist on 2024-01-15 are seen (unfollows were below 0.5 %).
"""
import collections
import datetime
import json
import math
import random
import sys

sys.path.insert(0, 'pipeline')
from hits import hits  # noqa: E402
from timeline import ANCHORS  # noqa: E402

MATRIX = 'data/raw/stored_recommendations_2023-04-26.json'  # near_recommender matrix_intersection_05.json, best first


def to_block(day):
    """Inverse of timeline.to_date: linear interpolation between the exactly known anchor blocks."""
    ordinal = datetime.date.fromisoformat(day).toordinal()
    pts = [(datetime.date.fromisoformat(d).toordinal(), b) for b, d in ANCHORS]
    for (d0, b0), (d1, b1) in zip(pts, pts[1:]):
        if d0 <= ordinal <= d1:
            return round(b0 + (ordinal - d0) / (d1 - d0) * (b1 - b0))
    raise ValueError(day)


def graph_at(edges, block):
    g = collections.defaultdict(set)
    for s, targets in edges.items():
        for t, b in targets.items():
            if b <= block:
                g[s].add(t)
    return g


def new_edges(edges, b0, b1):
    out = collections.defaultdict(set)
    for s, targets in edges.items():
        for t, b in targets.items():
            if b0 < b <= b1:
                out[s].add(t)
    return out


def pick(ranked, followed, user, k):
    out = []
    for v in ranked:
        if v != user and v not in followed:
            out.append(v)
            if len(out) == k:
                break
    return out


def evaluate(edges, cohort, matrix, start, end, label, ks=(5, 15)):
    b0, b1 = to_block(start), to_block(end)
    g0, fresh = graph_at(edges, b0), new_edges(edges, b0, b1)
    indeg = collections.Counter(v for ts in g0.values() for v in ts)
    nodes, _, auth = hits({s: list(ts) for s, ts in g0.items()})
    by_pop = [v for v, _ in indeg.most_common(200)]
    by_hits = [nodes[i] for i in sorted(range(len(nodes)), key=lambda i: -auth[i])[:200]]
    hubs = sorted(cohort)
    anyone = sorted(indeg)
    rng = random.Random(0)
    users = sorted(u for u in fresh if u in g0 and fresh[u] - g0[u])

    def friends(u, k):
        c = collections.Counter(v for x in g0[u] for v in g0.get(x, ()) if v != u and v not in g0[u])
        return [v for v, _ in sorted(c.items(), key=lambda kv: (-kv[1], -indeg[kv[0]]))[:k]]

    def trending(u, k):
        followed_groups = {cohort[v] for v in g0[u] if v in cohort}
        outside = [h for h in hubs if h not in g0[u] and cohort[h] not in followed_groups]
        pool = outside if len(outside) >= k else [h for h in hubs if h not in g0[u]]
        return rng.sample(pool, min(k, len(pool)))

    def rate(rec, subset, repeats=1):
        """Share of users with at least one recommended account among their new follows (mean over repeats)."""
        total = 0.0
        for _ in range(repeats):
            total += sum(1 for u in subset if set(rec(u)) & fresh[u]) / len(subset)
        return total / repeats

    methods = {}
    for tag, subset in (('all', users), ('matrix', [u for u in users if u in matrix])):
        if not subset:
            continue
        for k in ks:
            recs = {
                'popularity': (lambda u, k=k: pick(by_pop, g0[u], u, k), 1),
                'hits': (lambda u, k=k: pick(by_hits, g0[u], u, k), 1),
                'friends': (lambda u, k=k: friends(u, k), 1),
                'trending': (lambda u, k=k: trending(u, k), 20),
                'random': (lambda u, k=k: rng.sample(anyone, k), 20),
            }
            if tag == 'matrix':
                recs['stored'] = (lambda u, k=k: pick(matrix[u], g0[u], u, k), 1)
            for name, (rec, repeats) in recs.items():
                methods[f'{tag}/{name}@{k}'] = {'users': len(subset), 'rate': round(rate(rec, subset, repeats), 4)}

    # cold start: accounts whose first follow falls into the window
    newcomers = sorted(u for u in fresh if u not in g0)
    cold = {'newcomers': len(newcomers)}
    if newcomers:
        k = ks[0]
        in_cohort = [{cohort[v] for v in fresh[u] if v in cohort} for u in newcomers]
        cold['follow_a_hub'] = round(sum(1 for g in in_cohort if g) / len(newcomers), 4)
        cold['follow_2_communities'] = round(sum(1 for g in in_cohort if len(g) >= 2) / len(newcomers), 4)
        # chance that k random hubs contain at least one of the hubs the newcomer followed (hypergeometric)
        chance = sum(1 - math.comb(len(hubs) - m, k) / math.comb(len(hubs), k) for m in (len(fresh[u] & set(hubs)) for u in newcomers))
        cold[f'hit_trending@{k}'] = round(chance / len(newcomers), 4)
        cold[f'hit_popularity@{k}'] = round(sum(1 for u in newcomers if set(by_pop[:k]) & fresh[u]) / len(newcomers), 4)
    return {'label': label, 'window': [start, end], 'users': len(users), 'methods': methods, 'cold_start': cold}


def main():
    base = json.load(open('trending_users.json'))
    cohort = {n['id']: n['group'] for n in base['nodes'] if n['group'] != 1000}
    edges = json.load(open('data/edges_bh_2024-01-15.json'))['edges']
    matrix = json.load(open(MATRIX))
    out = [
        evaluate(edges, cohort, matrix, '2023-04-26', '2023-10-31', 'before launch (matrix date to 2023-10-31)'),
        evaluate(edges, cohort, matrix, '2023-11-07', '2024-01-15', 'after launch (2023-11-07 to 2024-01-15)'),
    ]
    json.dump(out, open('data/evaluation.json', 'w'), indent=1)
    for window in out:
        print(f"\n{window['label']}: {window['users']} users with a new follow")
        print(f"  {'method':22}{'users':>7}{'hit rate':>10}")
        for name, r in window['methods'].items():
            print(f"  {name:22}{r['users']:>7}{r['rate']:>10.1%}")
        print('  cold start:', window['cold_start'])


if __name__ == '__main__':
    main()
