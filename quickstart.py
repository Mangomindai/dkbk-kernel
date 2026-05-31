"""
AgentGuard — Quickstart Example
================================
Shows the three most common use cases in under 50 lines.

Before running:
    pip install -r requirements.txt
    python app.py   ← start the server in another terminal

Then run this file:
    python examples/quickstart.py
"""

import requests

BASE_URL = "http://localhost:5000"


# ──────────────────────────────────────────────
# Step 1 — Login and get a token
# ──────────────────────────────────────────────

print("\n1️⃣  Logging in as admin...")
r = requests.post(f"{BASE_URL}/auth/login", json={
    "username": "admin",
    "password": "admin123"
})
token = r.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"   ✅ Token received")


# ──────────────────────────────────────────────
# Step 2 — Give an AI agent a scoped capability
# ──────────────────────────────────────────────

print("\n2️⃣  Granting agent a scoped capability (read-only, 1 hour)...")
r = requests.post(f"{BASE_URL}/capabilities/grant", headers=headers, json={
    "subject":      "my-agent-001",
    "resource_id":  "customer-database",
    "actions":      ["read"],
    "ttl_hours":    1
})
cap = r.json()
print(f"   ✅ Capability granted")
print(f"   JTI:   {cap['jti']}")
print(f"   Token: {cap['capability_token'][:40]}...")


# ──────────────────────────────────────────────
# Step 3 — Check all agent statuses
# ──────────────────────────────────────────────

print("\n3️⃣  Checking agent supervision status...")
r = requests.get(f"{BASE_URL}/supervision/status", headers=headers)
data = r.json()
print(f"   ✅ Total agents tracked: {data['total_agents']}")
for agent in data.get("agents", []):
    print(f"   🤖 {agent['agent_id']} — trust: {agent['trust_score']} — status: {agent['status']}")


# ──────────────────────────────────────────────
# Step 4 — Check pending approvals
# ──────────────────────────────────────────────

print("\n4️⃣  Checking pending approvals...")
r = requests.get(f"{BASE_URL}/approvals/pending", headers=headers)
approvals = r.json().get("approvals", [])
if approvals:
    print(f"   ⚠️  {len(approvals)} approval(s) waiting:")
    for a in approvals:
        print(f"   → {a['agent_id']} wants to {a['action']} — approval id: {a['id']}")
else:
    print(f"   ✅ No pending approvals")


# ──────────────────────────────────────────────
# Step 5 — Use the trust engine directly
# ──────────────────────────────────────────────

print("\n5️⃣  Using the trust engine directly (no API needed)...")
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from kernel import TrustEngine

engine = TrustEngine(db_path="quickstart_demo.db")

# New agent starts TRUSTED
level = engine.get_trust_level("demo-agent")
print(f"   New agent trust level: {level}")

# Agent does something bad
result = engine.apply_penalty("demo-agent", "spam")
print(f"   After spam violation:  {result['new_level']} ({result['new_points']} points)")

# Agent does something bad again
result = engine.apply_penalty("demo-agent", "abuse")
print(f"   After abuse violation: {result['new_level']} ({result['new_points']} points)")

# Agent recovers with good behaviour
engine.upgrade_trust("demo-agent", reason="passed_review")
level = engine.get_trust_level("demo-agent")
print(f"   After good behaviour:  {level}")

# Clean up demo db
os.remove("quickstart_demo.db")


# ──────────────────────────────────────────────
# Done
# ──────────────────────────────────────────────

print("\n" + "─" * 50)
print("✅  AgentGuard is working.")
print("    Docs:   README.md")
print("    Issues: github.com/dheerajkumar/agentguard/issues")
print("─" * 50 + "\n")
