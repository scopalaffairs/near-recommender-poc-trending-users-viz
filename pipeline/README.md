# Pipeline: NEAR Social follow graph -> trending_users.json

Raw data is read from the public NEAR blockchain: contract `social.near`, method `get`
with keys `["<account>/graph/follow/*"]`, called against an archival RPC at a fixed block height.

Run from the repo root (`python3 pipeline/snap2.py`); paths are relative to it.

1. Account list (accounts that have follow keys today, a superset of the past; not committed, ~6 MB):
   `curl -s https://api.near.social/keys -H 'content-type: application/json' -d '{"keys":["*/graph/follow/*"],"options":{"return_type":"True"}}' -o data/follow_keys_now.json`
2. `findblk.py`: block height for a date (binary search over block timestamps).
3. `snap2.py` + `socialdb.py`: snapshot per block height into `data/raw/follows_<date>.json`
   (`{block, label, follows: {account: [followed, ...]}}`). Throttled and resumable, because the RPC rate-limits (HTTP 429).
4. `hits.py`: Kleinberg HITS (hub and authority scores) on the follow graph.

Snapshots: 2023-04-15 (before), 2023-10-31 (shortly before recommender launch), 2024-01-15 (after).
Limitation: the account list is from today, so accounts that have since removed all follows are missing.

## Cascade and outputs

`python3 pipeline/cascade.py` (needs numpy) turns each snapshot into `data/trending_users_<date>.json`
(same schema as `trending_users.json`, plus per node `auth`/`hub` = HITS scores and `bridge: true` for
accounts following anchors of two or more communities) and writes `data/metrics.json`.

The anchor cohort (20 hubs and their community groups) is taken from the original `trending_users.json`
and held fixed over all snapshots, so before/after compare the same accounts. The original hub selection
rule is not recoverable: it is not HITS rank, in-degree or recent follower growth (checked against the
2023-04-15 graph); `scopalaffairs.near` with 4 followers shows it was partly hand-picked. Reproduction check
for 2023-04-15 against the original file: 96 % of nodes, 93 % of edges.

`metrics.json` also lists isolated clusters per snapshot (non-root-userbase accounts with >= 25 followers
who follow nobody in the root userbase). These are not part of the cohort graphs, so clusters that only
appeared later (e.g. creativesdao, nearchinese, nearinturkiye in Oct 2023) are visible there but not in the viz.
