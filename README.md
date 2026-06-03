# AgentGuard

**Constitutional Governance Kernel for AI Agents**

> *"Your AI agents are only as safe as the system governing them."*
> *"If your agent can break AgentGuard, it better be good at breaking Bitcoin."*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/agentguard-kernel.svg)](https://pypi.org/project/agentguard-kernel/)

---

## Install

```bash
pip install agentguard-kernel
```
[![PyPI](https://img.shields.io/pypi/v/agentguard-kernel.svg)](https://pypi.org/project/agentguard-kernel/)
---

## The Problem

You're building with AI agents. Your agent has access to your database, your payments, your users.

**What happens when it does something it shouldn't?**

Most teams have no answer. No pause button. No audit trail. No trust scoring. No approval gate. Just an agent with full access and a prayer.

AgentGuard changes that.

---

## Quick Start

```python
from agentguard import TrustEngine

engine = TrustEngine(db_path="trust.db")

# New agent starts TRUSTED
level = engine.get_trust_level("my-agent-001")
print(level)  # → TRUSTED

# Quick permission check
if engine.is_allowed("my-agent-001"):
    # proceed with action
    pass

# Agent does something bad
result = engine.apply_penalty("my-agent-001", "spam")
print(result)  # → {"new_points": 20, "new_level": "LIMITED"}

# Agent does something worse
result = engine.apply_penalty("my-agent-001", "abuse")
print(result)  # → {"new_points": 50, "new_level": "OBSERVED"}

# Agent recovers with good behaviour
engine.upgrade_trust("my-agent-001", reason="passed_review")

# Emergency: hard revoke
engine.revoke("my-agent-001", reason="critical_violation")

# Full audit trail
history = engine.get_history("my-agent-001")

# See all agents
agents = engine.list_agents()
```

---

## Trust Levels

```
TRUSTED → LIMITED → OBSERVED → SUSPICIOUS → QUARANTINED → REVOKED
```

| Level       | Points | What it means                    |
|-------------|--------|----------------------------------|
| TRUSTED     | 0–19   | Full access, normal operation    |
| LIMITED     | 20–39  | Restricted actions, monitored    |
| OBSERVED    | 40–59  | All actions logged, some blocked |
| SUSPICIOUS  | 60–79  | Most actions require approval    |
| QUARANTINED | 80–99  | Almost fully restricted          |
| REVOKED     | 100    | Completely blocked               |

---

## Violation Penalties

| Violation            | Points |
|----------------------|--------|
| fake_verification    | 50     |
| hate_speech          | 60     |
| drug_listing         | 40     |
| unauthorized_access  | 40     |
| high_risk_activity   | 35     |
| abuse                | 30     |
| multiple_flags       | 25     |
| spam                 | 20     |

---

## API Reference

### `TrustEngine(db_path="trust.db")`
Initialize with a SQLite database path. Uses `trust.db` by default.

### `get_trust_level(user_id) → str`
Returns the current trust level string.

### `get_trust_score(user_id) → dict`
Returns `{"level": ..., "points": ..., "appeal_status": ...}`.

### `is_allowed(user_id) → bool`
Returns `False` for QUARANTINED or REVOKED agents. Use this as your fast gate check.

### `apply_penalty(user_id, violation_type, details="") → dict`
Applies a penalty. Returns `{"new_points": ..., "new_level": ...}`.

### `upgrade_trust(user_id, reason="") → dict`
Rewards good behaviour, reduces points by 15.

### `revoke(user_id, reason="") → dict`
Hard stop — immediately sets agent to REVOKED.

### `submit_appeal(user_id, reason, evidence) → dict`
Agent submits an appeal for review.

### `get_history(user_id, limit=50) → list`
Full audit trail for an agent.

### `list_agents() → list`
All tracked agents and their trust state.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Your App                       │
├─────────────────────────────────────────────────┤
│         AgentGuard Kernel                        │
│    Trust Engine │ Risk Scoring │ Audit Log       │
├─────────────────────────────────────────────────┤
│              SQLite (Community)                  │
│         PostgreSQL (Enterprise)                  │
└─────────────────────────────────────────────────┘
```

Zero dependencies. Drop into any project in 5 minutes.

---

## Enterprise Edition

The community kernel is free and open source.

Enterprise adds: REST API, JWT auth, Ed25519 capability tokens, human approval gate, real-time event stream, dashboard UI, global emergency stop, multi-tenant orgs, PostgreSQL + Redis, SSO/SAML, webhooks, SLA, and priority support.

📧 bkdk62309@gmail.com — response within 24 hours.

---

## License

MIT — free to use, modify, and build on.

---

## Author

**Dheeraj Kumar Biswakarma**
🐙 [github.com/Mangomindai/agentguard](https://github.com/Mangomindai/agentguard)
