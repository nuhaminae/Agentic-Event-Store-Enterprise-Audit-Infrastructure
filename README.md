<h1 align="center"> Agentic Event Store & Enterprise Audit Infrastructure </h1>

[![CI](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/actions/workflows/CI.yml/badge.svg)](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/actions/workflows/CI.yml)
![Black Formatting](https://img.shields.io/badge/code%20style-black-000000.svg)
![isort Imports](https://img.shields.io/badge/imports-isort-blue.svg)
![Flake8 Lint](https://img.shields.io/badge/lint-flake8-yellow.svg)

---

## Project Review

This project implements an **agentic event store** with enterprise‑grade audit infrastructure.  
It is designed to support **event sourcing**, **audit trails**, and **domain logic enforcement** across aggregates.  
Phase 1 delivered the event store foundation (append, replay, outbox, checkpoints).  
Phase 2 introduces domain aggregates, command handlers, and business rule enforcement.

---

## Key Features

- **Event Store Core**: Append events immutably with optimistic concurrency and audit metadata.  
- **Outbox Pattern**: Reliable publishing of events with status tracking.  
- **Projection Checkpoints**: Replay progress tracking for projections.  
- **Domain Aggregates**:  
  - LoanApplicationAggregate with full state machine and rules.  
  - AgentSessionAggregate with Gas Town enforcement and model version locking.  
  - ComplianceRecordAggregate with mandatory check tracking.  
  - AuditLedgerAggregate with causal ordering.  
- **Command Handlers**: Encapsulate business logic (submit application, credit analysis, fraud screening, compliance check, decision generation, human review, agent session start).  
- **Tests**: Concurrency tests and domain rule enforcement tests integrated under `tests/`.

---

## Table of Contents

- [Project Review](#project-review)
- [Key Features](#key-features)
- [Table of Contents](#table-of-contents)
- [Project Structure (Snippet)](#project-structure-snippet)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
- [Usage](#usage)
- [Project Status](#project-status)

---

## Project Structure (Snippet)

```bash
Agentic-Event-Store-Enterprise-Audit-Infrastructure/
├── src/
│   ├── aggregates/                # Domain aggregates (loan, agent, compliance, audit)
│   ├── commands/                  # Command handlers
│   ├── models/                    # Pydantic models for events, metadata, outbox
│   ├── event_store.py             # Event store core (append, replay, checkpoints)
│   └── schema.sql                 # Database schema
├── tests/                         # Test suites
│   ├── test_concurrency.py        # Concurrency and outbox tests
│   └── test_domain_logic.py       # Rule enforcement tests
├── pyproject.toml                 # Dependencies (locked with uv)
├── DESIGN.md                      # Design notes
├── DOMAINNOTES.md                 # Domain logic notes
└── README.md                      # Documentation
```

---

## Installation

### Prerequisites

- Python 3.12  
- Git  
- PostgreSQL (for event store persistence)

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

---

## Project Status

Phase 1 (event store foundation) is complete.  
Phase 2 (domain logic aggregates and command handlers) is complete.
Phase 3 (Projections & Async Daemon) is in progress.
Check the [commit history](https://github.com/nuhaminae/Agentic-Event-Store-Enterprise-Audit-Infrastructure/) for updates.
