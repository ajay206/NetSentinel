"""NetGen: Synthetic telecom topology, alarm, and KPI generator."""

from netgen.alarms import SEVERITIES, fibre_cut, make_alarm
from netgen.kpis import KPI_BOUNDS, KPI_NAMES, generate_kpis, kpi_value
from netgen.topology import Link, Node, Site, Topology, build_topology

__all__ = [
    "SEVERITIES",
    "make_alarm",
    "fibre_cut",
    "KPI_BOUNDS",
    "KPI_NAMES",
    "generate_kpis",
    "kpi_value",
    "Link",
    "Node",
    "Site",
    "Topology",
    "build_topology",
]

__version__ = "0.1.0"
