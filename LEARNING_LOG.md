# Learning Log - NetSentinel

This log is maintained by Ajay to track learnings, insights, and key concepts encountered during the development of NetSentinel.

---

## Week 1: Setup, Repo Skeleton & Core Infrastructure (Oct 17–18, 2026)

### Focus Areas
- Monorepo bootstrapping with `uv` workspace and shared library (`ns-common`).
- Containerized core infrastructure (`Kafka KRaft` single-node, `TimescaleDB`, `Kafka UI`).
- Event streaming fundamentals: topics, partitions, keys, and consumer groups.
- Telecom standards overview: Fault Management vs. Performance Management, alarm severities (X.733), TMF642 alarm shape, and 3GPP KPI names (TS 28.552).

### Key Learnings & Notes
*(To be filled by Ajay)*

- **Why Kafka auto-create topics is disabled:**
- **Kafka KRaft vs ZooKeeper:**
- **TMF642 alarm structure takeaways:**

---

## Week 2: Simulator, Gateway & React Dashboard (Oct 14, 2026)

### Focus Areas
- Generating synthetic topology and fault scenarios (`libs/netgen`).
- Publishing TMF642‑like alarm JSON to Kafka (`netgen‑simulator`).
- Thin FastAPI gateway that aggregates health, serves recent alarms, and pushes live updates via WebSocket.
- React + Vite UI consuming the WebSocket stream, displaying severity‑coloured tables, and showing service health tiles.

### Learning Prompts for Ajay
- **WebSockets vs. polling:**  
  *What are the latency, bandwidth, and back‑pressure differences? How does the gateway handle reconnects?*  

- **aiokafka consumer groups & offset reset:**  
  *When the gateway restarts, which offset does it start from? How would you configure “latest” vs. “earliest”?*  

- **React Query (or SWR) polling strategy:**  
  *If you switched from WebSocket to periodic polling for recent alarms, what cache‑invalidation rules would you use?*  

- **Tailwind utility classes:**  
  *List the classes you used for severity colour‑coding. How would you extend the palette for a new “info” severity?*  

- **Why a thin gateway now:**  
  *Explain the trade‑off between a thin FastAPI façade and a richer microservice. How does this decision simplify testing and deployment in Week 2?*  

*(Leave space for answers as you work through the next sprint.)*
