"""
Macro-event replay — surprise score + windowed price reaction.
=====================================================================

This module composes :func:`cbsrm.macro.macro_events.score_event` with a
windowed log-return computation on a price panel, producing a long-form
DataFrame that pairs each scored macro release with the price reaction
of every series in a caller-supplied panel.

Where ``crisis_replay.py`` analyses the *indicator's own time series*
inside a crisis window, this module analyses *external asset prices*
around a discrete macro event. The two are complements:

  - crisis_replay  →  "how did the stress index behave during GFC?"
  - macro_replay   →  "how did SPY / TLT move around the May 2024 CPI?"

The function is intentionally pure: no I/O, no network, no caching. The
caller provides both the event calendar (``events_df``) and the price
panel (``prices_df``). Suitable for back-testing, dashboard tiles, and
SSRN-quality figures.

Schema
------

``events_df`` must contain columns::

    event       — str, one of macro_events.list_supported_events()
    date        — parseable to pd.Timestamp (the *release* date)
    actual      — float
    consensus   — float

Optional columns: ``previous``, ``unit``.

``prices_df`` is a wide-form price panel: rows indexed by date, columns
are price series names (e.g. ``SPY``, ``TLT``).

``replay_macro_events()`` returns a long-form DataFrame, one row per
(event, price_series), with the score fields and the windowed log-return
columns ``pre_return`` and ``post_return``::

    event, date, actual, consensus, surprise, surprise_z,
    direction, severity, risk_bias, price_series,
    pre_return, post_return

A ``pre_return`` is the log return from the bar ``pre_window_days``
before the event to the bar at/just-before the event. A ``post_return``
is the log return from the bar at/just-before the event to the bar
``post_window_days`` after. Both use the as-of-or-prior price for the
event-date anchor so that an event landing on a weekend / holiday still
gets a deterministic reading.

Design notes
------------

* Both windows are calendar-day windows on the price index, not strict
  trading-day counts. This keeps the API simple and broker-agnostic; if
  the caller wants strict B-day counts they can reindex ``prices_df``
  to business days before calling.
* ``surprise`` is signed: ``actual - consensus``. ``surprise_z`` is the
  per-event z-score from the scorer. ``direction`` and ``risk_bias``
  come straight from the scorer.
* Missing price coverage for a given event/series yields ``NaN`` in
  ``pre_return``/``post_return``; the row is *still* emitted so the
  caller can see the gap.
"""
from __future__ import annotations

from typing import Iterable

import math

import numpy as np
import pandas as pd

from cbsrm.macro.macro_events import score_event


_REQUIRED_EVENT_COLS = ("event", "date", "actual", "consensus")


def _coerce_event_date(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts


def _ensure_prices_index(prices_df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices_df.index, pd.DatetimeIndex):
        new_index = pd.to_datetime(prices_df.index, errors="raise")
    else:
        new_index = prices_df.index
    if new_index.tz is not None:
        new_index = new_index.tz_convert("UTC").tz_localize(None)
    out = prices_df.copy()
    out.index = new_index
    return out.sort_index()


def _asof_price(series: pd.Series, when: pd.Timestamp) -> float | None:
    """Return the value of ``series`` at or just-before ``when``.

    Returns ``None`` if no such observation exists.
    """
    # series is already sorted ascending
    idx = series.index.searchsorted(when, side="right") - 1
    if idx < 0:
        return None
    val = series.iloc[idx]
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return float(val)


def _log_return(p0: float | None, p1: float | None) -> float:
    if p0 is None or p1 is None:
        return float("nan")
    if p0 <= 0 or p1 <= 0:
        return float("nan")
    return math.log(p1 / p0)


def replay_macro_events(
    events_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    pre_window_days: int = 5,
    post_window_days: int = 5,
) -> pd.DataFrame:
    """Score macro events and join with windowed price returns.

    Parameters
    ----------
    events_df :
        Macro-release calendar. Must contain columns
        ``event``, ``date``, ``actual``, ``consensus``.
        Optional: ``previous``, ``unit``.
    prices_df :
        Wide-form price panel. Index is dates; columns are price
        series names. Each cell is a level (close price).
    pre_window_days, post_window_days :
        Calendar-day window widths for pre/post-event log returns.
        Must be positive integers.

    Returns
    -------
    pd.DataFrame
        Long-form. One row per (event_row × price_series). Columns::

            event, date, actual, consensus, surprise, surprise_z,
            direction, severity, risk_bias, price_series,
            pre_return, post_return

    Raises
    ------
    ValueError
        If a required column is missing, the inputs are empty, or
        either window is non-positive.
    """
    if not isinstance(events_df, pd.DataFrame):
        raise ValueError("events_df must be a pandas DataFrame")
    if not isinstance(prices_df, pd.DataFrame):
        raise ValueError("prices_df must be a pandas DataFrame")

    if events_df.empty:
        raise ValueError("events_df is empty; nothing to replay")
    if prices_df.empty:
        raise ValueError("prices_df is empty; cannot compute returns")

    missing = [c for c in _REQUIRED_EVENT_COLS if c not in events_df.columns]
    if missing:
        raise ValueError(
            f"events_df is missing required column(s): {missing}. "
            f"Required: {list(_REQUIRED_EVENT_COLS)}"
        )

    if not isinstance(pre_window_days, int) or pre_window_days <= 0:
        raise ValueError(
            f"pre_window_days must be a positive int, got {pre_window_days!r}"
        )
    if not isinstance(post_window_days, int) or post_window_days <= 0:
        raise ValueError(
            f"post_window_days must be a positive int, got {post_window_days!r}"
        )

    prices_df = _ensure_prices_index(prices_df)
    price_series_names = list(prices_df.columns)
    if not price_series_names:
        raise ValueError("prices_df has no price series columns")

    rows: list[dict] = []

    for _, ev in events_df.iterrows():
        event_name = str(ev["event"])
        try:
            event_date = _coerce_event_date(ev["date"])
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"events_df row has unparseable date {ev['date']!r}: {exc}"
            ) from exc

        previous = ev["previous"] if "previous" in events_df.columns else None
        if previous is not None and isinstance(previous, float) and math.isnan(previous):
            previous = None
        unit = ev["unit"] if "unit" in events_df.columns else None
        if isinstance(unit, float) and math.isnan(unit):
            unit = None

        try:
            scored = score_event(
                event=event_name,
                actual=float(ev["actual"]),
                consensus=float(ev["consensus"]),
                previous=float(previous) if previous is not None else None,
                unit=unit if unit is None else str(unit),
            )
        except ValueError:
            # Unknown event or non-finite numerics — surface, don't silently skip.
            raise

        pre_anchor = event_date - pd.Timedelta(days=pre_window_days)
        post_anchor = event_date + pd.Timedelta(days=post_window_days)

        for series_name in price_series_names:
            series = prices_df[series_name].dropna()
            p_pre = _asof_price(series, pre_anchor)
            p_at = _asof_price(series, event_date)
            p_post = _asof_price(series, post_anchor)

            pre_ret = _log_return(p_pre, p_at)
            post_ret = _log_return(p_at, p_post)

            rows.append({
                "event": scored["event"],
                "date": event_date,
                "actual": scored["actual"],
                "consensus": scored["consensus"],
                "surprise": scored["surprise"],
                "surprise_z": scored["surprise_z"],
                "direction": scored["direction"],
                "severity": scored["severity"],
                "risk_bias": scored["risk_bias"],
                "price_series": series_name,
                "pre_return": pre_ret,
                "post_return": post_ret,
            })

    columns = [
        "event", "date", "actual", "consensus",
        "surprise", "surprise_z", "direction", "severity", "risk_bias",
        "price_series", "pre_return", "post_return",
    ]
    out = pd.DataFrame(rows, columns=columns)
    return out


__all__ = ["replay_macro_events"]
