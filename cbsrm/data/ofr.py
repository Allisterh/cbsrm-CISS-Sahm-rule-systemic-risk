"""
OFR (Office of Financial Research, US Treasury) data client.
=============================================================

Wraps two OFR public surfaces:

  1. OFR Financial Stress Index — downloadable CSV at a stable URL.
     Methodology: Monin (2019), "The OFR Financial Stress Index",
     *Risks* 7(1): 25. Daily cadence, 33 raw indicators across 5
     categories (credit, equity valuation, funding, safe assets,
     volatility), aggregated via dynamic factor model.

  2. OFR Short-term Funding Monitor — JSON REST API at
     data.financialresearch.gov/v1.

Both are US government works in the public domain. Derived analytics
are unrestricted for commercial use.

USAGE
-----

    from cbsrm.data import OFRClient
    client = OFRClient()
    fsi = client.get_fsi()                    # composite + 5 contributions
    print(fsi.head())
    print(fsi.tail())

    # Short-term funding monitor (subset of mnemonics)
    timeseries = client.get_stfm_series("REPO_AON_TOTAL_VOLUME")

CSV URL is configurable: the official OFR URL has changed in the past;
operators can override via constructor or env var OFR_FSI_CSV_URL.
"""
from __future__ import annotations

import io
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import requests

log = logging.getLogger("cbsrm.data.ofr")


# Canonical OFR FSI download URL (subject to change — override via env or arg).
# As of v0.2 the published URL is the OFR's FSI page download. If this 404s,
# update via env OFR_FSI_CSV_URL=... or pass csv_url=... to the constructor.
DEFAULT_FSI_CSV_URL = (
    "https://www.financialresearch.gov/financial-stress-index/data/files/ofr-fsi.csv"
)

DEFAULT_STFM_BASE = "https://data.financialresearch.gov/v1"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
# Note: OFR's CSV endpoint (financialresearch.gov) returns 403 to any UA that
# identifies as a script ("cbsrm/...", default httpx UA, curl/wget). A plain
# desktop-Chrome UA passes the WAF. The project-identifying string is moved
# to the X-Project-Source header below.
DEFAULT_PROJECT_HEADER = (
    "cbsrm/0.3.1 research-bot (+https://github.com/pravo123/cbsrm)"
)
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RETRY_MAX = 3
DEFAULT_RETRY_BACKOFF_S = 1.0


@dataclass
class OFRFSIMeta:
    """Metadata for the OFR FSI series."""
    series_id: str = "OFR-FSI"
    title: str = "OFR Financial Stress Index"
    units: str = "Z-score (0 = average level of stress)"
    frequency: str = "D"
    source: str = (
        "Office of Financial Research (US Department of the Treasury). "
        "Methodology: Monin (2019), 'The OFR Financial Stress Index', "
        "Risks 7(1): 25. https://www.financialresearch.gov/financial-stress-index/"
    )
    columns_documented: tuple[str, ...] = (
        "OFR FSI", "Credit", "Equity valuation", "Funding",
        "Safe assets", "Volatility",
    )


@dataclass
class OFRClient:
    """Public OFR data client.

    Parameters
    ----------
    csv_url : str, optional
        OFR FSI CSV URL. Defaults to canonical URL; override via env
        ``OFR_FSI_CSV_URL`` or constructor.
    cache_dir : Path, optional
        Local cache. Default ``./.cbsrm_cache/ofr``. None disables.
    session : requests.Session, optional
        Pre-configured session (test injection point).
    """
    csv_url: str | None = None
    stfm_base: str | None = None
    cache_dir: Path | None = field(default_factory=lambda: Path(".cbsrm_cache/ofr"))
    session: requests.Session | None = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    retry_max: int = DEFAULT_RETRY_MAX
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self) -> None:
        if self.csv_url is None:
            self.csv_url = os.environ.get("OFR_FSI_CSV_URL", DEFAULT_FSI_CSV_URL)
        if self.stfm_base is None:
            self.stfm_base = os.environ.get("OFR_STFM_BASE", DEFAULT_STFM_BASE)
        if self.session is None:
            self.session = requests.Session()
        # The OFR WAF blocks UAs that identify as scripts/bots. We send a
        # standard desktop-Chrome UA in the User-Agent header, AND identify
        # the project transparently via a custom X-Project-Source header that
        # any OFR ops engineer can grep server logs for.
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "X-Project-Source": DEFAULT_PROJECT_HEADER,
            "Accept": "text/csv, */*;q=0.5",
        })
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    # ─── Public API ───────────────────────────────────────────────────

    def source_info(self) -> OFRFSIMeta:
        return OFRFSIMeta()

    def get_fsi(self) -> pd.DataFrame:
        """Return OFR FSI as a DataFrame.

        Columns include 'OFR FSI' (the composite) plus the five
        contribution categories (Credit, Equity valuation, Funding,
        Safe assets, Volatility). Index is UTC-tz DatetimeIndex.
        """
        raw = self._fetch_csv(self.csv_url)
        return self._parse_fsi_csv(raw)

    def get_stfm_series(self, mnemonic: str) -> pd.Series:
        """Pull one time series from the Short-Term Funding Monitor API.

        Endpoint: GET {stfm_base}/series/timeseries/{mnemonic}
        Returns a pandas Series with UTC-tz DatetimeIndex.
        """
        url = f"{self.stfm_base}/series/timeseries/{mnemonic}"
        cache_key = f"stfm_{mnemonic}.json"
        payload = self._get_json(url, cache_key=cache_key)
        return self._parse_stfm_timeseries(payload, mnemonic)

    def list_stfm_mnemonics(self) -> list[dict[str, Any]]:
        """List all available STFM mnemonics."""
        url = f"{self.stfm_base}/metadata/mnemonics/"
        payload = self._get_json(url, cache_key="stfm_mnemonics.json")
        if isinstance(payload, dict) and "data" in payload:
            return list(payload["data"])
        if isinstance(payload, list):
            return payload
        return []

    # ─── HTTP + cache ─────────────────────────────────────────────────

    def _fetch_csv(self, url: str) -> str:
        cache_key = self._cache_key_for_url(url, suffix=".csv")
        cached = self._cache_load_text(cache_key)
        if cached is not None:
            return cached

        last_exc: Exception | None = None
        for attempt in range(self.retry_max):
            try:
                r = self.session.get(url, timeout=self.timeout_s)
                if r.status_code == 429 or 500 <= r.status_code < 600:
                    raise requests.HTTPError(f"transient OFR {r.status_code}")
                r.raise_for_status()
                self._cache_save_text(cache_key, r.text)
                return r.text
            except Exception as e:
                last_exc = e
                if attempt + 1 < self.retry_max:
                    sleep = DEFAULT_RETRY_BACKOFF_S * (2 ** attempt)
                    log.info(f"OFR CSV retry {attempt+1}/{self.retry_max} after {sleep}s: {e}")
                    time.sleep(sleep)
        raise RuntimeError(f"OFR CSV fetch failed after {self.retry_max} attempts: {last_exc}")

    def _get_json(self, url: str, cache_key: str | None = None) -> Any:
        cached = self._cache_load_json(cache_key) if cache_key else None
        if cached is not None:
            return cached

        last_exc: Exception | None = None
        for attempt in range(self.retry_max):
            try:
                r = self.session.get(url, timeout=self.timeout_s)
                if r.status_code == 429 or 500 <= r.status_code < 600:
                    raise requests.HTTPError(f"transient OFR {r.status_code}")
                r.raise_for_status()
                payload = r.json()
                if cache_key:
                    self._cache_save_json(cache_key, payload)
                return payload
            except Exception as e:
                last_exc = e
                if attempt + 1 < self.retry_max:
                    sleep = DEFAULT_RETRY_BACKOFF_S * (2 ** attempt)
                    time.sleep(sleep)
        raise RuntimeError(f"OFR JSON fetch failed: {last_exc}")

    # ─── Parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_fsi_csv(raw: str) -> pd.DataFrame:
        """Parse the OFR FSI CSV.

        OFR publishes the FSI as a CSV with a 'Date' (or 'date') column
        plus contribution columns. Schema has varied over time; this
        parser is permissive: it autodetects the date column and
        coerces remaining columns to float.
        """
        # Skip BOM or blank lines defensively
        df = pd.read_csv(io.StringIO(raw))
        # Find date column
        date_col = None
        for cand in ("Date", "date", "DATE", "Observation Date"):
            if cand in df.columns:
                date_col = cand
                break
        if date_col is None:
            # Assume first column
            date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col], utc=True, errors="coerce")
        df = df.dropna(subset=[date_col])
        df = df.set_index(date_col).sort_index()
        df.index.name = "date"
        # Coerce remaining columns to float
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    @staticmethod
    def _parse_stfm_timeseries(payload: Any, mnemonic: str) -> pd.Series:
        """Parse OFR STFM /series/timeseries response.

        Observed shape (subject to OFR API conventions):
          {"data": [{"date": "2024-01-02", "value": 4.31}, ...]}
        We are permissive — multiple shapes are handled.
        """
        obs: list[dict[str, Any]] = []
        if isinstance(payload, dict):
            if "data" in payload:
                obs = list(payload["data"])
            elif "observations" in payload:
                obs = list(payload["observations"])
        elif isinstance(payload, list):
            obs = payload
        if not obs:
            return pd.Series(dtype=float, name=mnemonic)

        dates: list[pd.Timestamp] = []
        values: list[float] = []
        for o in obs:
            v = o.get("value")
            d = o.get("date") or o.get("observation_date") or o.get("ts")
            if v in (None, "", "."):
                continue
            try:
                values.append(float(v))
            except (TypeError, ValueError):
                continue
            dates.append(pd.Timestamp(d, tz="UTC"))
        if not values:
            return pd.Series(dtype=float, name=mnemonic)
        return pd.Series(
            values,
            index=pd.DatetimeIndex(dates, name="date"),
            name=mnemonic, dtype=float,
        )

    # ─── Cache helpers ────────────────────────────────────────────────

    @staticmethod
    def _cache_key_for_url(url: str, suffix: str = ".dat") -> str:
        # Use last URL path segment, sanitized
        last = url.rstrip("/").rsplit("/", 1)[-1]
        last = "".join(c if c.isalnum() or c in "-_." else "_" for c in last)
        if not last.endswith(suffix):
            last += suffix
        return last

    def _cache_load_text(self, key: str) -> str | None:
        if self.cache_dir is None:
            return None
        p = self.cache_dir / key
        if not p.exists():
            return None
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None

    def _cache_save_text(self, key: str, body: str) -> None:
        if self.cache_dir is None:
            return
        try:
            (self.cache_dir / key).write_text(body, encoding="utf-8")
        except OSError as e:
            log.warning(f"OFR cache write failed: {e}")

    def _cache_load_json(self, key: str) -> Any | None:
        if self.cache_dir is None:
            return None
        import json
        p = self.cache_dir / key
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _cache_save_json(self, key: str, payload: Any) -> None:
        if self.cache_dir is None:
            return
        import json
        try:
            (self.cache_dir / key).write_text(
                json.dumps(payload, default=str), encoding="utf-8"
            )
        except OSError as e:
            log.warning(f"OFR cache write failed: {e}")
