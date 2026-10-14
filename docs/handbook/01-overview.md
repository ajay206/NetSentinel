# 01 - Overview & Architecture

## What is NetSentinel?
NetSentinel is an AI-assisted Network Operations Center (NOC) copilot designed for telecom operators. It ingests synthetic network telemetry, correlates alarms and performance metrics, identifies root causes using topological knowledge graphs and vector RAG, and assists NOC engineers in resolving incidents rapidly.

**Important Note:** All data processed by NetSentinel is 100% synthetic. No real telecom subscriber or network data is ever used.

## Why Event-Driven Microservices?
Telecom networks produce continuous, high-volume streams of events (alarms, link state changes, KPI threshold violations). An event-driven architecture built on Apache Kafka ensures loose coupling, fault isolation, and real-time responsiveness across ingestion, streaming analytics, and AI copilot orchestration.

## Architecture Diagram

```mermaid
graph TD
    subgraph Simulation
        NS[netgen-simulator] -->|alarms.raw, kpis| K[Kafka Event Bus]
    end

    subgraph Core Stream Processing
        K --> AI[alarm-ingest]
        K --> KS[kpi-service]
        AI -->|alarms.enriched| K
        KS --> TS[(TimescaleDB)]
    end

    subgraph Intelligence & Storage
        TS --> IS[incident-service]
        IS -->|incidents| K
        NEO[(Neo4j Topology)] <--> TSVC[topology-service]
        QD[(Qdrant Vector DB)] <--> RS[rag-service]
        ML[ml-service] -->|anomaly inference| K
    end

    subgraph AI Copilot Layer
        CO[copilot-orchestrator] --> MCP[internal mcp-server]
        MCP -.-> TSVC
        MCP -.-> RS
        MCP -.-> IS
        LLG[llm-gateway] --> OL[(Ollama Local LLM)]
        CO --> LLG
    end

    subgraph Gateway & Frontend
        AG[api-gateway / Traefik] --> CO
        AG --> UI[noc-console (React)]
    end
```

> **Security & Design Constraint:** The Model Context Protocol (MCP) server is strictly an internal tool layer called exclusively by the `copilot-orchestrator`. There are no external AI clients.
