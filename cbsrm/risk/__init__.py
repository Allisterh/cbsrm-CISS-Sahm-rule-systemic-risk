"""
cbsrm.risk — risk-pricing module (added v0.4).

Where ``cbsrm.indicators`` measure *stress* (a contemporaneous read of how
the system is trading) and ``cbsrm.macro`` classifies *regime* (a slower
condition variable), ``cbsrm.risk`` *prices* tail outcomes. The first
inhabitant is SRISK (Brownlees & Engle 2017) — a conditional capital-
shortfall measure: how much equity capital firm *i* would need to inject
to remain solvent if a systemic crisis hit?

v0.4 inventory
--------------

- ``SRISKCalculator``       — the SRISK identity given (D, W, LRMES, k)
- ``LRMESMonteCarlo``       — Monte Carlo LRMES under GJR-GARCH-DCC dynamics
- ``GARCHDCCSimulator``     — bivariate GJR-GARCH(1,1) + DCC simulator
- ``srisk_panel``           — aggregator over many firms

Planned (post-v0.4)
-------------------
- MES (Marginal Expected Shortfall) — 1-day cousin of LRMES
- CoVaR (Adrian-Brunnermeier 2016) — different conditional-VaR construction
- Capital-shortfall-by-jurisdiction roll-up (BIS-style consolidated view)

Reference
---------

Brownlees, C., & Engle, R. F. (2017). SRISK: A conditional capital shortfall
measure of systemic risk. *Review of Financial Studies*, 30(1), 48-79.
NYU Stern V-Lab maintains the canonical live numbers at https://vlab.stern.nyu.edu/.
"""
from cbsrm.risk.garch_dcc_sim import GARCHDCCParams, GARCHDCCSimulator
from cbsrm.risk.srisk import (
    LRMESMonteCarlo,
    SRISKCalculator,
    SRISKResult,
    srisk_panel,
)

__all__ = [
    "GARCHDCCParams",
    "GARCHDCCSimulator",
    "LRMESMonteCarlo",
    "SRISKCalculator",
    "SRISKResult",
    "srisk_panel",
]
