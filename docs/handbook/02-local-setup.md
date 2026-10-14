# 02 - Local Development Setup (Mac M2 8 GB)

This guide walks you through setting up NetSentinel locally on a resource-constrained development environment like a MacBook Air M2 with 8 GB RAM.

## System Prerequisites
* **Python:** `>=3.12` (installed via Homebrew or python.org)
* **uv:** Fast Python package installer and workspace manager (`pip install uv`)
* **Docker Desktop:** Configured with at least 4 GB RAM allocation
* **Ollama (Optional for AI phases):** Running locally (`ollama serve`) with models like `llama3` or `mistral`.

## Step-by-Step Setup

1. **Clone and Configure Environment:**
   ```bash
   git clone https://github.com/ajay206/netsentinel.git
   cd netsentinel
   cp .env.example .env
   # Edit .env and set POSTGRES_PASSWORD=your_secure_password
   ```

2. **Install Python Dependencies (uv):**
   ```bash
   uv sync --all-extras --dev
   ```

3. **Start Core Infrastructure:**
   ```bash
   make up-core
   ```
   *Note: This starts Apache Kafka (KRaft single-node, heap capped at 512MB) and TimescaleDB under strict memory limits suited for 8GB laptops.*

4. **Initialize Kafka Topics:**
   ```bash
   make topics
   ```

5. **Run Tests:**
   ```bash
   make test
   ```

6. **Verify Kafka Event Loop (Smoke Test):**
   ```bash
   make smoke
   ```
