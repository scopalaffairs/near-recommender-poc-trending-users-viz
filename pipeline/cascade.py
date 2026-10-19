"""Build trending_users graphs and mixing metrics from follow-graph snapshots.

Cascade (run from the repo root: python3 pipeline/cascade.py):
  1. HITS on the full follow graph of a snapshot (hub + authority score per account).
  2. Root userbase R = seeds (root.near, mob.near, eugene.near) and the accounts they follow.
  3. Cohort of anchor accounts ("hubs") with a community group, fixed at the baseline (the 20
     hubs of the original trending_users.json) and tracked unchanged through every snapshot, so
     before/after compare the same accounts instead of a re-ranked selection.
  4. Graph per snapshot = anchors + all their followers (group 1000), follower -> anchor edges
     (value 0) and anchor -> anchor edges (value 1). Leaves following anchors of two or more
     groups are marked "bridge": those are the places where clusters meet.
  5. Also detected per snapshot, reported in metrics only: isolated clusters = non-R accounts with
     many followers who follow nobody in R.
"""
import collections
import json
import sys

import numpy as np

sys.path.insert(0, 'pipeline')
from hits import hits, load  # noqa: E402

SNAPSHOTS = ['2023-04-15', '2023-10-31', '2024-01-15']
SEEDS = ['root.near', 'mob.near', 'eugene.near']
MIN_FOLLOWERS, MIN_ISOLATION = 25, 0.5


def main():
    base = json.load(open('trending_users.json'))
    group_of = {n['id']: n['group'] for n in base['nodes'] if n['group'] != 1000}
    anchors = set(group_of)
    metrics = {'anchors': group_of, 'snapshots': {}}

    for label in SNAPSHOTS:
        f = load(label)
        fol = collections.defaultdict(set)
        for s, ts in f.items():
            for t in ts:
                fol[t].add(s)
        nodes, h, a = hits(f)
        hub_s, auth_s = dict(zip(nodes, h)), dict(zip(nodes, a))

        friends = set(SEEDS)
        for s in SEEDS:
            friends |= set(f.get(s, []))

        leaves = set().union(*[fol[x] for x in anchors]) - anchors
        links = [{'source': s, 'target': t, 'value': 0} for s in leaves for t in f.get(s, []) if t in anchors]
        links += [{'source': s, 'target': t, 'value': 1} for s in anchors for t in f.get(s, []) if t in anchors]
        groups_followed = {s: {group_of[t] for t in f.get(s, []) if t in anchors} for s in leaves}
        bridges = {s for s, g in groups_followed.items() if len(g) >= 2}

        def node(i, g):
            n = {'id': i, 'group': g, 'auth': round(float(auth_s.get(i, 0)), 5), 'hub': round(float(hub_s.get(i, 0)), 5)}
            if i in bridges:
                n['bridge'] = True
            return n
        out_nodes = [node(i, group_of[i]) for i in sorted(anchors)] + [node(i, 1000) for i in sorted(leaves)]
        json.dump({'nodes': out_nodes, 'links': links, 'meta': {'snapshot': label, 'block': json.load(open(f'data/raw/follows_{label}.json'))['block']}},
                  open(f'data/trending_users_{label}.json', 'w'), separators=(',', ':'))

        # mixing metrics
        gsize = collections.Counter()
        for s in leaves:
            for g in groups_followed[s]:
                gsize[g] += 1
        cross = collections.Counter()  # leaves following group A and group B
        for s in leaves:
            gs = sorted(groups_followed[s])
            for i, x in enumerate(gs):
                for y in gs[i + 1:]:
                    cross[f'{x}-{y}'] += 1
        # isolated clusters (non-R accounts with many followers who follow nobody in R)
        isolated = []
        for x, fs in fol.items():
            if len(fs) >= MIN_FOLLOWERS and x not in friends:
                iso = sum(1 for u in fs if not (set(f.get(u, [])) & friends)) / len(fs)
                if iso >= MIN_ISOLATION:
                    isolated.append({'id': x, 'followers': len(fs), 'isolation': round(iso, 2), 'in_cohort': x in anchors})
        isolated.sort(key=lambda d: -d['followers'])
        metrics['snapshots'][label] = {
            'block': json.load(open(f'data/raw/follows_{label}.json'))['block'],
            'accounts_with_follows': len(f), 'follow_edges': sum(map(len, f.values())),
            'graph_nodes': len(out_nodes), 'graph_links': len(links), 'leaves': len(leaves),
            'bridge_leaves': len(bridges), 'bridge_share': round(len(bridges) / len(leaves), 4),
            'leaves_per_group': dict(gsize), 'leaves_following_both_groups': dict(cross),
            'root_userbase_size': len(friends), 'isolated_clusters': isolated,
        }
        print(label, 'nodes', len(out_nodes), 'links', len(links), 'bridges', len(bridges), f'({len(bridges) / len(leaves):.1%})')

    json.dump(metrics, open('data/metrics.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
