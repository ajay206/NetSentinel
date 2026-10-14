# ADR-002: Microservices Architecture with Kafka Event Bus and Internal MCP Server

* **Status:** Proposed
* **Date:** 2026-10-14
* **Deciders:** NetSentinel Architecture Team

## Context
NetSentinel requires decoupled ingestion, processing, streaming analytics, and AI orchestration to handle high-throughput telecom telemetry and real-time alarms without single points of failure. Furthermore, AI capabilities must securely access internal tools and databases without exposing raw system hooks to external clients.

## Decision
1. **Microservices with Database-per-Service:** Each service owns its database instance (TimescaleDB, Neo4j, Qdrant, etc.) to ensure loose coupling.
2. **Kafka Event Bus (KRaft):** Asynchronous event-driven communication using Kafka topics (`alarms.raw`, `alarms.enriched`, `kpis`, `incidents`).
3. **Internal Model Context Protocol (MCP) Server:** The MCP server operates as an internal tool layer invoked exclusively by the `copilot-orchestrator`. There are no external AI clients.

## Consequences
* **Positive:** High scalability, strict service boundaries, robust event streaming, and secure internal AI tooling via MCP.
* **Negative:** Distributed system operational overhead and eventual consistency considerations across services.
