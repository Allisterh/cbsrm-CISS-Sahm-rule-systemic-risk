"""
CBSRM — Cross-Border Systemic Risk Monitor
==========================================

Open-source quantitative framework for cross-jurisdiction financial-stability
monitoring. Reproduces canonical systemic-stress indices (CISS, SRISK, CoVaR)
in modern typed Python, integrates them across jurisdictions, and exposes
the result via API for hedge funds, family offices, and regulators.

Public methodology, regulator-grade audit trail, Apache-2.0 licensed.

See cbsrm.data, cbsrm.indicators, cbsrm.network, cbsrm.stress, cbsrm.api,
cbsrm.audit subpackages. README.md and whitepaper/cbsrm_methodology_v1.md
describe the full methodology and intended use.
"""
__version__ = "0.3.0"
__all__ = ["__version__"]
