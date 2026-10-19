"""Did the recommender change who gained followers? Difference-in-differences against a control group.

Treated: the 20 hubs of the original trending list (the accounts a "trending users" recommendation would push).
Control: the 20 largest accounts outside that list on 2023-04-15, not recommended by that rule.
Outcome: new followers per week (from the block height at which each follow was written).
Statistic: ratio of the weekly average after the launch to the average before it, treated divided by control.
The same test is repeated for possible dates of the near.org platform relaunch ("August 2023", exact day unknown),
together with the weekly number of new accounts (accounts whose first follow falls into the week).
A ratio above 1 means the hubs gained relative to the control; the same statistic is computed for placebo
launch dates to show how large the ratio is by chance. Needs data/edges_bh_2024-01-15.json; run from the repo root.
"""
import collections
import datetime
import json
import math
import random
import sys

sys.path.insert(0, 'pipeline')
from evaluate import to_block  # noqa: E402
from timeline import LAUNCH, to_date  # noqa: E402

WEEKS = 8
FIRST_WEEK_DAYS = 7


def week_index(day):
    return (day - datetime.date(2023, 1, 2)).days // 7


def main():
    base = json.load(open('trending_users.json'))
    hubs = sorted(n['id'] for n in base['nodes'] if n['group'] != 1000)
    edges = json.load(open('data/edges_bh_2024-01-15.json'))['edges']

    followers = collections.defaultdict(list)  # account -> [(week index, date)]
    first_seen = {}
    follows_of = collections.defaultdict(list)
    for s, targets in edges.items():
        for t, block in targets.items():
            d = to_date(block)
            followers[t].append((week_index(d), d))
            follows_of[s].append((d, t))
    for s, items in follows_of.items():
        items.sort()
        first_seen[s] = items[0][0]

    in_apr = collections.Counter({t: sum(1 for w, d in fs if d <= datetime.date(2023, 4, 15)) for t, fs in followers.items()})
    controls = [a for a, _ in in_apr.most_common(80) if a not in hubs][:20]
    n_weeks = week_index(datetime.date(2024, 1, 15)) + 1

    def series(accounts):
        out = [[0] * n_weeks for _ in accounts]
        for i, a in enumerate(accounts):
            for w, _ in followers[a]:
                if 0 <= w < n_weeks:
                    out[i][w] += 1
        return out

    treated, control = series(hubs), series(controls)
    launch = week_index(datetime.date.fromisoformat(LAUNCH))

    def ratio(groups, at, weeks=WEEKS):
        pre = sum(sum(g[at - weeks:at]) for g in groups)
        post = sum(sum(g[at:at + weeks]) for g in groups)
        return post / pre if pre else float('nan')

    def did(at, weeks=WEEKS, idx=None):
        t = [treated[i] for i in (idx[0] if idx else range(len(treated)))]
        c = [control[i] for i in (idx[1] if idx else range(len(control)))]
        return ratio(t, at, weeks) / ratio(c, at, weeks)

    rng = random.Random(1)
    boots = []
    for _ in range(2000):
        idx = ([rng.randrange(20) for _ in range(20)], [rng.randrange(20) for _ in range(20)])
        v = did(launch, idx=idx)
        if not math.isnan(v) and v > 0:
            boots.append(math.log(v))
    boots.sort()
    lo, hi = math.exp(boots[int(.025 * len(boots))]), math.exp(boots[int(.975 * len(boots))])

    placebo = {}
    for at in range(WEEKS, launch - WEEKS + 1):  # fake launch dates whose windows end before the real one
        placebo[at] = did(at)
    real = did(launch)
    rank = sum(1 for v in placebo.values() if v <= real) / len(placebo)

    placebo_by_week = {(datetime.date(2023, 1, 2) + datetime.timedelta(weeks=at)).isoformat(): round(v, 2) for at, v in placebo.items()}
    summary = {
        'launch': LAUNCH, 'weeks': WEEKS,
        'hubs': {'accounts': len(hubs), 'before': sum(sum(g[launch - WEEKS:launch]) for g in treated), 'after': sum(sum(g[launch:launch + WEEKS]) for g in treated)},
        'control': {'accounts': controls, 'before': sum(sum(g[launch - WEEKS:launch]) for g in control), 'after': sum(sum(g[launch:launch + WEEKS]) for g in control)},
        'ratio_hubs': round(ratio(treated, launch), 3), 'ratio_control': round(ratio(control, launch), 3),
        'did': round(real, 3), 'did_ci95': [round(lo, 3), round(hi, 3)],
        'placebo': {'n': len(placebo), 'median': round(sorted(placebo.values())[len(placebo) // 2], 3),
                    'min': round(min(placebo.values()), 3), 'max': round(max(placebo.values()), 3), 'share_below_real': round(rank, 3)},
        'robustness': {str(w): round(did(launch, w), 3) for w in (4, 6, 8, 10)},
    }

    # newcomers: accounts whose first follow falls into a week; what share of their first-week follows hit the hubs / controls
    hubset, ctrlset = set(hubs), set(controls)
    weekly = collections.defaultdict(lambda: {'n': 0, 'hub': 0, 'control': 0})
    for s, items in follows_of.items():
        d0 = items[0][0]
        if d0 < datetime.date(2023, 3, 1):
            continue  # accounts that already existed when the series starts are not newcomers
        first_week = {t for d, t in items if (d - d0).days < FIRST_WEEK_DAYS}
        row = weekly[week_index(d0)]
        row['n'] += 1
        row['hub'] += bool(first_week & hubset)
        row['control'] += bool(first_week & ctrlset)
    new_pre = [weekly[w] for w in range(launch - WEEKS, launch)]
    new_post = [weekly[w] for w in range(launch, launch + WEEKS)]

    def share(rows, key):
        n = sum(r['n'] for r in rows)
        return sum(r[key] for r in rows) / n if n else float('nan'), n

    summary['newcomers'] = {k: {'before': round(share(new_pre, k)[0], 4), 'after': round(share(new_post, k)[0], 4)} for k in ('hub', 'control')}
    summary['newcomers']['count'] = {'before': share(new_pre, 'hub')[1], 'after': share(new_post, 'hub')[1]}

    # conversion: accounts that follow only one community (as of a date) and later follow another one, per month
    group = {n['id']: n['group'] for n in base['nodes'] if n['group'] != 1000}
    to_block_fn = lambda day: to_block(day)

    def groups_at(block):
        g = collections.defaultdict(set)
        for s, targets in edges.items():
            if s in group:
                continue
            for t, b in targets.items():
                if t in group and b <= block:
                    g[s].add(group[t])
        return g

    def conversion(start, end, months, community=0):
        b0, b1 = to_block_fn(start), to_block_fn(end)
        g0, g1 = groups_at(b0), groups_at(b1)
        only = [u for u, gs in g0.items() if gs == {community}]
        moved = sum(1 for u in only if g1.get(u, {community}) - {community})
        return {'accounts': len(only), 'moved': moved, 'per_month': round(moved / len(only) / months * 100, 3) if only else None}

    months_pre = (datetime.date.fromisoformat(LAUNCH) - datetime.date(2023, 4, 15)).days / 30.44
    months_post = (datetime.date(2024, 1, 15) - datetime.date.fromisoformat(LAUNCH)).days / 30.44
    summary['conversion_aurora_to_other'] = {
        'before': conversion('2023-04-15', LAUNCH, months_pre), 'after': conversion(LAUNCH, '2024-01-15', months_post)}

    # second event: the platform relaunch, "August 2023" (exact day unknown). The same test is run for each Monday in
    # August; the window is shortened so that the "after" period ends before the recommender launch.
    def new_accounts_per_week(first, last):
        return sum(1 for d0 in first_seen.values() if first <= week_index(d0) < last) / max(1, last - first)

    platform = []
    for day in ('2023-08-07', '2023-08-14', '2023-08-21', '2023-08-28'):
        at = week_index(datetime.date.fromisoformat(day))
        w = min(WEEKS, launch - at)
        boots_p = []
        rng_p = random.Random(2)
        for _ in range(2000):
            idx = ([rng_p.randrange(20) for _ in range(20)], [rng_p.randrange(20) for _ in range(20)])
            v = did(at, w, idx)
            if not math.isnan(v) and v > 0:
                boots_p.append(math.log(v))
        boots_p.sort()
        platform.append({
            'date': day, 'weeks': w,
            'hubs': [sum(sum(g[at - w:at]) for g in treated), sum(sum(g[at:at + w]) for g in treated)],
            'control': [sum(sum(g[at - w:at]) for g in control), sum(sum(g[at:at + w]) for g in control)],
            'did': round(did(at, w), 3),
            'did_ci95': [round(math.exp(boots_p[int(.025 * len(boots_p))]), 3), round(math.exp(boots_p[int(.975 * len(boots_p))]), 3)],
            'new_accounts_per_week': [round(new_accounts_per_week(at - w, at), 1), round(new_accounts_per_week(at, at + w), 1)],
        })
    summary['platform_relaunch'] = platform
    summary['new_accounts_per_week_recommender'] = [round(new_accounts_per_week(launch - WEEKS, launch), 1), round(new_accounts_per_week(launch, launch + WEEKS), 1)]

    out = {'summary': summary, 'placebo_by_week': placebo_by_week, 'weeks': [
        {'week': (datetime.date(2023, 1, 2) + datetime.timedelta(weeks=w)).isoformat(),
         'hubs': sum(g[w] for g in treated), 'control': sum(g[w] for g in control),
         'new_accounts': sum(1 for d0 in first_seen.values() if week_index(d0) == w)}
        for w in range(n_weeks)]}
    json.dump(out, open('data/impact.json', 'w'), separators=(',', ':'))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
