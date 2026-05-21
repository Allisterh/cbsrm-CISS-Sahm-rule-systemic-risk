"""Tests for cbsrm.builders.ciss_us_builder."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cbsrm.builders.ciss_us_builder import (
    CANONICAL_SPECS, CISSUSBuilder, CISSUSBuilderConfig,
    CISSUSBuilderManifest, InputSpec,
)


# ─── Fake FRED client ─────────────────────────────────────────────────


class FakeFRED:
    """Returns a deterministic synthetic panel for the requested mnemonics."""

    def __init__(self, n_obs: int = 400, seed: int = 7) -> None:
        self.n_obs = n_obs
        self.seed = seed
        self.calls: list[dict] = []

    def get_multi(self, series_ids, **kwargs) -> pd.DataFrame:
        self.calls.append({"series_ids": list(series_ids), **kwargs})
        rng = np.random.default_rng(self.seed)
        idx = pd.date_range("2018-01-01", periods=self.n_obs, freq="W", tz="UTC")
        data = {}
        for sid in series_ids:
            base = rng.normal(0.0, 1.0, self.n_obs).cumsum()
            # Make price-like (positive) for series the builder treats as prices
            if sid in ("SP500", "DGS10", "DTWEXBGS", "DEXUSEU", "DEXJPUS"):
                data[sid] = 100.0 + base
            else:
                data[sid] = base
        return pd.DataFrame(data, index=idx)


# ─── Spec list integrity ──────────────────────────────────────────────


def test_canonical_specs_have_15_inputs():
    assert len(CANONICAL_SPECS) == 15


def test_canonical_specs_5_per_subindex_no_3():
    """3 inputs per subindex, 5 subindices."""
    by_sub: dict[str, int] = {}
    for s in CANONICAL_SPECS:
        by_sub[s.subindex] = by_sub.get(s.subindex, 0) + 1
    assert len(by_sub) == 5
    for k, n in by_sub.items():
        assert n == 3, f"{k} has {n} inputs (expected 3)"


def test_canonical_specs_unique_names():
    names = [s.name for s in CANONICAL_SPECS]
    assert len(set(names)) == len(names)


def test_canonical_specs_all_recipes_known():
    valid = {"PASSTHROUGH", "SPREAD", "ABS", "CMAX", "REALVOL", "DAILY_VOL"}
    for s in CANONICAL_SPECS:
        assert s.recipe in valid, f"{s.name}: unknown recipe {s.recipe}"


def test_cmax_specs_have_window():
    for s in CANONICAL_SPECS:
        if s.recipe == "CMAX":
            assert s.cmax_window is not None and s.cmax_window > 0


def test_realvol_daily_vol_specs_have_window():
    for s in CANONICAL_SPECS:
        if s.recipe in ("REALVOL", "DAILY_VOL"):
            assert s.realvol_window is not None and s.realvol_window > 0


# ─── Construction ─────────────────────────────────────────────────────


def test_builder_lists_unique_fred_series():
    b = CISSUSBuilder(FakeFRED())
    ids = b.required_fred_series()
    assert ids == sorted(set(ids))           # unique + sorted
    assert "VIXCLS" in ids
    assert "SP500" in ids
    assert "SOFR" in ids
    assert "IORB" in ids


def test_builder_with_no_overrides_returns_canonical():
    b = CISSUSBuilder(FakeFRED())
    specs = b.specs()
    assert len(specs) == 15
    assert specs == list(CANONICAL_SPECS)


def test_builder_override_replaces_one_spec():
    custom = InputSpec(
        name="money_market_1", subindex="money_market",
        recipe="PASSTHROUGH", fred_ids=("CUSTOM_SERIES",),
    )
    cfg = CISSUSBuilderConfig(overrides={"money_market_1": custom})
    b = CISSUSBuilder(FakeFRED(), cfg)
    specs = b.specs()
    by_name = {s.name: s for s in specs}
    assert by_name["money_market_1"] is custom
    assert by_name["money_market_2"] == [
        s for s in CANONICAL_SPECS if s.name == "money_market_2"
    ][0]


# ─── End-to-end build ─────────────────────────────────────────────────


def test_build_returns_15_columns():
    b = CISSUSBuilder(FakeFRED(n_obs=300))
    df, manifest = b.build()
    assert isinstance(df, pd.DataFrame)
    assert df.shape[1] == 15
    assert isinstance(manifest, CISSUSBuilderManifest)
    assert manifest.rows_built == len(df)


def test_build_column_names_match_canonical():
    b = CISSUSBuilder(FakeFRED(n_obs=300))
    df, _ = b.build()
    expected = [s.name for s in CANONICAL_SPECS]
    assert list(df.columns) == expected


def test_build_drops_nan_rows():
    b = CISSUSBuilder(FakeFRED(n_obs=300))
    df, _ = b.build()
    assert not df.isna().any().any()


def test_build_manifest_records_substitutes():
    b = CISSUSBuilder(FakeFRED(n_obs=300))
    _, manifest = b.build()
    n_sub = manifest.n_substitutes()
    # Per CANONICAL_SPECS table, there are several substitutes
    assert n_sub >= 5
    # At least the SLOOS-type ones flagged
    sub_names = [e["name"] for e in manifest.inputs if e.get("is_substitute")]
    assert "financial_intermediaries_1" in sub_names
    assert "fx_market_2" in sub_names


def test_build_passes_kwargs_to_fred():
    fake = FakeFRED(n_obs=100)
    b = CISSUSBuilder(fake)
    b.build(start="2020-01-01", end="2024-01-01", frequency="m")
    # v0.3.1: build() now makes TWO fetches — main panel + quarterly SLOOS
    # series at native cadence (frequency omitted for the latter so FRED
    # returns them quarterly instead of 400-ing on freq=w/m).
    assert len(fake.calls) == 2
    main_call = next(c for c in fake.calls if "frequency" in c and c.get("frequency") == "m")
    assert main_call["observation_start"] == "2020-01-01"
    assert main_call["observation_end"] == "2024-01-01"
    assert main_call["frequency"] == "m"
    # Quarterly call must NOT include the frequency kwarg
    quarterly_call = next(c for c in fake.calls if "frequency" not in c)
    assert "DRTSCILM" in quarterly_call["series_ids"]
    assert "DRTSCLCC" in quarterly_call["series_ids"]


# ─── Recipes ──────────────────────────────────────────────────────────


def test_spread_recipe_subtracts():
    panel = pd.DataFrame({
        "SOFR": [5.0, 5.1, 5.2],
        "IORB": [4.8, 4.8, 4.8],
    })
    spec = InputSpec(
        name="x", subindex="money_market",
        recipe="SPREAD", fred_ids=("SOFR", "IORB"),
    )
    out = CISSUSBuilder._recipe_spread(spec, panel)
    assert list(out) == pytest.approx([0.2, 0.3, 0.4])


def test_abs_recipe_takes_absolute():
    panel = pd.DataFrame({"T10Y2Y": [-0.5, 0.0, 0.5, -1.2]})
    spec = InputSpec(name="x", subindex="bond_market",
                     recipe="ABS", fred_ids=("T10Y2Y",))
    out = CISSUSBuilder._recipe_abs(spec, panel)
    assert list(out) == pytest.approx([0.5, 0.0, 0.5, 1.2])


def test_cmax_recipe_zero_at_new_highs():
    # Monotonically increasing → drawdown 0 always
    panel = pd.DataFrame({"SP500": [100.0, 101.0, 102.0, 103.0, 104.0]})
    spec = InputSpec(name="x", subindex="equity_market",
                     recipe="CMAX", fred_ids=("SP500",), cmax_window=3)
    out = CISSUSBuilder._recipe_cmax(spec, panel)
    assert all(v == pytest.approx(0.0) for v in out)


def test_cmax_recipe_positive_on_drawdown():
    panel = pd.DataFrame({"SP500": [100.0, 110.0, 120.0, 90.0]})
    spec = InputSpec(name="x", subindex="equity_market",
                     recipe="CMAX", fred_ids=("SP500",), cmax_window=10)
    out = CISSUSBuilder._recipe_cmax(spec, panel)
    # Last value: rolling_max=120, current=90 → (120-90)/120 = 0.25
    assert out.iloc[-1] == pytest.approx(0.25)


def test_realvol_recipe_nonnegative():
    panel = pd.DataFrame({
        "DGS10": [3.0, 3.05, 3.10, 3.08, 3.12, 3.15, 3.13, 3.20,
                  3.18, 3.22, 3.25, 3.19, 3.21, 3.24, 3.20],
    })
    spec = InputSpec(name="x", subindex="bond_market",
                     recipe="REALVOL", fred_ids=("DGS10",), realvol_window=5)
    out = CISSUSBuilder._recipe_realvol(spec, panel)
    valid = out.dropna()
    assert (valid >= 0).all()


def test_daily_vol_recipe_uses_diffs():
    """Constant series → zero vol."""
    panel = pd.DataFrame({"DTWEXBGS": [100.0] * 30})
    spec = InputSpec(name="x", subindex="fx_market",
                     recipe="DAILY_VOL", fred_ids=("DTWEXBGS",), realvol_window=10)
    out = CISSUSBuilder._recipe_daily_vol(spec, panel)
    valid = out.dropna()
    assert valid.abs().max() == pytest.approx(0.0, abs=1e-12)


def test_recipe_unknown_raises():
    bad = InputSpec(name="x", subindex="z",
                    recipe="BOGUS", fred_ids=("X",))
    with pytest.raises(ValueError, match="unknown recipe"):
        CISSUSBuilder._apply_recipe(CISSUSBuilder(FakeFRED()), bad,
                                    pd.DataFrame({"X": [1.0]}))


def test_passthrough_recipe_validates_arity():
    bad = InputSpec(name="x", subindex="z",
                    recipe="PASSTHROUGH", fred_ids=("A", "B"))
    with pytest.raises(ValueError, match="PASSTHROUGH"):
        CISSUSBuilder._recipe_passthrough(bad, pd.DataFrame())


def test_recipe_failure_records_warning_and_fills_nan():
    """If a recipe raises, builder marks warning + fills column with NaN."""
    # Create a panel missing one required series
    class PartialFRED:
        def get_multi(self, series_ids, **_kwargs):
            idx = pd.date_range("2020-01-01", periods=50, freq="W")
            # Return all but VIXCLS
            return pd.DataFrame(
                {s: np.linspace(1.0, 2.0, 50) for s in series_ids if s != "VIXCLS"},
                index=idx,
            )
    b = CISSUSBuilder(PartialFRED())
    df, manifest = b.build()
    # equity_market_1 (VIXCLS PASSTHROUGH) should have produced a warning
    assert any("equity_market_1" in w for w in manifest.warnings)
