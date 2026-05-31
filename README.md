**Constitutional Governance Kernel for AI Agents**

> *"Your AI agents are only as safe as the system governing them."*

> *"If your agent can break AgentGuard, it better be good at breaking Bitcoin."*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)

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
pip install agentguard
```

```python
from agentguard import TrustEngine

engine = TrustEngine(db_path="trust.db")

# New agent starts TRUSTED
level = engine.get_trust_level("my-agent-001")
print(level)  # → TRUSTED

# Agent does something bad
result = engine.apply_penalty("my-agent-001", "spam")
print(result)  # → {"new_points": 20, "new_level": "LIMITED"}

# Agent does something bad again
result = engine.apply_penalty("my-agent-001", "abuse")
print(result)  # → {"new_points": 50, "new_level": "OBSERVED"}

# Agent recovers with good behaviour
engine.upgrade_trust("my-agent-001", reason="passed_review")

# Get full history
history = engine.get_history("my-agent-001")
```

---

## Trust Engine (kernel.py)

The trust engine is a standalone module — use it without the full API if you prefer.

```python
from agentguard import TrustEngine

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
│         AgentGuard Kernel (kernel.py)            │
│    Trust Engine │ Risk Scoring │ Audit Log       │
├─────────────────────────────────────────────────┤
│              SQLite (default)                    │
│         PostgreSQL (Enterprise)                  │
└─────────────────────────────────────────────────┘
```

`kernel.py` — pure trust logic, no dependencies, drop into any project in 5 minutes.

Full REST API with approval gates, capability tokens, and real-time monitoring available in Enterprise Edition.

---

## Community vs Enterprise

| Feature | Community | Enterprise |
|---------|-----------|------------|
| Trust Engine | ✅ Free | ✅ |
| Violation tracking | ✅ Free | ✅ |
| Appeals system | ✅ Free | ✅ |
| Up to 3 agents | ✅ Free | ✅ |
| REST API | ❌ | ✅ |
| JWT Authentication | ❌ | ✅ |
| Capability tokens | ❌ | ✅ |
| Human approval gate | ❌ | ✅ |
| Risk engine (0-100 scoring) | ❌ | ✅ |
| Real-time event stream | ❌ | ✅ |
| Full audit trail | ❌ | ✅ |
| Agent supervision dashboard | ❌ | ✅ |
| Global pause — stop all agents | ❌ | ✅ |
| Multi-tenant organisations | ❌ | ✅ |
| PostgreSQL + Redis | ❌ | ✅ |
| SSO / SAML | ❌ | ✅ |
| Unlimited agents | ❌ | ✅ |
| Webhook notifications | ❌ | ✅ |
| SLA | ❌ | ✅ |
| Setup and onboarding call | ❌ | ✅ |
| Priority support | ❌ | ✅ |
| Support | Community | 24hr response |
| Price | Free | $99-999/month |

---

## Enterprise Edition — What You Get

**Authentication & Security**
Every request is authenticated with JWT tokens. Passwords hashed with bcrypt. Every capability cryptographically signed with Ed25519. If your agent can break it — it better be good at breaking Bitcoin.

**Capability Tokens**
Agents don't get broad API keys. They get scoped, time-limited, signed tokens. `agent-001` can only READ `customer-database` for the next 1 hour. Nothing else. Token expires. Access gone. Automatically.

**Human Approval Gate**
Your agent wants to delete a database. Transfer funds. Export customer data. AgentGuard pauses it automatically. Notifies a human. Waits for approval or denial. Nothing proceeds without sign-off. Your 3am disaster never happens.

**Risk Engine**
Every action scored 0–100 in real time. Delete + database + 3am = 95/100. Read + config + 9am = 12/100. Critical risk means hard stop. Medium risk means approval required. You set the thresholds.

**Real-time Dashboard**
Watch your agents act in real time. Trust scores changing live. Approvals appearing instantly. Block any agent with one click. Pause ALL agents globally with one API call. Your enterprise client can watch too.

**Full Audit Trail**
Every action. Every decision. Every trust change. Immutably logged forever. Actor, timestamp, policy version, outcome. Your enterprise client asks what your AI did last Tuesday at 3pm — you show them exactly.

**Global Emergency Stop**
One API call. All agents paused. Instantly. No matter how many. No matter where they are. When something goes wrong you stop everything first and ask questions second.

**Multi-tenant**
Run AgentGuard for multiple teams or clients on one deployment. Company A cannot see Company B. Each organisation has its own agents, policies, audit trail, and capabilities.

---

## Pricing

| Tier | Agents | Price | Best for |
|------|--------|-------|----------|
| Community | Up to 3 | Free | Trying it out |
| Startup | Up to 10 | $99/month | Early stage startups |
| Growth | Up to 50 | $299/month | Scaling teams |
| Enterprise | Unlimited | $999/month | Production deployments |

All paid tiers include setup call, priority support, and SLA.

📧 Email to get started — response within 24 hours.

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

## Contact

**Dheeraj Kumar Biswakarma**
📧 bkdk62309@gmail.com
🐙 github.com/Mangomindai/agentguard

For enterprise enquiries, integration support, or custom features — email directly. Response within 24 hours.

---

## Author

Built while trying to build something else entirely — which is how the best infrastructure gets made.

---

*If AgentGuard saved your team from a 3am incident, give it a ⭐*
