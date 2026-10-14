# ADR-001: Knowledge Graph and Vector RAG for Root-Cause Context

* **Status:** Proposed
* **Date:** 2026-10-14
* **Deciders:** NetSentinel Architecture Team

## Context
Telecom networks are complex, highly interconnected systems of cell towers, optical links, core routers, and virtualized network functions (VNFs). When alarms fire in a Network Operations Center (NOC), operators must rapidly understand upstream/downstream dependencies and historical incident context to isolate root causes. Vector search alone struggles with explicit topological paths, while graph traversal alone struggles with unstructured runbooks and textual logs.

## Decision
We adopt a hybrid architecture combining:
1. **Knowledge Graph (Neo4j):** Modeling telecom topology (sites, links, equipment, services) to query structural dependencies during alarm correlation.
2. **Vector RAG (Qdrant):** Storing and searching historical incident reports, maintenance tickets, and vendor documentation for semantic context.

## Consequences
* **Positive:** Combines precise topological root-cause identification with rich historical semantic insights for the AI copilot.
* **Negative:** Increased operational complexity requiring both Neo4j and Qdrant services in later phases.
