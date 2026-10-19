# NEAR Social: trending users before and after the recommender

An interactive 3D map of the [NEAR Social](https://near.social) follow network around its "trending users",
rebuilt from the public blockchain at three points in time, plus a weekly timeline of how the network grew.

- Graph: https://near-recommender-poc-trending-users-viz.vercel.app/
- Timeline: https://near-recommender-poc-trending-users-viz.vercel.app/timeline.html

| 2023-04-15, before the recommender | 2024-01-15, after the recommender |
|---|---|
| ![Graph on 2023-04-15](docs/images/viz-2023-04-15.jpg) | ![Graph on 2024-01-15](docs/images/viz-2024-01-15.jpg) |

Each dot is an account, each line a follow. Colors are communities, big dots are the 20 hub accounts (sized by
HITS authority), and gold dots are *bridge accounts* that follow hubs of two or more communities.

## Background

NEAR Social was a social network whose posts, likes and follows were written to the NEAR blockchain (contract
`social.near`). In 2023 a team built a recommender for it as the capstone project of the Constructor Data Science
Bootcamp (batch 03/2023), in collaboration with Pagoda, the company behind the NEAR Blockchain Operating System. The
original code is in [scopalaffairs/near_recommender](https://github.com/scopalaffairs/near_recommender). It ran four
algorithms: top trending users, friends of friends, tag similarity and post similarity.

The problem the trending-users part addressed: the network had a few large, mostly isolated clusters. The clearest
one was a "mushroom" of accounts that had joined through the Aurora network and followed only the Aurora news
account. These clusters did not know each other or the core userbase around `root.near` and `mob.near`. The
recommender suggested trending users from a *different* community than the user's own, so that clusters would meet.

According to the project author, the timeline was: research in spring 2023 (Google Colab, later Databricks), the
recommender went live around November 2023 (about the time of NEARCon in Lisbon), and the near.org platform, relaunched
in August 2023, was shut down in March 2024.

### How `trending_users.json` was made originally

Taken from the original code (`src/models/trending_users.py`, `src/data/queries/query_user_metrics.py`):

1. Follow edges come from the parsed `social.near` transactions (`graph_follows`).
2. Communities: Louvain community detection on the undirected follow graph (cdlib, resolution 1).
3. Per user, over the last 30 days: *engagement* = comments + likers + followers, *activity* = posts + likes +
   followings, each weighted 1 / 0.5 / 0.1.
4. `trending_metric = weighted engagement / weighted activity`. The top 20 users are the trending users.

`trending_users.json` is consistent with this: 20 hub accounts (the group IDs are community IDs) plus 1,676 followers
of those hubs, with the edges between them. It is the original, unchanged dataset from spring 2023 and is the first
entry in the graph's switcher.

## What this repository adds

The pipeline that produced the original data is lost, and the recommender had no control group. So the data was
rebuilt from the chain itself:

1. **Snapshots** of the whole follow graph on 2023-04-15, 2023-10-31 and 2024-01-15 (`data/raw/`), read from an
   archival NEAR RPC node at fixed block heights.
2. **A fixed cohort**: the 20 hubs of the original file, held constant over all snapshots, so before and after
   compare the same accounts. Their followers are the leaves.
3. **HITS scores** (hub and authority) for every account and **bridge accounts** per snapshot (`data/trending_users_*.json`).
4. **A weekly timeline** of new follows into the cohort and of bridge events, from the block height at which each
   follow was written (`data/timeline.json`).

How well does it reproduce the original? On 2023-04-15, 96 % of the original nodes and 93 % of its edges match
(the rest are accounts that unfollowed, and accounts that followed afterwards). Louvain communities on the 2023-04-15
graph put the Aurora hubs together, the JumpDeFi/Neko hubs together and most root-userbase hubs together,
as the original groups do; the small NDC/Mintbase and NEARxART groups merge differently. Louvain is not
deterministic, and the original ran on a different data base, so exact IDs differ.

## What the data shows

Descriptive only. There was no control group, so none of this proves or disproves an effect of the recommender.

| | 2023-04-15 | 2023-10-31 | 2024-01-15 |
|---|---|---|---|
| nodes in the cohort graph | 1,728 | 2,422 | 2,518 |
| bridge accounts (follow ≥ 2 communities) | 140 (8.2 %) | 314 (13.1 %) | 333 (13.3 %) |

- **The clusters merged before the recommender existed, not after.** The bridge share rose from April to October
  2023 and then stayed flat to January 2024.
- **Growth peaked in spring 2023 and faded.** The weekly new follows into the hubs peaked at 408 in the week of
  2023-02-27 (the Aurora campaign) and were at 20 to 50 per week by autumn.
- **No visible bump at the launch.** In the eight weeks before the launch the hubs gained 29.8 new follows per week
  on average, in the eight weeks after 17.0. New bridge events: 3.4 versus 2.0 per week.
- **Conversion did not rise.** Of the accounts that followed only Aurora hubs, 0.42 % per month also followed another
  community between April and October 2023, and 0.30 % per month between October and January.
- **The Aurora cluster stayed a mushroom.** 92 % of its followers followed no other community in April 2023, 88 % in
  January 2024.
- **Almost nobody unfollowed.** Less than 0.3 % of follow edges disappeared between snapshots. Writing to the chain
  cost money, which plausibly kept casual activity down.

## Limitations

- **No control group, no causal claim.** Between April 2023 and January 2024 there were also the near.org relaunch,
  NEARCon and general network growth and decline. The launch date is approximate.
- **The cohort is fixed on purpose**, so it cannot show clusters that appeared later. `data/metrics.json` lists
  isolated clusters per snapshot, e.g. `creativesdao.sputnik-dao.near`, `nearchinese.near` and `nearinturkiye.near`
  in October 2023.
- **The original hub selection is not recomputed.** The trending metric needs the history of posts, likes and
  comments. SocialDB keeps only the latest value per key, so this history is not available from archival state and
  would need transaction data (for example NEAR Lake or the public BigQuery dataset).
- **Only follow edges still present are seen.** The account list comes from today's follow keys
  (`api.near.social`), so accounts that have since removed every follow are missing.
- **Block heights to dates** are interpolated between blocks with exactly known timestamps (error of a few days).

## Repository layout

| Path | Content |
|---|---|
| `index.html` | 3D graph (three.js via 3d-force-graph, all CDN versions pinned) with a snapshot switcher |
| `timeline.html` | weekly follows and bridge events, plain SVG, light and dark theme, table view |
| `trending_users.json` | the original dataset from spring 2023 |
| `data/raw/follows_<date>.json` | follow graph snapshots: `{block, label, follows: {account: [followed, ...]}}` |
| `data/trending_users_<date>.json` | cohort graph per snapshot (nodes carry HITS `auth` / `hub`, and `bridge`) |
| `data/metrics.json` | mixing metrics and isolated clusters per snapshot |
| `data/timeline.json`, `data/edges_bh_2024-01-15.json` | weekly series and the follow creation block heights behind it |
| `pipeline/` | the scripts, see [pipeline/README.md](pipeline/README.md) |

To run it locally: `python3 -m http.server`, then open http://localhost:8000. To regenerate the derived data from the
snapshots: `python3 pipeline/cascade.py` and `python3 pipeline/timeline.py` (needs numpy).

## License

GPL-3.0, like the original [near_recommender](https://github.com/scopalaffairs/near_recommender). See [LICENSE](LICENSE).
