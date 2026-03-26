<h1 align="center"> Agentic Event Store & Enterprise Audit Infrastructure </h1>

[![CI](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/actions/workflows/CI.yml/badge.svg)](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/actions/workflows/CI.yml)
![Black Formatting](https://img.shields.io/badge/code%20style-black-000000.svg)
![isort Imports](https://img.shields.io/badge/imports-isort-blue.svg)
![Flake8 Lint](https://img.shields.io/badge/lint-flake8-yellow.svg)

---

## Project Review

This project implements an agentic event store with enterprise‑grade audit infrastructure.  
It supports event sourcing, audit trails, domain logic enforcement, projections, upcasting, and MCP server integration.  

- Phase 1: Event store foundation (append, replay, outbox, checkpoints).  
- Phase 2: Domain aggregates, command handlers, business rule enforcement.  
- Phase 3: Projections and async daemon for CQRS read models.  
- Phase 4: Upcasting, immutability, integrity chains, Gas Town crash recovery.  
- Phase 5: MCP server exposing tools and resources for agents and auditors.

---

## Key Features

- Event Store Core: Append events immutably with optimistic concurrency and audit metadata.  
- Outbox Pattern: Reliable publishing of events with status tracking.  
- Projection Checkpoints: Replay progress tracking for projections.  
- Domain Aggregates: LoanApplicationAggregate, AgentSessionAggregate, ComplianceRecordAggregate, AuditLedgerAggregate.  
- Command Handlers: Encapsulate business logic for lifecycle operations.  
- Projections: ApplicationSummary, AgentPerformanceLedger, ComplianceAuditView.  
- Upcasting: Schema evolution with versioned event transformations.  
- Integrity: Cryptographic audit chains to detect tampering.  
- Gas Town Recovery: Deterministic replay for agent crash recovery.  
- MCP Server: Enterprise interface exposing tools and resources.  

---

## Table of Contents

- [Project Review](#project-review)
- [Key Features](#key-features)
- [Table of Contents](#table-of-contents)
- [Project Structure (Snippet)](#project-structure-snippet)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Database Provisioning](#database-provisioning)
  - [Environment Variables](#environment-variables)
  - [Setup](#setup)
- [Usage](#usage)
  - [MCP Tool Examples](#mcp-tool-examples)
  - [MCP Resource Examples](#mcp-resource-examples)
  - [Concurrency Example](#concurrency-example)
  - [Upcasting and Gas Town Recovery](#upcasting-and-gas-town-recovery)
- [Project Status](#project-status)

---

## Project Structure (Snippet)

```bash
Agentic-Event-Store-Enterprise-Audit-Infrastructure/
├── src/
│   ├── aggregates/                # Domain aggregates
│   ├── commands/                  # Command handlers
│   ├── models/                    # Event & metadata models
│   ├── event_store.py             # Event store core
│   ├── projections/               # CQRS read models & daemon
│   ├── upcasting/                 # Upcasters & registry
│   ├── integrity/                 # Audit chain & Gas Town
│   └── mcp/                       # MCP server, tools, resources
├── tests/
│   ├── test_concurrency.py        # Concurrency & outbox tests
│   ├── test_domain_logic.py       # Rule enforcement tests
│   ├── test_projections.py        # Projection lag & rebuild tests
│   ├── test_upcasting.py          # Immutability & upcast tests
│   ├── test_gas_town.py           # Crash recovery tests
│   └── test_mcp_lifecycle.py      # End-to-end MCP lifecycle test
├── pyproject.toml                 # Dependencies
├── DESIGN.md                      # Design notes
├── DOMAINNOTES.md                 # Domain logic notes
└── README.md                      # Documentation
```

---

## Installation

### Prerequisites

- Python 3.12  
- Git  
- PostgreSQL  

### Database Provisioning

```bash
createdb ledger_app
psql -d ledger_app -f src/schema.sql
psql -d ledger_app -f src/projection_schema.sql
```

### Environment Variables

Create a `.env` file:

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

### Setup

```bash
git clone https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure.git
cd Agentic-Event-Store-Enterprise-Audit-Infrastructure
uv sync   # recommended dependency management
```

---

## Usage

- Run tests with `pytest -v`.  
- Use `event_store.append` to persist domain events.  
- Reconstruct aggregates with `LoanApplicationAggregate.load(store, application_id)`.  
- Execute commands via handlers in `src/commands/handlers.py`.  
- Run MCP server with `python -m src.mcp.server`.  

### MCP Tool Examples

```python
await client.call_tool("submit_application", {"application_id":"loan-999","amount":10000})
await client.call_tool("record_credit_analysis", {"application_id":"loan-999","score":680})
await client.call_tool("record_fraud_screening", {"application_id":"loan-999","result":"pass"})
await client.call_tool("record_compliance_check", {"compliance_id":"comp-999","rule":"AML","result":"pass"})
await client.call_tool("generate_decision", {"application_id":"loan-999","decision":"approved"})
await client.call_tool("record_human_review", {"application_id":"loan-999","reviewer":"agent-456","outcome":"completed"})
await client.call_tool("start_agent_session", {"agent_id":"agent-456","model_version":"v1.0"})
```

### MCP Resource Examples

```python
apps = await client.query_resource("applications", {"dsn": DSN})
audit = await client.query_resource("audit-trail", {"dsn": DSN})
integrity = await client.call_tool("run_integrity_check", {"dsn": DSN})
```

### Concurrency Example

```python
async def concurrent_append():
    payload = {"application_id":"loan-999","decision":"approved"}
    task1 = client.call_tool("generate_decision", payload)
    task2 = client.call_tool("generate_decision", payload)
    results = await asyncio.gather(task1, task2, return_exceptions=True)
    print(results)

asyncio.run(concurrent_append())
```

### Upcasting and Gas Town Recovery

```python
from src.integrity.gas_town import reconstruct_agent_context
context = await reconstruct_agent_context(DSN, "agent-456")
print("Recovered agent context:", context)
```

---

## Project Status

- Phase 1: Event store foundation (Completed)
- Phase 2: Domain logic aggregates and command handlers (Completed)
- Phase 3: Projections and Async Daemon  (Completed)
- Phase 4: Upcasting, Integrity and Gas Town  (Completed)
- Phase 5: MCP Server  (Completed)
- Phase 6: What‑If & Regulatory Package (Upcoming)

Check the [commit history](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/) for updates.
