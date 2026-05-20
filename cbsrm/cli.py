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
            "DXY-REGIME-US", "JPY-REGIME", "MACRO-COMPOSITE-US",
        ],
        "supported_locales": ["en", "ja", "es", "fr", "de"],
        "data_sources": ["FRED", "OFR", "ECB"],
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

    p_macro = sub.add_parser("macro-regime",
                             help="4-state macro composite (RISK_ON / TRANSITION / RISK_OFF)")
    p_macro.add_argument("--start"); p_macro.add_argument("--end")
    p_macro.add_argument("--api-key")
    p_macro.add_argument("-v", "--verbose", action="store_true")
    p_macro.set_defaults(func=cmd_macro_regime)

    p_verify = sub.add_parser("verify-audit")
    p_verify.add_argument("--db", required=True)
    p_verify.set_defaults(func=cmd_verify_audit)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
