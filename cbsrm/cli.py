"""
CBSRM CLI — one-shot stress-index queries against public data.

Commands:
    cbsrm info
        Print package + indicator inventory.

    cbsrm latest STLFSI4
        Fetch the latest STLFSI4 value from FRED and print it.

    cbsrm ofr-fsi
        Fetch and print the latest OFR FSI composite + subindex breakdown.

    cbsrm ecb-ciss [--variant EA|US|UK]
        Fetch and print the latest ECB-published CISS value.

    cbsrm ciss-us [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--frequency w]
        End-to-end CISS-US compute:
          FRED → CISSUSBuilder → CISSUSCanonical → AuditedIndicator

    cbsrm replicate cbsrm-side canonical-side [...]
        Run replication diagnostics between two indicators.
        Currently supports: ciss-us vs (ofr-fsi | ecb-ciss-ea | ecb-ciss-us)

    cbsrm verify-audit --db PATH
        Re-hash the audit chain stored at PATH.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


# ─── Command handlers ────────────────────────────────────────────────


def cmd_info(_args: argparse.Namespace) -> int:
    from cbsrm import __version__
    print(json.dumps({
        "cbsrm_version": __version__,
        "indicators": [
            "STLFSI4", "OFR-FSI", "ECB-CISS-EA", "ECB-CISS-US", "ECB-CISS-UK",
            "CISS-US", "CISS-US-Canonical",
        ],
        "macro_indicators": [
            "YIELD-CURVE-US", "NFP-MOMENTUM-US", "FFR-CHANGE-US",
            "DXY-REGIME-US", "JPY-REGIME", "CPI-SURPRISE-US",
            "OIL-MACRO", "CREDIT-SPREAD-REGIME-US",
            "SAHM-RULE-US",
            "MACRO-COMPOSITE-US",
        ],
        "connectedness_indicators": ["DY-SPILLOVER"],
        "risk_modules": [
            "SRISK", "LRMES (Monte Carlo)", "Delta-CoVaR", "MES (empirical + Monte Carlo)",
        ],
        "supported_locales": ["en", "ja", "es", "fr", "de"],
        "data_sources": ["FRED", "OFR", "ECB", "BIS"],
        "builders": ["CISSUSBuilder"],
        "diagnostics": ["replicate", "crisis_windows"],
    }, indent=2))
    return 0


def cmd_latest(args: argparse.Namespace) -> int:
    from cbsrm.data import FREDClient
    from cbsrm.indicators import STLFSIWrap

    if args.indicator.upper() not in ("STLFSI4", "STLFSI"):
        print(f"`latest` command only supports STLFSI4; got {args.indicator}",
              file=sys.stderr)
        return 1

    client = FREDClient(api_key=args.api_key)
    df = client.get_multi(["STLFSI4"])
    if df.empty:
        print("FRED returned no data", file=sys.stderr); return 2
    result = STLFSIWrap().compute(df)
    if result.latest is None:
        print("no recent observations", file=sys.stderr); return 3
    ts, value = result.latest
    print(json.dumps({
        "indicator_id": result.indicator_id, "version": result.version,
        "as_of": ts.isoformat(), "value": value,
        "interpretation": result.metadata.get("interpretation"),
    }, indent=2))
    return 0


def cmd_ofr_fsi(args: argparse.Namespace) -> int:
    from cbsrm.data import OFRClient
    from cbsrm.indicators import OFRFSIWrap

    client = OFRClient(csv_url=args.csv_url)
    print(f"[ofr-fsi] fetching {client.csv_url}", file=sys.stderr)
    try:
        df = client.get_fsi()
    except Exception as e:
        print(f"[ofr-fsi] fetch failed: {e}", file=sys.stderr)
        return 1
    if df.empty:
        print("[ofr-fsi] no rows returned", file=sys.stderr); return 2

    result = OFRFSIWrap().compute(df)
    if result.latest is None:
        return 3
    ts, value = result.latest
    out: dict[str, Any] = {
        "indicator_id": result.indicator_id,
        "version": result.version,
        "as_of": ts.isoformat(), "value": value,
        "n_obs": int(result.values.size),
        "interpretation": result.metadata.get("interpretation"),
    }
    if args.verbose and result.subindex_values is not None:
        out["subindex_latest"] = result.subindex_values.iloc[-1].to_dict()
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_ecb_ciss(args: argparse.Namespace) -> int:
    from cbsrm.data import ECBSDMXClient
    from cbsrm.indicators import ECBCISSWrap

    variant = args.variant.upper()
    client = ECBSDMXClient()
    if variant == "EA":
        s = client.get_ciss_euro_area(start_period=args.start, end_period=args.end)
    elif variant == "US":
        s = client.get_ciss_us(start_period=args.start, end_period=args.end)
    elif variant == "UK":
        s = client.get_ciss_uk(start_period=args.start, end_period=args.end)
    else:
        print(f"unknown variant: {variant}", file=sys.stderr); return 1

    if s.empty:
        print("[ecb-ciss] no data returned", file=sys.stderr); return 2

    result = ECBCISSWrap(variant=variant).compute(s)
    if result.latest is None:
        return 3
    ts, value = result.latest
    print(json.dumps({
        "indicator_id": result.indicator_id, "version": result.version,
        "as_of": ts.isoformat(), "value": value,
        "n_obs": int(result.values.size),
        "interpretation": result.metadata.get("interpretation"),
    }, indent=2, default=str))
    return 0


def cmd_ciss_us(args: argparse.Namespace) -> int:
    from cbsrm.audit import AuditChain, AuditedIndicator
    from cbsrm.builders import CISSUSBuilder
    from cbsrm.data import FREDClient
    from cbsrm.indicators import CISSUSCanonical

    fred = FREDClient(api_key=args.api_key)
    builder = CISSUSBuilder(fred)
    print(
        f"[ciss-us] fetching {len(builder.required_fred_series())} FRED series "
        f"({args.start} → {args.end}, freq={args.frequency})…",
        file=sys.stderr,
    )
    df, manifest = builder.build(
        start=args.start, end=args.end, frequency=args.frequency,
    )
    if df.empty:
        print(f"[ciss-us] no usable rows. warnings: {manifest.warnings}", file=sys.stderr)
        return 1
    print(f"[ciss-us] built {len(df)} rows from {len(df.columns)} inputs "
          f"({manifest.n_substitutes()} substitutes)", file=sys.stderr)

    conn = sqlite3.connect(args.audit_db) if args.audit_db else sqlite3.connect(":memory:")
    audit = AuditChain(conn)
    indicator = AuditedIndicator(CISSUSCanonical(), audit, consumer="cli:ciss-us")
    result = indicator.compute(df)

    if result.latest is None:
        return 2
    ts, value = result.latest
    out: dict[str, Any] = {
        "indicator_id": result.indicator_id, "version": result.version,
        "as_of": ts.isoformat(), "value": value,
        "audit_row_id": result.audit_row_id,
        "n_obs": int(result.values.size),
        "manifest": manifest.as_dict(),
        "interpretation": result.metadata.get("interpretation"),
    }
    if args.verbose:
        out["subindex_latest"] = (
            result.subindex_values.iloc[-1].to_dict()
            if result.subindex_values is not None and not result.subindex_values.empty
            else {}
        )
    print(json.dumps(out, indent=2, default=str))
    return 0


def cmd_replicate(args: argparse.Namespace) -> int:
    """Run replication diagnostics between two indicators.

    Currently supports: ciss-us as cbsrm-side, vs (ofr-fsi, ecb-ciss-ea, ecb-ciss-us).
    """
    from cbsrm.builders import CISSUSBuilder
    from cbsrm.data import ECBSDMXClient, FREDClient, OFRClient
    from cbsrm.diagnostics import replicate
    from cbsrm.indicators import CISSUSCanonical, ECBCISSWrap, OFRFSIWrap

    pair = (args.cbsrm.lower(), args.canonical.lower())

    # cbsrm side: CISS-US
    if pair[0] != "ciss-us":
        print(f"v0.2 only supports cbsrm side = ciss-us; got {args.cbsrm}",
              file=sys.stderr)
        return 1

    print("[replicate] computing CISS-US-Canonical from FRED…", file=sys.stderr)
    fred = FREDClient(api_key=args.api_key)
    df, manifest = CISSUSBuilder(fred).build(
        start=args.start, end=args.end, frequency=args.frequency,
    )
    if df.empty:
        print(f"[replicate] CISS-US inputs empty. warnings: {manifest.warnings}",
              file=sys.stderr)
        return 2
    cbsrm_result = CISSUSCanonical().compute(df)
    cbsrm_series = cbsrm_result.values

    # canonical side
    if pair[1] == "ofr-fsi":
        print("[replicate] fetching OFR FSI…", file=sys.stderr)
        ofr_df = OFRClient(csv_url=args.csv_url).get_fsi()
        canon = OFRFSIWrap().compute(ofr_df).values
        canon_label = "OFR FSI"
    elif pair[1] in ("ecb-ciss-ea", "ecb-ciss-us", "ecb-ciss-uk"):
        variant = pair[1].rsplit("-", 1)[-1].upper()
        ecb = ECBSDMXClient()
        print(f"[replicate] fetching ECB CISS ({variant})…", file=sys.stderr)
        if variant == "EA":
            s = ecb.get_ciss_euro_area(start_period=args.start, end_period=args.end)
        elif variant == "US":
            s = ecb.get_ciss_us(start_period=args.start, end_period=args.end)
        else:
            s = ecb.get_ciss_uk(start_period=args.start, end_period=args.end)
        canon = ECBCISSWrap(variant=variant).compute(s).values
        canon_label = f"ECB CISS ({variant})"
    else:
        print(f"unknown canonical side: {args.canonical}", file=sys.stderr)
        return 1

    rep = replicate(cbsrm_series, canon,
                    cbsrm_label="CBSRM CISS-US-Canonical v0.1",
                    canonical_label=canon_label)

    if args.json:
        print(json.dumps(rep.as_dict(), indent=2, default=str))
    else:
        print(rep.summary())
        ok, breaches = rep.meets_threshold(
            full_sample_r=args.threshold_full,
            crisis_r=args.threshold_crisis,
        )
        print()
        if ok:
            print(f"✓ Meets replication thresholds "
                  f"(full ≥ {args.threshold_full}, crisis ≥ {args.threshold_crisis})")
        else:
            print(f"✗ Replication thresholds not met:")
            for b in breaches:
                print(f"  - {b}")
    return 0


def cmd_crisis_replay(args: argparse.Namespace) -> int:
    """Run the crisis-replay analyzer over canonical episode windows."""
    from cbsrm.data import ECBSDMXClient, OFRClient
    from cbsrm.diagnostics import (
        CrisisReplay, replay_to_markdown_dossier,
    )
    from cbsrm.indicators import ECBCISSWrap, OFRFSIWrap

    indicator_id = args.indicator.lower()

    if indicator_id == "ofr-fsi":
        df = OFRClient(csv_url=args.csv_url).get_fsi()
        result = OFRFSIWrap().compute(df)
    elif indicator_id in ("ecb-ciss-ea", "ecb-ciss-us", "ecb-ciss-uk"):
        variant = indicator_id.rsplit("-", 1)[-1].upper()
        ecb = ECBSDMXClient()
        if variant == "EA":
            s = ecb.get_ciss_euro_area(start_period=args.start, end_period=args.end)
        elif variant == "US":
            s = ecb.get_ciss_us(start_period=args.start, end_period=args.end)
        else:
            s = ecb.get_ciss_uk(start_period=args.start, end_period=args.end)
        result = ECBCISSWrap(variant=variant).compute(s)
    else:
        print(f"unknown indicator for crisis-replay: {args.indicator}. "
              f"Try: ofr-fsi | ecb-ciss-ea | ecb-ciss-us | ecb-ciss-uk",
              file=sys.stderr)
        return 1

    rp = CrisisReplay(
        values=result.values,
        subindex_values=result.subindex_values,
        indicator_id=result.indicator_id,
    )

    if args.window:
        report = rp.replay(args.window)
        if args.markdown:
            print(report.to_markdown())
        else:
            print(report.to_text())
            if args.json:
                print()
                print(json.dumps(report.as_dict(), indent=2, default=str))
    else:
        # Full dossier
        if args.markdown:
            print(replay_to_markdown_dossier(rp))
        else:
            from cbsrm.diagnostics import replay_all_windows
            reports = replay_all_windows(rp)
            print(f"# Crisis-replay summary — {rp.indicator_id}")
            print(f"# Date range: {rp.values.index.min().date()} → {rp.values.index.max().date()}")
            print(f"# Windows with overlap: {len(reports)}")
            print()
            for _name, r in reports.items():
                print(r.to_text())
    return 0


def _fred_macro_fetch(series_ids: list[str], api_key: str | None,
                      start: str | None, end: str | None,
                      frequency: str | None = None) -> "pd.DataFrame":
    """Helper: fetch one or more FRED series into a wide DataFrame for the
    macro indicators."""
    from cbsrm.data import FREDClient
    fred = FREDClient(api_key=api_key)
    kwargs: dict[str, Any] = {}
    if start:
        kwargs["observation_start"] = start
    if end:
        kwargs["observation_end"] = end
    if frequency:
        kwargs["frequency"] = frequency
    return fred.get_multi(series_ids, **kwargs)


def _emit_macro_result(result: Any, verbose: bool) -> None:
    ts, value = result.latest if result.latest is not None else (None, None)
    out: dict[str, Any] = {
        "indicator_id": result.indicator_id,
        "version": result.version,
        "as_of": ts.isoformat() if ts is not None else None,
        "value": value,
        "n_obs": int(result.values.size),
    }
    # Surface key metadata fields
    keys = (
        "regime", "classification",
        "latest_z_score", "latest_z", "latest_rate_pct",
        "latest_spread_pp", "latest_recession_prob_12mo",
        "latest_is_inverted", "latest_days_inverted_run",
        "latest_composite_change_bp", "latest_log_return_3m",
        "latest_regime", "latest_composite_score",
        "latest_sub_scores", "latest_override_triggers",
        "interpretation",
    )
    for k in keys:
        if k in result.metadata:
            out[k] = result.metadata[k]
    if verbose and result.subindex_values is not None and not result.subindex_values.empty:
        out["subindex_latest"] = result.subindex_values.iloc[-1].to_dict()
    print(json.dumps(out, indent=2, default=str))


def cmd_yield_curve(args: argparse.Namespace) -> int:
    from cbsrm.macro import YieldCurveIndicator
    df = _fred_macro_fetch(["T10Y3M"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "T10Y3M" not in df.columns:
        print("[yield-curve] no T10Y3M data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(YieldCurveIndicator().compute(df), args.verbose)
    return 0


def cmd_nfp_momentum(args: argparse.Namespace) -> int:
    from cbsrm.macro import NFPMomentumIndicator
    df = _fred_macro_fetch(["PAYEMS"], args.api_key, args.start, args.end, frequency="m")
    if df.empty or "PAYEMS" not in df.columns:
        print("[nfp-momentum] no PAYEMS data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(NFPMomentumIndicator().compute(df), args.verbose)
    return 0


def cmd_ffr_change(args: argparse.Namespace) -> int:
    from cbsrm.macro import FFRChangeIndicator
    df = _fred_macro_fetch(["DFF"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "DFF" not in df.columns:
        print("[ffr-change] no DFF data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(FFRChangeIndicator().compute(df), args.verbose)
    return 0


def cmd_dxy_regime(args: argparse.Namespace) -> int:
    from cbsrm.macro import DXYRegimeIndicator
    df = _fred_macro_fetch(["DTWEXBGS"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "DTWEXBGS" not in df.columns:
        print("[dxy-regime] no DTWEXBGS data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(DXYRegimeIndicator().compute(df), args.verbose)
    return 0


def cmd_jpy_regime(args: argparse.Namespace) -> int:
    from cbsrm.macro import JPYRegimeIndicator
    df = _fred_macro_fetch(["DEXJPUS"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "DEXJPUS" not in df.columns:
        print("[jpy-regime] no DEXJPUS data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(JPYRegimeIndicator().compute(df), args.verbose)
    return 0


def cmd_cpi_surprise(args: argparse.Namespace) -> int:
    from cbsrm.macro import CPISurpriseIndicator
    df = _fred_macro_fetch(["CPIAUCSL"], args.api_key, args.start, args.end, frequency="m")
    if df.empty or "CPIAUCSL" not in df.columns:
        print("[cpi-surprise] no CPIAUCSL data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(CPISurpriseIndicator().compute(df), args.verbose)
    return 0


def cmd_oil_macro(args: argparse.Namespace) -> int:
    from cbsrm.macro import OilMacroIndicator
    df = _fred_macro_fetch(["DCOILWTICO"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "DCOILWTICO" not in df.columns:
        print("[oil-macro] no DCOILWTICO data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(OilMacroIndicator().compute(df), args.verbose)
    return 0


def cmd_credit_spread(args: argparse.Namespace) -> int:
    from cbsrm.macro import CreditSpreadRegimeIndicator
    df = _fred_macro_fetch(["BAMLH0A0HYM2"], args.api_key, args.start, args.end, frequency="d")
    if df.empty or "BAMLH0A0HYM2" not in df.columns:
        print("[credit-spread] no BAMLH0A0HYM2 data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(CreditSpreadRegimeIndicator().compute(df), args.verbose)
    return 0


def cmd_delta_covar(args: argparse.Namespace) -> int:
    """Compute ΔCoVaR from a JSON input file.

    Input JSON schema:
        {
            "firm": "JPM",
            "firm_returns": [r1, r2, ...],
            "system_returns": [r1, r2, ...],
            "q": 0.05  (optional, default 0.05),
            "state_vars": [[m1_t1, m2_t1], [m1_t2, m2_t2], ...]  (optional)
        }
    """
    from cbsrm.risk import DeltaCoVaREstimator
    import json as _json
    raw = _json.loads(Path(args.input).read_text(encoding="utf-8"))
    q = float(raw.get("q", 0.05))
    estimator = DeltaCoVaREstimator(q=q)
    import numpy as _np
    state = None
    if "state_vars" in raw and raw["state_vars"] is not None:
        state = _np.asarray(raw["state_vars"], dtype=float)
    res = estimator.estimate(
        firm=str(raw.get("firm", "firm")),
        firm_returns=_np.asarray(raw["firm_returns"], dtype=float),
        system_returns=_np.asarray(raw["system_returns"], dtype=float),
        state_vars=state,
        metadata=raw.get("metadata"),
    )
    print(_json.dumps(res.__dict__, indent=2, default=str))
    return 0


def cmd_mes(args: argparse.Namespace) -> int:
    """Compute empirical MES from a JSON input file.

    Input JSON schema:
        {
            "firm": "JPM",
            "firm_returns": [...],
            "market_returns": [...],
            "q": 0.05
        }
    """
    from cbsrm.risk import empirical_mes
    import json as _json
    raw = _json.loads(Path(args.input).read_text(encoding="utf-8"))
    import numpy as _np
    res = empirical_mes(
        firm_returns=_np.asarray(raw["firm_returns"], dtype=float),
        market_returns=_np.asarray(raw["market_returns"], dtype=float),
        q=float(raw.get("q", 0.05)),
        firm=str(raw.get("firm", "firm")),
        metadata=raw.get("metadata"),
    )
    print(_json.dumps(res.__dict__, indent=2, default=str))
    return 0


def cmd_sahm_rule(args: argparse.Namespace) -> int:
    from cbsrm.macro import SahmRuleIndicator
    df = _fred_macro_fetch(["UNRATE"], args.api_key, args.start, args.end, frequency="m")
    if df.empty or "UNRATE" not in df.columns:
        print("[sahm-rule] no UNRATE data from FRED", file=sys.stderr)
        return 1
    _emit_macro_result(SahmRuleIndicator().compute(df), args.verbose)
    return 0


def cmd_dy_spillover(args: argparse.Namespace) -> int:
    """Compute Diebold-Yilmaz total spillover from a panel.

    Default: 4-sector US equity ETFs (XLF / XLK / XLE / XLU) via Stooq
    (no API key needed). Operator can pass --input JSON with their own
    return panel.
    """
    from cbsrm.indicators import DYSpilloverIndicator
    import json as _json
    import urllib.request as _ur
    import pandas as pd
    import numpy as np
    if args.input:
        raw = _json.loads(Path(args.input).read_text(encoding="utf-8"))
        df = pd.DataFrame(raw)
    else:
        tickers = (args.tickers or "XLF,XLK,XLE,XLU").split(",")
        # Try Stooq daily close as the default free source
        cols = {}
        for t in tickers:
            t = t.strip()
            url = f"https://stooq.com/q/d/l/?s={t.lower()}.us&i=d"
            try:
                with _ur.urlopen(url, timeout=30) as r:
                    data = pd.read_csv(r)
                if "Close" in data.columns and "Date" in data.columns:
                    cols[t] = pd.Series(
                        data["Close"].values,
                        index=pd.to_datetime(data["Date"]),
                    )
            except Exception as e:
                print(f"[dy-spillover] failed to fetch {t}: {e}", file=sys.stderr)
        if not cols:
            print("[dy-spillover] no data fetched; pass --input JSON instead",
                  file=sys.stderr)
            return 1
        df = pd.DataFrame(cols).dropna(how="any")
        # Convert prices to log returns
        df = np.log(df).diff().dropna()
    res = DYSpilloverIndicator().compute(df)
    _emit_macro_result(res, args.verbose)
    return 0


def cmd_bis_otc(args: argparse.Namespace) -> int:
    from cbsrm.data import BISStatsClient
    from cbsrm.indicators import BISOTCDerivativesIndicator
    client = BISStatsClient()
    print("[bis-otc] fetching OTC derivatives notional from BIS...", file=sys.stderr)
    try:
        df = client.get_otc_derivatives_notional(start_period=args.start)
    except Exception as e:
        print(f"[bis-otc] fetch failed: {e}", file=sys.stderr)
        return 1
    if df.empty:
        print("[bis-otc] no rows returned (BIS may have rotated the key)", file=sys.stderr)
        return 2
    result = BISOTCDerivativesIndicator().compute(df)
    if result.latest is None:
        return 3
    ts, value = result.latest
    print(json.dumps({
        "indicator_id": result.indicator_id, "version": result.version,
        "as_of": str(ts), "value": value,
        "n_obs": int(result.values.size),
        "interpretation": result.metadata.get("interpretation"),
    }, indent=2, default=str))
    return 0


def cmd_bis_cbs(args: argparse.Namespace) -> int:
    from cbsrm.data import BISStatsClient
    from cbsrm.indicators import BISCBSClaimsIndicator
    client = BISStatsClient()
    print("[bis-cbs] fetching consolidated banking statistics from BIS...", file=sys.stderr)
    try:
        df = client.get_consolidated_banking_claims(start_period=args.start)
    except Exception as e:
        print(f"[bis-cbs] fetch failed: {e}", file=sys.stderr)
        return 1
    if df.empty:
        print("[bis-cbs] no rows returned (BIS may have rotated the key)", file=sys.stderr)
        return 2
    result = BISCBSClaimsIndicator().compute(df)
    if result.latest is None:
        return 3
    ts, value = result.latest
    print(json.dumps({
        "indicator_id": result.indicator_id, "version": result.version,
        "as_of": str(ts), "value": value,
        "n_obs": int(result.values.size),
        "interpretation": result.metadata.get("interpretation"),
    }, indent=2, default=str))
    return 0


def cmd_srisk(args: argparse.Namespace) -> int:
    """Compute SRISK for a hand-supplied panel of firms.

    Inputs come from a JSON file (--input PATH) containing a list of dicts
    with keys: firm, market_cap_W, book_debt_D, lrmes. Optional: metadata.
    """
    from cbsrm.risk import srisk_panel
    import json as _json
    raw = _json.loads(Path(args.input).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        print("[srisk] --input file must contain a JSON list of firm dicts",
              file=sys.stderr)
        return 1
    out = srisk_panel(raw, k=args.k)
    print(_json.dumps(out, indent=2, default=str))
    return 0


def cmd_macro_regime(args: argparse.Namespace) -> int:
    """Compute the 4-state composite macro regime end-to-end."""
    import pandas as pd
    from cbsrm.macro import MacroCompositeIndicator

    # The four sub-indicators want different frequencies. PAYEMS is monthly,
    # the others are daily. Fetch separately then align via outer join +
    # forward-fill of the monthly series.
    df_daily = _fred_macro_fetch(
        ["T10Y3M", "DFF", "DTWEXBGS"], args.api_key, args.start, args.end, frequency="d",
    )
    df_monthly = _fred_macro_fetch(
        ["PAYEMS"], args.api_key, args.start, args.end, frequency="m",
    )
    if df_daily.empty or df_monthly.empty:
        print("[macro-regime] empty FRED response on one or more series",
              file=sys.stderr)
        return 1
    # Align monthly PAYEMS onto the daily grid via forward-fill
    payems_aligned = df_monthly["PAYEMS"].reindex(df_daily.index, method="ffill")
    df = df_daily.copy()
    df["PAYEMS"] = payems_aligned
    df = df.dropna(how="any")
    if df.empty:
        print("[macro-regime] no overlapping observations", file=sys.stderr)
        return 2
    _emit_macro_result(MacroCompositeIndicator().compute(df), args.verbose)
    return 0


def cmd_verify_audit(args: argparse.Namespace) -> int:
    from cbsrm.audit import AuditChain
    conn = sqlite3.connect(args.db)
    audit = AuditChain(conn)
    ok, broken = audit.verify()
    print(json.dumps({"chain_ok": ok, "broken_row_ids": broken}, indent=2))
    return 0 if ok else 3


def cmd_crisis_dossier(args: argparse.Namespace) -> int:
    """Export a deterministic crisis-window dossier as JSON, Markdown, or HTML.

    Pure, offline, side-effect-free. Composes
    `cbsrm.diagnostics.build_crisis_dossier` with the
    `cbsrm.reporting` renderer; does not duplicate any methodology.
    """
    from cbsrm.diagnostics import build_crisis_dossier, list_dossier_windows
    from cbsrm.reporting import build_report_payload, render_dossier_markdown

    supported = list_dossier_windows()
    if args.window not in supported:
        print(
            f"error: unknown crisis-dossier window '{args.window}'. "
            f"Supported windows: {', '.join(supported)}.",
            file=sys.stderr,
        )
        return 2

    try:
        dossier = build_crisis_dossier(args.window)
    except ValueError as exc:
        # Defence in depth — list_dossier_windows() above should have caught
        # this, but if the registry shape ever changes, fail clean here too.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Compute the canonical output text for each format BEFORE writing
    # stdout, so the same bytes can be hashed into the optional manifest
    # without re-rendering. `payload` stays None for non-JSON formats;
    # `build_report_manifest` only records `payload_sha256` when the
    # payload is supplied.
    title_prefix = getattr(args, "title_prefix", None)
    payload: dict | None = None

    if args.format == "markdown":
        output_text = render_dossier_markdown(dossier, title_prefix=title_prefix)
    elif args.format == "html":
        # Lazy import — the HTML renderer depends on the optional
        # `markdown` extra. Surfacing the import here keeps `cbsrm`
        # importable and the json/markdown formats usable without it.
        from cbsrm.reporting import render_dossier_html

        output_text = render_dossier_html(dossier, title_prefix=title_prefix)
    else:  # "json" (default)
        payload = build_report_payload(dossier)
        # ensure_ascii=False keeps em-dashes / arrows readable; UTF-8-safe
        # stdout handles the encoding even on Windows cp1252 consoles.
        output_text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    _write_stdout_utf8_safe(output_text)

    # Build the manifest once if either side-effect (file write,
    # audit-chain stamping) was requested. Reusing the same dict
    # guarantees the manifest file and the audit row describe
    # bit-identical bytes.
    manifest_path = getattr(args, "manifest", None)
    audit_db_path = getattr(args, "audit_db", None)
    store_db_path = getattr(args, "store_db", None)
    manifest: dict | None = None
    if (
        manifest_path is not None
        or audit_db_path is not None
        or store_db_path is not None
    ):
        from cbsrm.reporting import build_report_manifest

        manifest = build_report_manifest(
            report_id="crisis-dossier",
            output_text=output_text,
            output_format=args.format,
            window_id=args.window,
            source="cli",
            dossier=dossier,
            payload=payload,
        )

    if manifest_path is not None:
        assert manifest is not None  # for type checkers
        Path(manifest_path).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if audit_db_path is not None:
        assert manifest is not None  # for type checkers
        from cbsrm.reporting import stamp_manifest_to_db_path

        # The shared path-based helper opens the sqlite connection,
        # wraps it in AuditChain, stamps, and closes the connection
        # in a try/finally — same behaviour the CLI did inline before,
        # now matched bit-for-bit by the Streamlit sidebar path.
        try:
            audit_row = stamp_manifest_to_db_path(manifest, audit_db_path)
        except sqlite3.OperationalError as exc:
            print(
                f"error: cannot open audit db '{audit_db_path}': {exc}",
                file=sys.stderr,
            )
            return 2

        # One concise stderr line so the operator can locate the row
        # later via `cbsrm verify-audit --db PATH` or by querying the
        # subject through the API's /audit/{subject} surface. Stdout
        # is reserved for the report bytes.
        print(
            f"audit: row_id={audit_row['row_id']} "
            f"subject={audit_row['subject']} "
            f"hash={audit_row['hash']}",
            file=sys.stderr,
        )

    if store_db_path is not None:
        assert manifest is not None  # for type checkers
        from cbsrm.reporting import store_report_artifact

        try:
            stored = store_report_artifact(
                store_db_path,
                output_text=output_text,
                manifest=manifest,
            )
        except sqlite3.OperationalError as exc:
            print(
                f"error: cannot open report store '{store_db_path}': {exc}",
                file=sys.stderr,
            )
            return 2

        # Same convention as the audit-db line: one concise stderr
        # record so the operator can correlate stored bytes with
        # downstream audit rows and API lookups. Stdout is reserved
        # for the report itself.
        print(
            f"stored: output_sha256={stored['output_sha256']} "
            f"was_existing={stored['was_existing']} "
            f"db={store_db_path}",
            file=sys.stderr,
        )

    return 0


def cmd_macro_composite(args: argparse.Namespace) -> int:
    """Export a deterministic macro-composite snapshot as JSON or Markdown.

    First-cut CLI front-end for the v0.9 macro-composite report. Pure
    pass-through over :func:`cbsrm.reporting.build_macro_composite_report`
    and :func:`cbsrm.reporting.render_macro_composite_markdown` — the
    builder is offline, fixture-backed, and deterministic, so this
    command never touches the network or writes to disk. Manifest /
    audit / store / API / Streamlit wiring for this report is
    intentionally deferred to follow-up slices.
    """
    from cbsrm.reporting import (
        build_macro_composite_report,
        list_macro_composite_windows,
        render_macro_composite_markdown,
    )

    try:
        report = build_macro_composite_report(args.window)
    except ValueError:
        supported = ", ".join(list_macro_composite_windows())
        print(
            f"error: unknown macro-composite window '{args.window}'. "
            f"Supported windows: {supported}.",
            file=sys.stderr,
        )
        return 2

    if args.format == "markdown":
        output_text = render_macro_composite_markdown(report)
    else:
        output_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    _write_stdout_utf8_safe(output_text)
    return 0


def cmd_reports(_args: argparse.Namespace) -> int:
    """Print the deterministic report registry catalog as JSON.

    Pure pass-through over :func:`cbsrm.reporting.get_report_catalog`.
    The command is metadata-only — it never executes a report, never
    touches the network, and never writes to disk. Mirrors the
    ``GET /reports`` HTTP endpoint for CLI/API parity.
    """
    from cbsrm.reporting import get_report_catalog

    catalog = get_report_catalog()
    # Match the formatting convention of ``crisis-dossier --format json``
    # above: indent=2, ensure_ascii=False, UTF-8-safe stdout. The catalog
    # is plain ASCII today, but mirroring keeps the surface uniform if a
    # future entry carries non-ASCII (e.g. en-dashes in titles).
    _write_stdout_utf8_safe(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"
    )
    return 0


def _write_stdout_utf8_safe(text: str) -> None:
    """Write `text` to stdout as UTF-8 even on Windows cp1252 consoles.

    Falls back to a best-effort text write (with ``errors='replace'``) when
    a binary buffer is unavailable (e.g. some pytest capsys variants), so
    the CLI never aborts on non-ASCII rendered content like ``→`` or em-dashes.
    """
    buf = getattr(sys.stdout, "buffer", None)
    if buf is not None:
        buf.write(text.encode("utf-8"))
        try:
            sys.stdout.flush()
        except Exception:
            pass
        return
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        # Last-resort fallback: replace unencodable chars so the command
        # still produces well-formed output rather than crashing.
        encoding = getattr(sys.stdout, "encoding", "ascii") or "ascii"
        sys.stdout.write(text.encode(encoding, errors="replace").decode(encoding))


# ─── Argparse wiring ─────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cbsrm",
                                description="Cross-Border Systemic Risk Monitor CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Service info").set_defaults(func=cmd_info)

    p_latest = sub.add_parser("latest", help="Latest value of one indicator")
    p_latest.add_argument("indicator")
    p_latest.add_argument("--api-key", help="FRED API key (or env FRED_API_KEY)")
    p_latest.set_defaults(func=cmd_latest)

    p_ofr = sub.add_parser("ofr-fsi", help="Latest OFR FSI composite")
    p_ofr.add_argument("--csv-url", help="Override OFR FSI CSV URL")
    p_ofr.add_argument("-v", "--verbose", action="store_true")
    p_ofr.set_defaults(func=cmd_ofr_fsi)

    p_ecb = sub.add_parser("ecb-ciss", help="Latest ECB-published CISS value")
    p_ecb.add_argument("--variant", default="EA", choices=["EA", "US", "UK"])
    p_ecb.add_argument("--start", help="Start period (YYYY-MM-DD)")
    p_ecb.add_argument("--end", help="End period (YYYY-MM-DD)")
    p_ecb.set_defaults(func=cmd_ecb_ciss)

    p_ciss = sub.add_parser("ciss-us", help="Compute CISS-US end-to-end from FRED")
    p_ciss.add_argument("--start"); p_ciss.add_argument("--end")
    p_ciss.add_argument("--frequency", default="w")
    p_ciss.add_argument("--api-key")
    p_ciss.add_argument("--audit-db")
    p_ciss.add_argument("-v", "--verbose", action="store_true")
    p_ciss.set_defaults(func=cmd_ciss_us)

    p_rep = sub.add_parser("replicate",
                            help="Run replication diagnostics between two indicators")
    p_rep.add_argument("cbsrm", help="CBSRM-side indicator (currently: ciss-us)")
    p_rep.add_argument("canonical",
                        help="Canonical-side indicator: ofr-fsi | ecb-ciss-ea | ecb-ciss-us | ecb-ciss-uk")
    p_rep.add_argument("--start", default="2010-01-01")
    p_rep.add_argument("--end")
    p_rep.add_argument("--frequency", default="w")
    p_rep.add_argument("--api-key")
    p_rep.add_argument("--csv-url", help="Override OFR FSI CSV URL")
    p_rep.add_argument("--threshold-full", type=float, default=0.80,
                        help="Pearson r threshold for full sample (default 0.80)")
    p_rep.add_argument("--threshold-crisis", type=float, default=0.75,
                        help="Pearson r threshold for crisis windows (default 0.75)")
    p_rep.add_argument("--json", action="store_true")
    p_rep.set_defaults(func=cmd_replicate)

    p_cr = sub.add_parser("crisis-replay",
                           help="Run crisis-window analyzer over an indicator")
    p_cr.add_argument("indicator",
                       help="ofr-fsi | ecb-ciss-ea | ecb-ciss-us | ecb-ciss-uk")
    p_cr.add_argument("--window",
                       help="One canonical window (e.g. 2020-covid); default = all overlapping")
    p_cr.add_argument("--start"); p_cr.add_argument("--end")
    p_cr.add_argument("--csv-url", help="Override OFR FSI CSV URL")
    p_cr.add_argument("--markdown", action="store_true",
                       help="Render full markdown dossier (paper-ready)")
    p_cr.add_argument("--json", action="store_true")
    p_cr.set_defaults(func=cmd_crisis_replay)

    # ─── Macro Engine (v0.3) ─────────────────────────────────────────
    p_yc = sub.add_parser("yield-curve",
                          help="Yield-curve inversion + Estrella-Mishkin recession probability")
    p_yc.add_argument("--start"); p_yc.add_argument("--end")
    p_yc.add_argument("--api-key", help="FRED API key (or env FRED_API_KEY)")
    p_yc.add_argument("-v", "--verbose", action="store_true")
    p_yc.set_defaults(func=cmd_yield_curve)

    p_nfp = sub.add_parser("nfp-momentum",
                           help="Non-farm payrolls MoM-growth rolling z-score")
    p_nfp.add_argument("--start"); p_nfp.add_argument("--end")
    p_nfp.add_argument("--api-key")
    p_nfp.add_argument("-v", "--verbose", action="store_true")
    p_nfp.set_defaults(func=cmd_nfp_momentum)

    p_ffr = sub.add_parser("ffr-change",
                           help="Effective federal funds rate 3M/6M/12M change momentum")
    p_ffr.add_argument("--start"); p_ffr.add_argument("--end")
    p_ffr.add_argument("--api-key")
    p_ffr.add_argument("-v", "--verbose", action="store_true")
    p_ffr.set_defaults(func=cmd_ffr_change)

    p_dxy = sub.add_parser("dxy-regime",
                           help="Broad trade-weighted USD index trend regime")
    p_dxy.add_argument("--start"); p_dxy.add_argument("--end")
    p_dxy.add_argument("--api-key")
    p_dxy.add_argument("-v", "--verbose", action="store_true")
    p_dxy.set_defaults(func=cmd_dxy_regime)

    p_jpy = sub.add_parser("jpy-regime",
                           help="USD/JPY trend regime (Japan / safe-haven currency)")
    p_jpy.add_argument("--start"); p_jpy.add_argument("--end")
    p_jpy.add_argument("--api-key")
    p_jpy.add_argument("-v", "--verbose", action="store_true")
    p_jpy.set_defaults(func=cmd_jpy_regime)

    p_cpi = sub.add_parser("cpi-surprise",
                           help="YoY CPI inflation rolling z-score (momentum proxy)")
    p_cpi.add_argument("--start"); p_cpi.add_argument("--end")
    p_cpi.add_argument("--api-key")
    p_cpi.add_argument("-v", "--verbose", action="store_true")
    p_cpi.set_defaults(func=cmd_cpi_surprise)

    p_oil = sub.add_parser("oil-macro",
                           help="WTI crude-oil macroeconomic regime")
    p_oil.add_argument("--start"); p_oil.add_argument("--end")
    p_oil.add_argument("--api-key")
    p_oil.add_argument("-v", "--verbose", action="store_true")
    p_oil.set_defaults(func=cmd_oil_macro)

    p_credit = sub.add_parser("credit-spread",
                              help="ICE BofA US HY OAS regime classifier")
    p_credit.add_argument("--start"); p_credit.add_argument("--end")
    p_credit.add_argument("--api-key")
    p_credit.add_argument("-v", "--verbose", action="store_true")
    p_credit.set_defaults(func=cmd_credit_spread)

    p_sahm = sub.add_parser("sahm-rule",
                            help="Sahm Rule real-time recession indicator")
    p_sahm.add_argument("--start"); p_sahm.add_argument("--end")
    p_sahm.add_argument("--api-key")
    p_sahm.add_argument("-v", "--verbose", action="store_true")
    p_sahm.set_defaults(func=cmd_sahm_rule)

    p_dy = sub.add_parser("dy-spillover",
                          help="Diebold-Yilmaz total spillover index (Pesaran-Shin GFEVD)")
    p_dy.add_argument("--tickers",
                      help="Comma-separated ticker list (default XLF,XLK,XLE,XLU)")
    p_dy.add_argument("--input",
                      help="Optional JSON path with pre-computed returns panel")
    p_dy.add_argument("-v", "--verbose", action="store_true")
    p_dy.set_defaults(func=cmd_dy_spillover)

    p_bis_otc = sub.add_parser("bis-otc",
                               help="BIS OTC derivatives notional outstanding (semi-annual)")
    p_bis_otc.add_argument("--start", help="Start period (e.g. 2010)")
    p_bis_otc.set_defaults(func=cmd_bis_otc)

    p_bis_cbs = sub.add_parser("bis-cbs",
                               help="BIS consolidated banking statistics — cross-border claims (quarterly)")
    p_bis_cbs.add_argument("--start", help="Start period (e.g. 2010-Q1)")
    p_bis_cbs.set_defaults(func=cmd_bis_cbs)

    p_srisk = sub.add_parser("srisk",
                             help="Compute SRISK for a JSON panel of firms")
    p_srisk.add_argument("--input", required=True,
                         help="Path to JSON file with list of firm dicts "
                              "(firm, market_cap_W, book_debt_D, lrmes)")
    p_srisk.add_argument("--k", type=float, default=0.08,
                         help="Prudential capital ratio (default 0.08)")
    p_srisk.set_defaults(func=cmd_srisk)

    p_dcv = sub.add_parser("delta-covar",
                           help="Compute Delta-CoVaR for a firm vs system "
                                "(Adrian-Brunnermeier 2016)")
    p_dcv.add_argument("--input", required=True,
                       help="JSON path with firm, firm_returns, system_returns, q")
    p_dcv.set_defaults(func=cmd_delta_covar)

    p_mes = sub.add_parser("mes",
                           help="Empirical Marginal Expected Shortfall "
                                "(Acharya-Pedersen-Philippon-Richardson 2017)")
    p_mes.add_argument("--input", required=True,
                       help="JSON path with firm, firm_returns, market_returns, q")
    p_mes.set_defaults(func=cmd_mes)

    p_macro = sub.add_parser("macro-regime",
                             help="4-state macro composite (RISK_ON / TRANSITION / RISK_OFF)")
    p_macro.add_argument("--start"); p_macro.add_argument("--end")
    p_macro.add_argument("--api-key")
    p_macro.add_argument("-v", "--verbose", action="store_true")
    p_macro.set_defaults(func=cmd_macro_regime)

    p_verify = sub.add_parser("verify-audit")
    p_verify.add_argument("--db", required=True)
    p_verify.set_defaults(func=cmd_verify_audit)

    # ─── v0.8 reporting export ──────────────────────────────────────
    p_cd = sub.add_parser(
        "crisis-dossier",
        help="Export a deterministic crisis-window dossier (JSON or Markdown)",
    )
    p_cd.add_argument(
        "window",
        help="Crisis-window id (e.g. 2008Q4 / 2020Q1 / 2023Q1). "
             "Run with an unsupported value to see the full supported list.",
    )
    p_cd.add_argument(
        "--format", default="json", choices=["json", "markdown", "html"],
        help="Output format (default: json)",
    )
    p_cd.add_argument(
        "--title-prefix", default=None,
        help="Optional prefix prepended to the report title "
             "(applies to markdown and html formats; ignored for json)",
    )
    p_cd.add_argument(
        "--manifest", default=None, metavar="PATH",
        help="Optional path to write the deterministic export-time "
             "manifest JSON. Stdout report output is unchanged.",
    )
    p_cd.add_argument(
        "--audit-db", default=None, metavar="PATH",
        help="Optional path to a sqlite audit-chain DB. When supplied, "
             "the export manifest is appended as one REPORT_EXPORTED "
             "row and a one-line audit record is printed to stderr. "
             "The DB file is created if it does not exist. Stdout "
             "report output is unchanged.",
    )
    p_cd.add_argument(
        "--store-db", default=None, metavar="PATH",
        help="Optional path to a sqlite report-artifact store. When "
             "supplied, the rendered report text plus its manifest are "
             "persisted content-addressed by output_sha256 (INSERT OR "
             "IGNORE on collision). One stderr record is printed: "
             "`stored: output_sha256=<hash> was_existing=<bool> "
             "db=<path>`. The DB file is created if it does not exist. "
             "Stdout report output is unchanged.",
    )
    p_cd.set_defaults(func=cmd_crisis_dossier)

    # ─── v0.9 macro-composite report (CLI exposure, first cut) ──────
    from cbsrm.reporting import (
        list_macro_composite_windows as _list_mc_windows,
    )

    p_mc = sub.add_parser(
        "macro-composite",
        help="Export a deterministic macro-composite snapshot (JSON or Markdown)",
        description=(
            "Export the v0.9 macro-composite report (phase-classifier-only "
            "first cut) for one canonical window. Output is deterministic "
            "and offline; this command does not touch the network or write "
            "to disk. Manifest / audit / store / API / Streamlit wiring "
            "for this report is deferred to follow-up slices."
        ),
    )
    p_mc.add_argument(
        "window",
        choices=_list_mc_windows(),
        help="Macro-composite window id. Supported: 2008Q4 / 2020Q1 / 2023Q1.",
    )
    p_mc.add_argument(
        "--format", default="json", choices=["json", "markdown"],
        help="Output format (default: json)",
    )
    p_mc.set_defaults(func=cmd_macro_composite)

    # ─── v0.9 report registry catalog ───────────────────────────────
    sub.add_parser(
        "reports",
        help="Print the deterministic report catalog as JSON "
             "(metadata only; no report is executed)",
        description=(
            "Print the deterministic report registry catalog as JSON. "
            "Metadata-only: this command does not execute any report, "
            "make network calls, or write to disk. Mirrors the "
            "`GET /reports` HTTP endpoint for CLI/API parity."
        ),
    ).set_defaults(func=cmd_reports)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
