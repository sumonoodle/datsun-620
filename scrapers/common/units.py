"""Unit conversions so figures from different sources compare on equal terms.

Collectors normalise to canonical units before emitting observations:
  lengths -> mm, weights -> kg, displacement -> cc, power -> hp, torque -> Nm.
The original value and unit are kept in the citation for traceability.
"""

from __future__ import annotations


def inch_to_mm(v: float) -> float:
    return round(v * 25.4, 1)


def foot_to_mm(v: float) -> float:
    return round(v * 304.8, 1)


def lb_to_kg(v: float) -> float:
    return round(v * 0.45359237, 1)


def cuin_to_cc(v: float) -> float:
    return round(v * 16.387064, 1)


def ftlb_to_nm(v: float) -> float:
    return round(v * 1.3558179, 1)


def ps_to_hp(v: float) -> float:
    return round(v * 0.98632, 1)
