# AgentGuard DKBK


**AgentGuard is a governance kernel for AI agents — trust scoring, capability tokens, human approval gates, and full audit logs**

> *"Your AI agents are only as safe as the system governing them."*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.x-green.svg)](https://flask.palletsprojects.com/)

---

## The Problem

You're building with AI agents. Your agent has access to your database, your payments, your users.

**What happens when it does something it shouldn't?**

Most startups have no answer. No pause button. No audit trail. No trust scoring. No approval gate. Just an agent with full access and a prayer.

AgentGuard changes that.

---

## What AgentGuard Does

```
Agent wants to take an action
              ↓
AgentGuard checks:
  → Is this agent trusted enough?
  → Is this action too risky?
  → Does a human need to approve this?
  → Is this agent even allowed to act right now?
              ↓
ALLOW    → action proceeds, logged
PENDING  → paused, human notified for approval
BLOCK    → stopped, agent trust score drops
AUTO-BLOCK → agent trust too low, fully quarantined
```

Every decision is logged. Every action is auditable. Every agent is revocable.

---

## Core Features

**Trust Engine**
Every agent has a trust score (0.0 → 1.0). Successful actions build trust. Failures reduce it. Drop below 0.3 and the agent is automatically blocked. No human needed.

```
TRUSTED → LIMITED → OBSERVED → SUSPICIOUS → QUARANTINED → REVOKED
```

**Capability Tokens**
Agents get scoped, time-limited, cryptographically signed tokens. Not broad API keys. Specific permissions for specific resources that expire automatically.

**Human-in-the-Loop Approval Gate**
Risky actions (delete, transfer, export) pause automatically and wait for a human to approve or deny. Your on-call engineer gets notified. The agent waits.

**Risk Engine**
Every action is scored 0–100 based on action type, resource sensitivity, and time of day. High risk = approval required. Critical risk = hard stop.

**Real-time Event Stream**
SSE endpoint streams every agent event to your dashboard in real time. See trust changes, approvals, blocks as they happen.

**Full Audit Trail**
Every action, every decision, every trust change — immutably logged with actor, timestamp, policy version, and outcome. Your enterprise clients will stop asking uncomfortable questions.

---

## Quick Start

```bash
# Clone
git clone https://github.com/dheerajkumar/agentguard
cd agentguard

# Install
pip install -r requirements.txt

# Run
python app.py
```

Server starts at `http://localhost:5000`

Default users:
| Username | Password | Role  |
|----------|----------|-------|
| admin    | admin123 | admin |
| alice    | alice123 | user  |
| bob      | bob123   | user  |

---

## API in 5 Minutes

### 1. Login
```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Returns: {"token": "eyJ..."}
```

### 2. Check your agents
```bash
curl http://localhost:5000/supervision/status \
  -H "Authorization: Bearer YOUR_TOKEN"

# Returns: {"total_agents": 3, "agents": [...]}
```

### 3. Grant an agent scoped capability
```bash
curl -X POST http://localhost:5000/capabilities/grant \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "agent-123",
    "resource_id": "customer-database",
    "actions": ["read"],
    "ttl_hours": 1
  }'

# Returns: {"capability_token": "eyJ...", "jti": "uuid"}
```

### 4. See pending approvals
```bash
curl http://localhost:5000/approvals/pending \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 5. Approve or deny
```bash
# Approve
curl -X POST http://localhost:5000/approvals/APPROVAL_ID/approve \
  -H "Authorization: Bearer YOUR_TOKEN"

# Deny
curl -X POST http://localhost:5000/approvals/APPROVAL_ID/deny \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"reason": "Too risky"}'
```

### 6. Emergency — pause all agents
```bash
curl -X POST http://localhost:5000/supervision/global/pause \
  -H "Authorization: Bearer YOUR_TOKEN"

# Returns: {"message": "ALL AGENTS PAUSED"}
```

---

## Full API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/health` | None | Health check |
| POST | `/auth/login` | None | Get identity token |
| POST | `/capabilities/grant` | Admin | Grant scoped capability to agent |
| POST | `/capabilities/revoke` | Admin | Revoke capability by JTI |
| GET | `/resources/<id>` | User | Access a resource (policy checked) |
| POST | `/agents/<id>/action` | Agent | Record agent action + update trust |
| GET | `/supervision/status` | Admin | All agent statuses |
| GET | `/supervision/agent/<id>/timeline` | Admin | Full event history for one agent |
| POST | `/supervision/agent/<id>/pause` | Admin | Pause one agent |
| POST | `/supervision/agent/<id>/resume` | Admin | Resume one agent |
| POST | `/supervision/agent/<id>/block` | Admin | Hard block one agent |
| POST | `/supervision/global/pause` | Admin | Pause ALL agents instantly |
| GET | `/approvals/pending` | Admin | List pending approval requests |
| POST | `/approvals/<id>/approve` | Admin | Approve a held action |
| POST | `/approvals/<id>/deny` | Admin | Deny a held action |
| POST | `/tools/run` | User | Run a safe registered tool |
| GET | `/audit` | Admin | Audit log |
| GET | `/events` | User | SSE real-time event stream |

---

## Trust Engine (kernel.py)

The trust engine is a standalone module — use it without the full API if you prefer.

```python
from kernel import TrustEngine

engine = TrustEngine(db_path="trust.db")

# Check trust level
level = engine.get_trust_level("agent-123")
# → "TRUSTED" | "LIMITED" | "OBSERVED" | "SUSPICIOUS" | "QUARANTINED" | "REVOKED"

# Apply a violation
result = engine.apply_penalty("agent-123", "unauthorized_access")
# → {"new_points": 40, "new_level": "OBSERVED"}

# Reward good behaviour
engine.upgrade_trust("agent-123", reason="successful_completion")

# Agent appeals a block
engine.submit_appeal("agent-123", 
    reason="False positive", 
    evidence="Logs show normal behaviour")

# Get history
history = engine.get_history("agent-123")
```

### Trust Levels

| Level | Points | What it means |
|-------|--------|---------------|
| TRUSTED | 0–19 | Full access, normal operation |
| LIMITED | 20–39 | Restricted actions, monitored |
| OBSERVED | 40–59 | All actions logged, some blocked |
| SUSPICIOUS | 60–79 | Most actions require approval |
| QUARANTINED | 80–99 | Almost fully restricted |
| REVOKED | 100 | Completely blocked |

### Violation Penalties

| Violation | Points |
|-----------|--------|
| fake_verification | 50 |
| hate_speech | 60 |
| drug_listing | 40 |
| high_risk_activity | 35 |
| abuse | 30 |
| multiple_flags | 25 |
| spam | 20 |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Your App                       │
├─────────────────────────────────────────────────┤
│              AgentGuard API (app.py)             │
│  Auth │ Capabilities │ Approvals │ Supervision  │
├──────────────┬──────────────┬────────────────────┤
│ Trust Engine │ Risk Engine  │ Audit Log          │
│ (kernel.py)  │              │ (immutable)        │
├──────────────┴──────────────┴────────────────────┤
│           SQLite (dev) / PostgreSQL (prod)        │
└─────────────────────────────────────────────────┘
```

**Two layers, two files:**
- `kernel.py` — pure trust logic, no dependencies, drop into anything
- `app.py` — full governance platform, REST API, production ready

---

## Why AgentGuard

| | AgentGuard | DIY | Other tools |
|---|---|---|---|
| Trust decay | ✅ | Build it | ❌ |
| Capability tokens | ✅ | Build it | ❌ |
| Human approval gate | ✅ | Build it | Partial |
| Real-time event stream | ✅ | Build it | ❌ |
| Audit trail | ✅ | Build it | Partial |
| Drop-in kernel | ✅ | — | ❌ |
| Open source | ✅ | — | ❌ |
| Setup time | 5 min | Weeks | Days |

---

## Production Deployment

For production swap SQLite for PostgreSQL and add Redis for rate limiting. See `database.py`, `models.py`, and `redis_client.py` in the repo.

```bash
# Set environment variables
export DATABASE_URL=postgresql://user:pass@localhost:5432/agentguard
export REDIS_URL=redis://localhost:6379/0
export JWT_SECRET=your-secret-here

# Run with gunicorn
gunicorn app:app --workers 4 --bind 0.0.0.0:5000
```

---

## Roadmap

- [ ] pip installable package (`pip install agentguard`)
- [ ] Dashboard UI
- [ ] Webhook notifications (Slack, email)
- [ ] Multi-tenant organisations
- [ ] OpenTelemetry integration
- [ ] LangChain / CrewAI native middleware

---

## Contributing

PRs welcome. Open an issue first for major changes.

---

## Licence

MIT — free to use, modify, and build on. See [LICENSE](LICENSE).

---

## Author

**Dheeraj Kumar Biswakarma**

Built while trying to build something else entirely — which is how the best infrastructure gets made.

---

*If AgentGuard saved your team from a 3am incident, give it a ⭐* drop me some $$ as i saved ur ass email me bkdk62309@gmail.com
