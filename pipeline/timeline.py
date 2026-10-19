"""Weekly time series of new follow edges into the anchor cohort and of bridge events.

Needs data/edges_bh_<date>.json (edge creation block heights, from the newest snapshot) and the
anchor cohort from trending_users.json. Run from the repo root.
Block -> date is interpolated linearly between blocks whose timestamps were looked up exactly.
Survivorship: only edges still present in the newest snapshot are seen; unfollows were < 0.5 %.
"""
import collections
import datetime
import json
import sys

ANCHORS = [(88469695, '2023-03-31'), (89599925, '2023-04-15'), (104573607, '2023-10-31'), (110424804, '2024-01-15')]
LAUNCH = '2023-10-02'  # recommender launch, "early October 2023" per the author; exact day unknown
NAME = {0: 'Aurora', 1: 'Root-Userbase', 4: 'Mintbase/NDC', 5: 'JumpDeFi/Neko', 9: 'NEARxART'}


def to_date(block):
    pts = [(b, datetime.date.fromisoformat(d).toordinal()) for b, d in ANCHORS]
    lo, hi = (pts[0], pts[1]) if block < pts[1][0] else (pts[1], pts[2]) if block < pts[2][0] else (pts[2], pts[3])
    return datetime.date.fromordinal(round(lo[1] + (block - lo[0]) / (hi[0] - lo[0]) * (hi[1] - lo[1])))


def week(d):
    return (d - datetime.timedelta(days=d.weekday())).isoformat()


def main(label):
    base = json.load(open('trending_users.json'))
    group = {n['id']: n['group'] for n in base['nodes'] if n['group'] != 1000}
    edges = json.load(open(f'data/edges_bh_{label}.json'))['edges']
    first = collections.defaultdict(dict)  # follower -> {group: earliest date of an edge into that group}
    new_edges = collections.defaultdict(collections.Counter)  # week -> group -> count
    for s, targets in edges.items():
        if s in group:
            continue
        for t, block in targets.items():
            if t in group:
                d = to_date(block)
                new_edges[week(d)][group[t]] += 1
                g = group[t]
                if g not in first[s] or d < first[s][g]:
                    first[s][g] = d
    bridge_events = collections.Counter()
    for s, gd in first.items():
        if len(gd) >= 2:
            bridge_events[week(sorted(gd.values())[1])] += 1
    weeks = sorted(set(new_edges) | set(bridge_events))
    weeks = [w for w in weeks if '2023-01-01' <= w <= '2024-01-15']
    out = {'launch': LAUNCH, 'names': NAME, 'weeks': [
        {'week': w, 'edges': {NAME[g]: new_edges[w][g] for g in NAME}, 'total': sum(new_edges[w].values()), 'bridge_events': bridge_events[w]}
        for w in weeks]}
    json.dump(out, open('data/timeline.json', 'w'), separators=(',', ':'))
    return out


if __name__ == '__main__':
    out = main(sys.argv[1] if len(sys.argv) > 1 else '2024-01-15')
    print(f"{'week':12}{'total':>6}{'Aurora':>7}{'Root':>6}{'Mint/NDC':>9}{'Jump':>6}{'bridge':>7}")
    for w in out['weeks']:
        e = w['edges']
        print(f"{w['week']:12}{w['total']:>6}{e['Aurora']:>7}{e['Root-Userbase']:>6}{e['Mintbase/NDC']:>9}{e['JumpDeFi/Neko']:>6}{w['bridge_events']:>7}" + ('  <-- Launch-Woche' if w['week'] <= LAUNCH < (datetime.date.fromisoformat(w['week']) + datetime.timedelta(days=7)).isoformat() else ''))
