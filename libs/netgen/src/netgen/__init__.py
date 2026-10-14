"""NetGen: synthetic telecom topology and alarm generator."""

from netgen.alarms import (
    SEVERITIES,
    fibre_cut,
    make_alarm,
)
from netgen.topology import Link, Site, build_topology

__all__ = [
    "Site",
    "Link",
    "build_topology",
    "SEVERITIES",
    "make_alarm",
    "fibre_cut",
]
