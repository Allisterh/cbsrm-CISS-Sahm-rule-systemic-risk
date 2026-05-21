"""
CISSUSBuilder — turn FRED time series into a CISSUS-ready 15-column matrix.
============================================================================

The CISSUS indicator class is methodology-only: it accepts a 15-column
DataFrame and computes the composite. This builder bridges from raw FRED
series to that input matrix, applying the canonical US substitution
mapping (whitepaper §3.2) and the standard derived-series transforms:

  - SPREAD     : two-series subtraction       (e.g. SOFR − IORB)
  - CMAX       : rolling-window max drawdown  (e.g. S&P 500 CMAX 60w)
  - REALVOL    : rolling-window realized vol  (e.g. KBW Bank 60d)
  - ABS        : absolute value               (e.g. |10Y−2Y|)
  - DAILY_VOL  : rolling vol of daily returns (e.g. DTWEXBGS vol)

Where a canonical input cannot be sourced from FRED alone (e.g. cross-currency
basis swaps, SLOOS diffusion), the builder marks the column as a SUBSTITUTE
in its manifest. Operators can override the mapping with their own series
via `CISSUSBuilderConfig.overrides`.

USAGE
-----

    from cbsrm.data import FREDClient
    from cbsrm.builders import CISSUSBuilder
    from cbsrm.indicators import CISSUS

    builder = CISSUSBuilder(FREDClient(api_key="..."))
    df, manifest = builder.build(start="2010-01-01", frequency="w")

    indicator = CISSUS()
    result = indicator.compute(df)

The manifest documents exactly which FRED series fed each of the 15 inputs,
which were derived vs. raw, and which used a substitute. This is essential
for the audit trail: the indicator value's interpretation depends on the
manifest, not just the value.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger("cbsrm.builders.ciss_us")


# ─── Canonical 15-input specification ─────────────────────────────────


# Each input is specified by:
#   name      — column name in the output DataFrame
#   subindex  — which of the 5 CISS subindices it belongs to
#   recipe    — how to compute it from FRED inputs
#   fred_ids  — FRED mnemonics it depends on (for logging + manifest)
#   substitute_for — name of the canonical input being substituted (if not exact)
#
# Where a canonical input requires non-FRED data (e.g. basis swaps, SLOOS),
# the recipe falls back to a documented substitute and the manifest records
# the substitution.


@dataclass(frozen=True)
class InputSpec:
    name: str
    subindex: str
    recipe: str             # 'PASSTHROUGH' | 'SPREAD' | 'ABS' | 'CMAX' | 'REALVOL' | 'DAILY_VOL'
    fred_ids: tuple[str, ...]
    notes: str = ""
    is_substitute: bool = False
    substitute_for: str | None = None
    # Recipe parameters
    cmax_window: int | None = None
    realvol_window: int | None = None


CANONICAL_SPECS: tuple[InputSpec, ...] = (
    # ─── Money market ─────────────────────────────────────────────────
    InputSpec(
        name="money_market_1",
        subindex="money_market",
        recipe="PASSTHROUGH",
        fred_ids=("TEDRATE",),
        notes="TED spread (3M LIBOR − 3M T-Bill). Historical; LIBOR discontinued 2023.",
        is_substitute=True,
        substitute_for="3M-LIBOR-3M-TBill spread (post-LIBOR successor)",
    ),
    InputSpec(
        name="money_market_2",
        subindex="money_market",
        recipe="SPREAD",
        fred_ids=("SOFR", "IORB"),
        notes="SOFR − IORB spread. Reserve-supply funding-stress proxy.",
    ),
    InputSpec(
        name="money_market_3",
        subindex="money_market",
        recipe="PASSTHROUGH",
        fred_ids=("BAMLC0A0CM",),
        notes="ICE BofA US Corporate Index OAS — short-end credit stress proxy.",
        is_substitute=True,
        substitute_for="3M Commercial Paper − 3M T-Bill spread",
    ),

    # ─── Bond market ──────────────────────────────────────────────────
    InputSpec(
        name="bond_market_1",
        subindex="bond_market",
        recipe="ABS",
        fred_ids=("T10Y2Y",),
        notes="Absolute 10Y−2Y spread (curve dislocation magnitude).",
    ),
    InputSpec(
        name="bond_market_2",
        subindex="bond_market",
        recipe="PASSTHROUGH",
        fred_ids=("BAMLH0A0HYM2",),
        notes="ICE BofA US High-Yield OAS — credit stress.",
    ),
    InputSpec(
        name="bond_market_3",
        subindex="bond_market",
        recipe="REALVOL",
        fred_ids=("DGS10",),
        realvol_window=60,
        notes="60-day realized vol of 10Y Treasury yield (rate-vol proxy for MOVE).",
        is_substitute=True,
        substitute_for="MOVE Index",
    ),

    # ─── Equity market ────────────────────────────────────────────────
    InputSpec(
        name="equity_market_1",
        subindex="equity_market",
        recipe="PASSTHROUGH",
        fred_ids=("VIXCLS",),
        notes="VIX close.",
    ),
    InputSpec(
        name="equity_market_2",
        subindex="equity_market",
        recipe="CMAX",
        fred_ids=("SP500",),
        cmax_window=60,
        notes="S&P 500 CMAX over 60-day window (rolling max-drawdown).",
    ),
    InputSpec(
        name="equity_market_3",
        subindex="equity_market",
        recipe="REALVOL",
        fred_ids=("SP500",),
        realvol_window=20,
        notes="20-day realized vol of S&P 500 (intermediate-horizon vol stress).",
        is_substitute=True,
        substitute_for="S&P 500 financials beta",
    ),

    # ─── Financial intermediaries ─────────────────────────────────────
    InputSpec(
        name="financial_intermediaries_1",
        subindex="financial_intermediaries",
        recipe="PASSTHROUGH",
        fred_ids=("DRTSCILM",),
        notes="Net % of banks tightening C&I loan standards (SLOOS).",
        is_substitute=True,
        substitute_for="KBW Bank Index CMAX",
    ),
    InputSpec(
        name="financial_intermediaries_2",
        subindex="financial_intermediaries",
        recipe="PASSTHROUGH",
        fred_ids=("BAMLCC0A4BBBTRIV",),
        notes="ICE BofA BBB Corporate Index — investment-grade financial credit stress.",
        is_substitute=True,
        substitute_for="Bank-sector realized volatility",
    ),
    InputSpec(
        name="financial_intermediaries_3",
        subindex="financial_intermediaries",
        recipe="PASSTHROUGH",
        fred_ids=("DRTSCLCC",),
        notes="Net % of banks tightening consumer credit-card standards (SLOOS).",
        is_substitute=True,
        substitute_for="SLOOS tightening diffusion (canonical)",
    ),

    # ─── Foreign exchange ─────────────────────────────────────────────
    InputSpec(
        name="fx_market_1",
        subindex="fx_market",
        recipe="DAILY_VOL",
        fred_ids=("DTWEXBGS",),
        realvol_window=20,
        notes="20-day realized vol of trade-weighted USD (broad).",
    ),
    InputSpec(
        name="fx_market_2",
        subindex="fx_market",
        recipe="DAILY_VOL",
        fred_ids=("DEXUSEU",),
        realvol_window=20,
        notes="20-day realized vol of EUR/USD daily returns.",
        is_substitute=True,
        substitute_for="EUR/USD cross-currency basis swap",
    ),
    InputSpec(
        name="fx_market_3",
        subindex="fx_market",
        recipe="DAILY_VOL",
        fred_ids=("DEXJPUS",),
        realvol_window=20,
        notes="20-day realized vol of JPY/USD daily returns.",
        is_substitute=True,
        substitute_for="JPY/USD cross-currency basis swap",
    ),
)


# ─── Manifest + config ────────────────────────────────────────────────


@dataclass
class CISSUSBuilderManifest:
    """Reproducibility artifact returned alongside the input matrix.

    Records exactly which FRED series fed each canonical input, which
    were substituted, and the build parameters.
    """
    start: str | None
    end: str | None
    frequency: str | None
    rows_built: int
    inputs: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def n_substitutes(self) -> int:
        return sum(1 for i in self.inputs if i.get("is_substitute"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "start": self.start, "end": self.end, "frequency": self.frequency,
            "rows_built": self.rows_built,
            "n_substitutes": self.n_substitutes(),
            "inputs": list(self.inputs),
            "warnings": list(self.warnings),
        }


@dataclass
class CISSUSBuilderConfig:
    """Override knobs for the builder.

    overrides: name → new InputSpec (replaces canonical spec for that name)
    """
    overrides: dict[str, InputSpec] = field(default_factory=dict)
    default_frequency: str = "w"          # weekly aggregation by default
    default_aggregation: str = "avg"       # FRED frequency aggregation method


# ─── Builder ───────────────────────────────────────────────────────────


class CISSUSBuilder:
    """Build the 15-column CISS-US input matrix from FRED."""

    def __init__(self, fred_client: Any, config: CISSUSBuilderConfig | None = None) -> None:
        self.fred = fred_client
        self.config = config or CISSUSBuilderConfig()

    def specs(self) -> list[InputSpec]:
        """Effective spec list with overrides applied."""
        out: list[InputSpec] = []
        for s in CANONICAL_SPECS:
            out.append(self.config.overrides.get(s.name, s))
        return out

    def required_fred_series(self) -> list[str]:
        """Flat list of unique FRED mnemonics this builder will fetch."""
        ids: set[str] = set()
        for s in self.specs():
            ids.update(s.fred_ids)
        return sorted(ids)

    # FRED series IDs that are published at lower-than-weekly cadence.
    # Requesting these at frequency="w" returns HTTP 400. v0.3.1 fix: fetch
    # them at native frequency and reindex onto the main panel via ffill.
    QUARTERLY_FRED_IDS: tuple[str, ...] = ("DRTSCILM", "DRTSCLCC")

    def build(
        self,
        start: str | None = None,
        end: str | None = None,
        frequency: str | None = None,
    ) -> tuple[pd.DataFrame, CISSUSBuilderManifest]:
        """Fetch FRED series, apply recipes, return (15-col DataFrame, manifest)."""
        freq = frequency or self.config.default_frequency
        specs = self.specs()

        # Split required series into two cadences:
        # - main panel at the requested frequency
        # - quarterly panel for SLOOS-style series (FRED rejects freq=w for them)
        unique_ids = self.required_fred_series()
        quarterly_ids = [s for s in unique_ids if s in self.QUARTERLY_FRED_IDS]
        main_ids = [s for s in unique_ids if s not in self.QUARTERLY_FRED_IDS]
        log.info(
            f"CISSUSBuilder: fetching {len(main_ids)} FRED series at freq={freq}"
            + (f" + {len(quarterly_ids)} at native (quarterly)" if quarterly_ids else "")
        )
        raw_panel = self.fred.get_multi(
            main_ids,
            observation_start=start,
            observation_end=end,
            frequency=freq,
            aggregation_method=self.config.default_aggregation,
        )
        # Fetch quarterly series at native cadence and reindex onto main panel
        if quarterly_ids:
            q_panel = self.fred.get_multi(
                quarterly_ids,
                observation_start=start,
                observation_end=end,
                # Omit frequency to use FRED native (quarterly for these)
                aggregation_method=self.config.default_aggregation,
            )
            if not q_panel.empty:
                aligned_q = q_panel.reindex(raw_panel.index, method="ffill")
                for col in aligned_q.columns:
                    raw_panel[col] = aligned_q[col]

        # Apply each recipe
        out = pd.DataFrame(index=raw_panel.index)
        manifest_entries: list[dict[str, Any]] = []
        warnings: list[str] = []

        for spec in specs:
            try:
                series = self._apply_recipe(spec, raw_panel)
            except Exception as e:
                msg = f"recipe for {spec.name} ({spec.recipe}) failed: {e}"
                log.warning(msg)
                warnings.append(msg)
                series = pd.Series(np.nan, index=raw_panel.index, name=spec.name)
            out[spec.name] = series

            entry: dict[str, Any] = {
                "name": spec.name,
                "subindex": spec.subindex,
                "recipe": spec.recipe,
                "fred_ids": list(spec.fred_ids),
                "is_substitute": spec.is_substitute,
                "notes": spec.notes,
            }
            if spec.substitute_for:
                entry["substitute_for"] = spec.substitute_for
            if spec.cmax_window:
                entry["cmax_window"] = spec.cmax_window
            if spec.realvol_window:
                entry["realvol_window"] = spec.realvol_window
            manifest_entries.append(entry)

        # Filter rows where any input is NaN (CISSUS expects clean rows)
        clean = out.dropna(how="any")
        if clean.empty and not out.empty:
            warnings.append(
                "all rows dropped after NaN filter — check FRED coverage and frequency"
            )

        manifest = CISSUSBuilderManifest(
            start=start, end=end, frequency=freq,
            rows_built=int(len(clean)),
            inputs=manifest_entries, warnings=warnings,
        )
        return clean, manifest

    # ─── Recipes ──────────────────────────────────────────────────────

    def _apply_recipe(self, spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        if spec.recipe == "PASSTHROUGH":
            return self._recipe_passthrough(spec, panel)
        if spec.recipe == "SPREAD":
            return self._recipe_spread(spec, panel)
        if spec.recipe == "ABS":
            return self._recipe_abs(spec, panel)
        if spec.recipe == "CMAX":
            return self._recipe_cmax(spec, panel)
        if spec.recipe == "REALVOL":
            return self._recipe_realvol(spec, panel)
        if spec.recipe == "DAILY_VOL":
            return self._recipe_daily_vol(spec, panel)
        raise ValueError(f"unknown recipe: {spec.recipe}")

    @staticmethod
    def _need(panel: pd.DataFrame, name: str) -> pd.Series:
        if name not in panel.columns:
            raise KeyError(f"FRED series {name} not in fetched panel")
        return panel[name]

    @staticmethod
    def _recipe_passthrough(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        if len(spec.fred_ids) != 1:
            raise ValueError(f"PASSTHROUGH expects 1 FRED id, got {spec.fred_ids}")
        return CISSUSBuilder._need(panel, spec.fred_ids[0]).rename(spec.name)

    @staticmethod
    def _recipe_spread(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        if len(spec.fred_ids) != 2:
            raise ValueError(f"SPREAD expects 2 FRED ids, got {spec.fred_ids}")
        a = CISSUSBuilder._need(panel, spec.fred_ids[0])
        b = CISSUSBuilder._need(panel, spec.fred_ids[1])
        return (a - b).rename(spec.name)

    @staticmethod
    def _recipe_abs(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        if len(spec.fred_ids) != 1:
            raise ValueError(f"ABS expects 1 FRED id, got {spec.fred_ids}")
        return CISSUSBuilder._need(panel, spec.fred_ids[0]).abs().rename(spec.name)

    @staticmethod
    def _recipe_cmax(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        """CMAX_t = (rolling_max - current) / rolling_max."""
        if len(spec.fred_ids) != 1:
            raise ValueError(f"CMAX expects 1 FRED id, got {spec.fred_ids}")
        if not spec.cmax_window:
            raise ValueError("CMAX requires cmax_window")
        x = CISSUSBuilder._need(panel, spec.fred_ids[0])
        rolling_max = x.rolling(window=spec.cmax_window, min_periods=1).max()
        # Drawdown as positive fraction
        dd = (rolling_max - x) / rolling_max
        return dd.clip(lower=0.0).rename(spec.name)

    @staticmethod
    def _recipe_realvol(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        """Rolling standard deviation of log-differences."""
        if len(spec.fred_ids) != 1:
            raise ValueError(f"REALVOL expects 1 FRED id, got {spec.fred_ids}")
        if not spec.realvol_window:
            raise ValueError("REALVOL requires realvol_window")
        x = CISSUSBuilder._need(panel, spec.fred_ids[0]).astype(float)
        # Log-differences (returns); add tiny epsilon to avoid log of zero
        # for series that contain zeros (rare for prices).
        eps = 1e-12
        log_x = np.log(x.where(x > 0, eps))
        rets = log_x.diff()
        vol = rets.rolling(window=spec.realvol_window, min_periods=spec.realvol_window // 2).std()
        return vol.rename(spec.name)

    @staticmethod
    def _recipe_daily_vol(spec: InputSpec, panel: pd.DataFrame) -> pd.Series:
        """Rolling stdev of (level − level.shift(1)) — for FX-style series."""
        if len(spec.fred_ids) != 1:
            raise ValueError(f"DAILY_VOL expects 1 FRED id, got {spec.fred_ids}")
        if not spec.realvol_window:
            raise ValueError("DAILY_VOL requires realvol_window")
        x = CISSUSBuilder._need(panel, spec.fred_ids[0]).astype(float)
        diffs = x.diff()
        vol = diffs.rolling(window=spec.realvol_window, min_periods=spec.realvol_window // 2).std()
        return vol.rename(spec.name)
