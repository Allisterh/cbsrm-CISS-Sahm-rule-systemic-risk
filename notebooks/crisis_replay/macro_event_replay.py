"""
Macro-event crisis-replay walkthrough — runnable script.
=========================================================

This script demonstrates ``cbsrm.diagnostics.macro_replay.replay_macro_events``
end-to-end using the deterministic fixtures shipped under
``notebooks/crisis_replay/fixtures/``. No network, no external data.

Run from repo root::

    python notebooks/crisis_replay/macro_event_replay.py

Operator can convert this into a Jupyter notebook with::

    jupytext --to notebook notebooks/crisis_replay/macro_event_replay.py

Sections
--------

1. Load fixtures (events.csv + prices.csv)
2. Score + window each event/series via replay_macro_events
3. Aggregate: average post-event reaction by direction bucket
4. Aggregate: average post-event reaction by severity bucket
5. Print a leaderboard of the largest |post_return| reactions

All numerical aggregations are *demonstrative*. The fixtures are
synthetic; the conclusions are illustrative of the API, not empirical
findings.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
REPO_ROOT = HERE.parent.parent

# Self-bootstrap import path so the script runs from anywhere without
# requiring `pip install -e .` of the cbsrm package.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from cbsrm.diagnostics.macro_replay import replay_macro_events  # noqa: E402


def load_fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(FIXTURES / "events.csv")
    prices = pd.read_csv(FIXTURES / "prices.csv", index_col="date", parse_dates=True)
    return events, prices


def main() -> None:
    print("=" * 72)
    print("  Macro-event crisis-replay walkthrough  (fixtures-only, no network)")
    print("=" * 72)

    events, prices = load_fixtures()
    print(f"\n[1] Loaded {len(events)} events across "
          f"{events['event'].nunique()} unique macro prints.")
    print(f"    Price panel: {prices.shape[0]} rows × "
          f"{prices.shape[1]} series ({list(prices.columns)})")

    report = replay_macro_events(
        events_df=events,
        prices_df=prices,
        pre_window_days=5,
        post_window_days=5,
    )

    print(f"\n[2] Replay returned {len(report)} long-form rows.")
    print(report.head(8).to_string(index=False))

    print("\n[3] Average post_return by direction × price_series:")
    by_dir = (
        report.groupby(["direction", "price_series"])["post_return"]
        .mean()
        .unstack()
    )
    print(by_dir.round(5).to_string())

    print("\n[4] Average post_return by severity × price_series:")
    by_sev = (
        report.groupby(["severity", "price_series"])["post_return"]
        .mean()
        .unstack()
    )
    print(by_sev.round(5).to_string())

    print("\n[5] Top 6 largest |post_return| reactions:")
    top = report.assign(abs_post=lambda d: d["post_return"].abs()).nlargest(
        6, "abs_post"
    )[["date", "event", "direction", "severity", "price_series", "post_return"]]
    print(top.to_string(index=False))

    print("\nDone.")


if __name__ == "__main__":
    main()
