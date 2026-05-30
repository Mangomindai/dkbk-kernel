"""
DKBK v25.3 — Human-AI Delegation Fabric
=========================================
COMPLETE VERSION - All features intact
"""

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from queue import Queue, Empty
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import jwt
import sqlite3
from cachetools import TTLCache
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, Response, g, jsonify, request, stream_with_context

# ============================================================
# CONFIGURATION
# ============================================================

app = Flask(__name__)

os.environ.setdefault("DB_PATH", "control_tower.db")
_KEY_FILE = "private_key.pem"
_TOKEN_TTL_SECONDS = 24 * 3600
_AGENT_INACTIVITY_SECONDS = 300
_MONITOR_INTERVAL_SECONDS = 30
_APPROVAL_TTL_SECONDS = 3600
_SSE_HEARTBEAT_INTERVAL_SECONDS = 30
_SSE_CLIENT_TIMEOUT_SECONDS = 120
_AUTO_BLOCK_TRUST_THRESHOLD = 0.3

TRUST_SUCCESS_BONUS = 0.01
TRUST_FAILURE_PENALTY = -0.05

DEFAULT_RISK_WEIGHTS = {
    "action": {"delete": 30, "transfer": 30, "export": 25, "modify": 20, "read": 5},
    "resource": {"database": 20, "customer": 20, "payment": 20, "user": 15, "config": 15},
    "time_penalty_night": 20,
    "time_penalty_offhours": 10
}

# ============================================================
# LOGGING
# ============================================================

class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from flask import has_request_context
            if has_request_context() and hasattr(g, 'request_id'):
                record.request_id = g.request_id
            else:
                record.request_id = "-"
        except:
            record.request_id = "-"
        return True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dkbk_control_tower")
logger.addFilter(_RequestIdFilter())

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s'))
logger.addHandler(console_handler)

werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.WARNING)

# ============================================================
# KEYS
# ============================================================

def _load_or_generate_private_key() -> ec.EllipticCurvePrivateKey:
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(_KEY_FILE, "wb") as f:
        f.write(pem)
    logger.info("Generated new EC P-256 private key")
    return key

PRIVATE_KEY = _load_or_generate_private_key()
PUBLIC_KEY = PRIVATE_KEY.public_key()

# ============================================================
# DATABASE
# ============================================================

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(os.environ["DB_PATH"], check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def db_read(query: str, args: tuple = (), one: bool = False):
    try:
        with _connect() as conn:
            rows = conn.execute(query, args).fetchall()
            return dict(rows[0]) if one and rows else [dict(r) for r in rows]
    except Exception as e:
        logger.error("DB read error: %s", e)
        return None if one else []

def db_write(query: str, args: tuple = ()) -> bool:
    try:
        with _connect() as conn:
            conn.execute(query, args)
            conn.commit()
        return True
    except Exception as e:
        logger.error("DB write error: %s", e)
        return False

def init_db():
    with sqlite3.connect(os.environ["DB_PATH"]) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, username TEXT UNIQUE,
                password_hash TEXT,
                trust_score REAL DEFAULT 0.5,
                department TEXT DEFAULT 'general',
                org_id TEXT DEFAULT 'default',
                role TEXT DEFAULT 'user',
                principal_type TEXT DEFAULT 'human'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS policies (
                id TEXT PRIMARY KEY, action TEXT, min_trust REAL,
                time_start TEXT, time_end TEXT, department TEXT,
                org_id TEXT DEFAULT 'default', version TEXT, enabled INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY, actor_id TEXT, action TEXT, result TEXT,
                policy_version TEXT, request_id TEXT, org_id TEXT,
                timestamp TEXT, metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS revoked_capabilities (
                jti TEXT PRIMARY KEY, revoked_by TEXT, reason TEXT, revoked_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                agent_id TEXT PRIMARY KEY, principal_type TEXT, capability_jti TEXT,
                start_time REAL, last_action_time REAL, action_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0, trust_score REAL DEFAULT 0.7,
                status TEXT DEFAULT 'active', org_id TEXT DEFAULT 'default',
                created_at TEXT, updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id TEXT PRIMARY KEY, agent_id TEXT, event_type TEXT, action TEXT,
                result TEXT, trust_before REAL, trust_after REAL, flags TEXT,
                timestamp REAL, org_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                id TEXT PRIMARY KEY, agent_id TEXT, tool_name TEXT, params TEXT,
                action TEXT, status TEXT, created_at REAL, expires_at REAL,
                approved_by TEXT, approved_at REAL, org_id TEXT
            )
        """)

        default_policies = [
            ('read', 0.3, '00:00', '23:59', None, 'default', 'v1'),
            ('write', 0.6, '09:00', '17:00', None, 'default', 'v1'),
            ('delete', 0.9, '00:00', '23:59', 'engineering', 'default', 'v1'),
            ('admin', 0.8, '00:00', '23:59', None, 'default', 'v1'),
        ]
        for policy in default_policies:
            conn.execute("INSERT OR IGNORE INTO policies (id, action, min_trust, time_start, time_end, department, org_id, version) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), policy[0], policy[1], policy[2], policy[3], policy[4], policy[5], policy[6]))

        default_users = [
            ('user-alice', 'alice', 'alice123', 0.7, 'engineering', 'user'),
            ('user-bob', 'bob', 'bob123', 0.4, 'sales', 'user'),
            ('user-admin', 'admin', 'admin123', 1.0, 'admin', 'admin'),
        ]
        for uid, uname, pwd, trust, dept, role in default_users:
            pw_hash = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
            conn.execute("INSERT OR IGNORE INTO users (id, username, password_hash, trust_score, department, role) VALUES (?, ?, ?, ?, ?, ?)",
                        (uid, uname, pw_hash, trust, dept, role))

        conn.commit()
        logger.info("DKBK v25.3 database initialized")

# ============================================================
# HELPERS
# ============================================================

def get_user_state(user_id, org_id="default"):
    return db_read("SELECT * FROM users WHERE id = ? AND org_id = ?", (user_id, org_id), one=True)

def audit(actor_id, action, result, policy_version, request_id, org_id="default", metadata=None):
    db_write("INSERT INTO audit_log VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
             (str(uuid.uuid4()), actor_id, action, result, policy_version, request_id, org_id, datetime.now().isoformat(), metadata))

def is_capability_revoked(jti):
    return db_read("SELECT 1 FROM revoked_capabilities WHERE jti = ?", (jti,), one=True) is not None

def revoke_capability(jti, revoked_by, reason, request_id):
    return db_write("INSERT INTO revoked_capabilities VALUES (?, ?, ?, ?)", (jti, revoked_by, reason, datetime.now().isoformat()))

# ============================================================
# POLICY CACHE & ENGINE
# ============================================================

policy_cache = TTLCache(maxsize=256, ttl=300)

def get_policy(action: str, org_id: str = "default") -> Optional[Dict]:
    cache_key = f"{action}:{org_id}"
    if cache_key in policy_cache:
        return policy_cache[cache_key]
    row = db_read("SELECT * FROM policies WHERE action = ? AND org_id = ? AND enabled = 1", (action, org_id), one=True)
    policy_cache[cache_key] = row
    return row

def evaluate_baseline_policy(actor: dict, action: str, env: dict, org_id: str = "default") -> Tuple[bool, str, Optional[str]]:
    policy = get_policy(action, org_id)
    if not policy:
        return False, "Undefined policy", None
    if actor['trust_score'] < policy['min_trust']:
        return False, f"Insufficient trust: {actor['trust_score']} < {policy['min_trust']}", policy.get('version')
    now_str = env['time'].strftime("%H:%M")
    start, end = policy['time_start'], policy['time_end']
    in_window = (start <= now_str <= end) if start <= end else (now_str >= start or now_str <= end)
    if not in_window:
        return False, f"Outside window {start}-{end}", policy.get('version')
    if policy.get('department') and actor.get('department') != policy.get('department'):
        return False, f"Department mismatch: requires {policy.get('department')}", policy.get('version')
    return True, "Authorized", policy.get('version')

def evaluate_decision(actor: dict, action: str, resource: dict, env: dict, org_id: str = "default", capability=None) -> Tuple[bool, str, Optional[str]]:
    authorized, reason, version = evaluate_baseline_policy(actor, action, env, org_id)
    if capability and capability.is_valid():
        if capability.subject == actor['id'] and resource.get('id') == capability.resource_id and action in capability.actions:
            return True, "Authorized via Capability", version
    return authorized, reason, version

# ============================================================
# RISK ENGINE
# ============================================================

class RiskEngine:
    @classmethod
    def get_weights(cls, org_id: str = "default"):
        return DEFAULT_RISK_WEIGHTS

    @classmethod
    def calculate_risk(cls, actor: dict, action: str, resource: dict, tool_name: str, org_id: str = "default") -> Tuple[int, str]:
        weights = cls.get_weights(org_id)
        risk = (1.0 - actor.get("trust_score", 0.5)) * 30
        action_lower = action.lower()
        for k, pts in weights["action"].items():
            if k in action_lower:
                risk += pts
                break
        tool_lower = tool_name.lower()
        for k, pts in weights["resource"].items():
            if k in tool_lower:
                risk += pts
                break
        hour = datetime.now().hour
        if hour < 6 or hour > 20:
            risk += weights["time_penalty_night"]
        elif hour < 8 or hour > 18:
            risk += weights["time_penalty_offhours"]
        risk_int = min(int(risk), 100)
        level = "critical" if risk_int >= 70 else "medium" if risk_int >= 30 else "low"
        return risk_int, level

# ============================================================
# CAPABILITY CLASS
# ============================================================

class Capability:
    def __init__(self, issuer, subject, resource_id, actions, expires_at, org_id="default", jti=None, constraints=None):
        self.issuer = issuer
        self.subject = subject
        self.resource_id = resource_id
        self.actions = actions
        self.expires_at = expires_at
        self.org_id = org_id
        self.jti = jti or str(uuid.uuid4())
        self.constraints = constraints or {}
        self.token_type = "capability"

    def to_token(self):
        return jwt.encode({
            "typ": self.token_type, "iss": self.issuer, "sub": self.subject,
            "res": self.resource_id, "act": self.actions, "org": self.org_id,
            "exp": self.expires_at, "jti": self.jti, "constraints": self.constraints,
        }, PRIVATE_KEY, algorithm='ES256')

    @staticmethod
    def from_token(token):
        if not token:
            return None
        try:
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=['ES256'])
            if payload.get('typ') != "capability":
                return None
            return Capability(
                issuer=payload['iss'], subject=payload['sub'],
                resource_id=payload['res'], actions=payload['act'],
                expires_at=payload['exp'], org_id=payload.get('org', 'default'),
                jti=payload['jti'], constraints=payload.get('constraints', {}),
            )
        except Exception:
            return None

    def is_valid(self):
        if self.expires_at < datetime.now(timezone.utc).timestamp():
            return False
        if is_capability_revoked(self.jti):
            return False
        return True

# ============================================================
# APPROVAL GATE
# ============================================================

class ApprovalGate:
    SENSITIVE_ACTIONS = {
        "delete": ["database", "records", "users", "data"],
        "transfer": ["money", "funds", "payment", "balance"],
        "modify": ["permissions", "policies", "config", "settings"],
        "export": ["customers", "users", "emails", "personal"],
    }

    @classmethod
    def needs_approval(cls, tool_name: str, params: dict, principal_type: str) -> bool:
        if principal_type == "copilot":
            return True
        for action, keywords in cls.SENSITIVE_ACTIONS.items():
            if any(k in tool_name.lower() for k in keywords):
                return True
        return False

    @classmethod
    def create_request(cls, agent_id, tool_name, params, action, org_id) -> dict:
        req_id = str(uuid.uuid4())
        now = time.time()
        db_write("""
            INSERT INTO approval_requests (id, agent_id, tool_name, params, action, status, created_at, expires_at, org_id)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """, (req_id, agent_id, tool_name, json.dumps(params), action, now, now + _APPROVAL_TTL_SECONDS, org_id))
        return {"id": req_id, "status": "pending", "expires_at": now + _APPROVAL_TTL_SECONDS}

    @classmethod
    def approve(cls, request_id, approved_by, org_id) -> bool:
        return db_write("""
            UPDATE approval_requests SET status = 'approved', approved_by = ?, approved_at = ?
            WHERE id = ? AND org_id = ? AND status = 'pending' AND expires_at > ?
        """, (approved_by, time.time(), request_id, org_id, time.time()))

    @classmethod
    def get_pending_approvals(cls, org_id) -> list:
        return db_read("SELECT * FROM approval_requests WHERE org_id = ? AND status = 'pending' AND expires_at > ? ORDER BY created_at ASC", (org_id, time.time()))

# ============================================================
# SUPERVISION ENGINE
# ============================================================

class SupervisionEngine:
    def __init__(self):
        self._lock = threading.RLock()
    
    def record_agent_event(self, agent_id, event_type, action, result, trust_before, trust_after, org_id, flags=None):
        db_write("INSERT INTO agent_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (str(uuid.uuid4()), agent_id, event_type, action, result, trust_before, trust_after, flags, time.time(), org_id))
        publish_event("agent.event", {
            "agent_id": agent_id,
            "event_type": event_type,
            "trust_after": trust_after,
            "action": action,
            "result": result
        }, org_id)
    
    def update_agent_trust(self, agent_id, result, org_id):
        session = db_read("SELECT trust_score FROM agent_sessions WHERE agent_id = ? AND org_id = ?", (agent_id, org_id), one=True)
        if not session:
            return
        trust_before = session['trust_score']
        if result == 'success':
            trust_after = min(1.0, trust_before + TRUST_SUCCESS_BONUS)
        else:
            trust_after = max(0.0, trust_before + TRUST_FAILURE_PENALTY)
        db_write("UPDATE agent_sessions SET trust_score = ?, updated_at = ? WHERE agent_id = ? AND org_id = ?",
                 (trust_after, datetime.now().isoformat(), agent_id, org_id))
        self.record_agent_event(agent_id, "TRUST_UPDATE", None, result, trust_before, trust_after, org_id)
        if trust_after < _AUTO_BLOCK_TRUST_THRESHOLD:
            self.block_agent(agent_id, "Trust score dropped below threshold", org_id)
        return trust_after
    
    def register_agent(self, agent_id, principal_type, capability_jti, trust_score, org_id):
        now = time.time()
        db_write("INSERT OR REPLACE INTO agent_sessions (agent_id, principal_type, capability_jti, start_time, last_action_time, trust_score, org_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (agent_id, principal_type, capability_jti, now, now, trust_score, org_id, datetime.now().isoformat(), datetime.now().isoformat()))
        self.record_agent_event(agent_id, "REGISTERED", None, None, trust_score, trust_score, org_id)
        publish_event("agent.registered", {"agent_id": agent_id, "trust_score": trust_score}, org_id)
    
    def block_agent(self, agent_id, reason, org_id):
        db_write("UPDATE agent_sessions SET status = 'blocked' WHERE agent_id = ? AND org_id = ?", (agent_id, org_id))
        self.record_agent_event(agent_id, "BLOCKED", None, None, 0, 0, org_id, reason)
        publish_event("agent.blocked", {"agent_id": agent_id, "reason": reason}, org_id)

    def pause_agent(self, agent_id, org_id):
        db_write("UPDATE agent_sessions SET status = 'paused' WHERE agent_id = ? AND org_id = ?", (agent_id, org_id))
        self.record_agent_event(agent_id, "PAUSED", None, None, 0, 0, org_id)
        publish_event("agent.paused", {"agent_id": agent_id}, org_id)

    def resume_agent(self, agent_id, org_id):
        db_write("UPDATE agent_sessions SET status = 'active' WHERE agent_id = ? AND org_id = ?", (agent_id, org_id))
        self.record_agent_event(agent_id, "RESUMED", None, None, 0, 0, org_id)
        publish_event("agent.resumed", {"agent_id": agent_id}, org_id)

    def pause_all_agents(self, org_id):
        db_write("UPDATE agent_sessions SET status = 'paused' WHERE org_id = ? AND status = 'active'", (org_id,))
        publish_event("global.pause", {"org_id": org_id}, org_id)

    def get_agent_status(self, agent_id, org_id):
        return db_read("SELECT * FROM agent_sessions WHERE agent_id = ? AND org_id = ?", (agent_id, org_id), one=True)

    def get_all_status(self, org_id):
        agents = db_read("SELECT agent_id, principal_type, status, trust_score, action_count, failure_count FROM agent_sessions WHERE org_id = ?", (org_id,))
        return {"total_agents": len(agents), "agents": agents}
    
    def get_agent_timeline(self, agent_id, org_id):
        return db_read("SELECT * FROM agent_events WHERE agent_id = ? AND org_id = ? ORDER BY timestamp ASC", (agent_id, org_id))

supervision = SupervisionEngine()

# ============================================================
# EVENT STREAM
# ============================================================

event_stream_clients: Dict[str, List[Queue]] = {}

@app.route('/events', methods=['GET'])
def sse_events():
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    if not token:
        return jsonify({"error": "No token"}), 401
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=['ES256'])
        org_id = payload.get('org', 'default')
    except:
        return jsonify({"error": "Invalid token"}), 401

    def generate():
        q = Queue()
        if org_id not in event_stream_clients:
            event_stream_clients[org_id] = []
        event_stream_clients[org_id].append(q)
        try:
            yield f"data: {json.dumps({'type': 'connected', 'org_id': org_id})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield f"data: {msg}\n\n"
                except Empty:
                    yield ": heartbeat\n\n"
        finally:
            if org_id in event_stream_clients:
                try:
                    event_stream_clients[org_id].remove(q)
                except ValueError:
                    pass
    return Response(stream_with_context(generate()), mimetype="text/event-stream")

def publish_event(event_type: str, data: dict, org_id: str):
    message = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    if org_id in event_stream_clients:
        for q in event_stream_clients[org_id]:
            try:
                q.put_nowait(message)
            except:
                pass

# ============================================================
# AUTHENTICATION
# ============================================================

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "")
        if not token:
            return jsonify({"error": "No token"}), 401
        try:
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=['ES256'])
            g.current_user_id = payload.get('sub')
            g.current_org_id = payload.get('org', 'default')
            g.current_user_role = payload.get('role', 'user')
            g.request_id = str(uuid.uuid4())
        except:
            return jsonify({"error": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        user = get_user_state(g.current_user_id, g.current_org_id)
        if not user or user.get('role') != 'admin':
            return jsonify({"error": "Admin required"}), 403
        return f(*args, **kwargs)
    return decorated

# ============================================================
# SAFE TOOL RUNNER
# ============================================================

def tool_add(params): return {"result": params["a"] + params["b"]}
def tool_subtract(params): return {"result": params["a"] - params["b"]}
def tool_multiply(params): return {"result": params["a"] * params["b"]}
def tool_divide(params):
    if params["b"] == 0:
        return {"error": "Division by zero"}
    return {"result": params["a"] / params["b"]}
def tool_uppercase(params): return {"result": params["text"].upper()}
def tool_lowercase(params): return {"result": params["text"].lower()}
def tool_reverse(params): return {"result": params["text"][::-1]}
def tool_length(params): return {"result": len(params["text"])}
def tool_echo(params): return {"result": params.get("message", "")}
def tool_json_parse(params):
    try:
        return {"result": json.loads(params["json_string"])}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {str(e)}"}
def tool_get_agent_status(params, db, org_id, actor_id):
    agent = db_read("SELECT status, trust_score FROM agent_sessions WHERE agent_id = ? AND org_id = ?", (params.get("agent_id"), org_id), one=True)
    return {"result": agent} if agent else {"error": "Agent not found"}
def tool_update_agent_trust(params, db, org_id, actor_id):
    new_trust = params.get("trust_score")
    if new_trust is None or not (0 <= new_trust <= 1):
        return {"error": "trust_score must be between 0 and 1"}
    db_write("UPDATE agent_sessions SET trust_score = ? WHERE agent_id = ? AND org_id = ?", (new_trust, params.get("agent_id"), org_id))
    return {"result": f"Agent {params.get('agent_id')} trust updated to {new_trust}"}

TOOL_REGISTRY = {
    "add": {"func": tool_add, "needs_db": False, "needs_auth": False},
    "subtract": {"func": tool_subtract, "needs_db": False, "needs_auth": False},
    "multiply": {"func": tool_multiply, "needs_db": False, "needs_auth": False},
    "divide": {"func": tool_divide, "needs_db": False, "needs_auth": False},
    "uppercase": {"func": tool_uppercase, "needs_db": False, "needs_auth": False},
    "lowercase": {"func": tool_lowercase, "needs_db": False, "needs_auth": False},
    "reverse": {"func": tool_reverse, "needs_db": False, "needs_auth": False},
    "length": {"func": tool_length, "needs_db": False, "needs_auth": False},
    "echo": {"func": tool_echo, "needs_db": False, "needs_auth": False},
    "json_parse": {"func": tool_json_parse, "needs_db": False, "needs_auth": False},
    "get_agent_status": {"func": tool_get_agent_status, "needs_db": True, "needs_auth": True},
    "update_agent_trust": {"func": tool_update_agent_trust, "needs_db": True, "needs_auth": True},
}

def dispatch_tool(tool_name, params, db=None, org_id=None, actor_id=None):
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}"}
    tool_info = TOOL_REGISTRY[tool_name]
    if tool_info["needs_auth"] and (not org_id or not actor_id):
        return {"error": f"Tool '{tool_name}' requires authentication"}
    try:
        if tool_info["needs_db"]:
            result = tool_info["func"](params, db, org_id, actor_id)
        else:
            result = tool_info["func"](params)
        return result
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}

@app.route('/tools/run', methods=['POST'])
@require_auth
def run_tool():
    data = request.json
    tool_name = data.get('tool_name')
    params = data.get('params', {})
    if not tool_name:
        return jsonify({"error": "tool_name required"}), 400
    result = dispatch_tool(tool_name, params, None, g.current_org_id, g.current_user_id)
    audit(g.current_user_id, f"tool_{tool_name}", "SUCCESS" if "error" not in result else "FAILED", None, str(uuid.uuid4()), g.current_org_id, f"params={json.dumps(params)}")
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

# ============================================================
# API ENDPOINTS
# ============================================================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "version": "v25.3", "features": ["abac", "trust_decay", "capabilities", "approvals", "sse", "safe_tools"]})

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user = db_read("SELECT * FROM users WHERE username = ?", (username,), one=True)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    if not bcrypt.checkpw(password.encode(), user['password_hash'].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    token = jwt.encode({
        "sub": user['id'], "username": user['username'], "role": user.get('role', 'user'),
        "org": user.get('org_id', 'default'), "exp": datetime.now(timezone.utc).timestamp() + _TOKEN_TTL_SECONDS
    }, PRIVATE_KEY, algorithm='ES256')
    return jsonify({"token": token, "user": {"id": user['id'], "username": user['username'], "role": user.get('role', 'user')}})

@app.route('/capabilities/grant', methods=['POST'])
@require_admin
def grant_capability():
    data = request.json
    cap = Capability(
        issuer=g.current_user_id, subject=data['subject'],
        resource_id=data['resource_id'], actions=data['actions'],
        expires_at=datetime.now(timezone.utc).timestamp() + (data.get('ttl_hours', 1) * 3600),
        org_id=g.current_org_id,
        constraints=data.get('constraints', {})
    )
    principal_type = data.get('principal_type', 'agent')
    if principal_type in ['agent', 'workflow', 'scheduled_job']:
        supervision.register_agent(data['subject'], principal_type, cap.jti, 0.7, g.current_org_id)
    publish_event("capability.granted", {"subject": data['subject'], "resource": data['resource_id'], "actions": data['actions']}, g.current_org_id)
    return jsonify({"capability_token": cap.to_token(), "jti": cap.jti})

@app.route('/resources/<resource_id>', methods=['GET'])
@require_auth
def get_resource(resource_id):
    cap_header = request.headers.get("X-Capability", "")
    capability = Capability.from_token(cap_header) if cap_header else None
    actor = get_user_state(g.current_user_id, g.current_org_id)
    authorized, reason, version = evaluate_decision(actor, "read", {"id": resource_id}, {"time": datetime.now()}, g.current_org_id, capability)
    if not authorized:
        return jsonify({"error": reason}), 403
    if actor.get('principal_type') in ['agent', 'workflow', 'scheduled_job']:
        supervision.update_agent_trust(g.current_user_id, "success", g.current_org_id)
    audit(g.current_user_id, "read_resource", "ALLOWED", version, str(uuid.uuid4()), g.current_org_id, f"resource={resource_id}")
    return jsonify({"resource_id": resource_id, "message": "Access granted", "authorized_via": "capability" if capability else "policy"})

@app.route('/agents/<agent_id>/action', methods=['POST'])
@require_auth
def agent_action(agent_id):
    data = request.json
    action_name = data.get('action')
    result = data.get('result', 'success')
    actor = get_user_state(g.current_user_id, g.current_org_id)
    if actor.get('principal_type') not in ['agent', 'workflow', 'scheduled_job']:
        return jsonify({"error": "Only agents can record actions"}), 403
    new_trust = supervision.update_agent_trust(g.current_user_id, result, g.current_org_id)
    audit(g.current_user_id, action_name, result.upper(), None, str(uuid.uuid4()), g.current_org_id, f"trust={new_trust}")
    return jsonify({"agent_id": agent_id, "action": action_name, "result": result, "new_trust_score": new_trust})

@app.route('/supervision/status', methods=['GET'])
@require_admin
def supervision_status():
    return jsonify(supervision.get_all_status(g.current_org_id))

@app.route('/supervision/agent/<agent_id>/timeline', methods=['GET'])
@require_admin
def agent_timeline(agent_id):
    timeline = supervision.get_agent_timeline(agent_id, g.current_org_id)
    return jsonify({"agent_id": agent_id, "timeline": timeline})

@app.route('/supervision/agent/<agent_id>/pause', methods=['POST'])
@require_admin
def pause_agent(agent_id):
    supervision.pause_agent(agent_id, g.current_org_id)
    return jsonify({"message": f"Agent {agent_id} paused"})

@app.route('/supervision/agent/<agent_id>/resume', methods=['POST'])
@require_admin
def resume_agent(agent_id):
    supervision.resume_agent(agent_id, g.current_org_id)
    return jsonify({"message": f"Agent {agent_id} resumed"})

@app.route('/supervision/agent/<agent_id>/block', methods=['POST'])
@require_admin
def block_agent(agent_id):
    reason = request.json.get('reason', 'Manual block')
    supervision.block_agent(agent_id, reason, g.current_org_id)
    return jsonify({"message": f"Agent {agent_id} blocked"})

@app.route('/supervision/global/pause', methods=['POST'])
@require_admin
def global_pause():
    supervision.pause_all_agents(g.current_org_id)
    return jsonify({"message": "ALL AGENTS PAUSED"})

@app.route('/audit', methods=['GET'])
@require_admin
def get_audit():
    # FIX: was truncated — `events = db_read` with no query
    limit  = min(int(request.args.get('limit', 100)), 1000)
    events = db_read(
        "SELECT * FROM audit_log WHERE org_id = ? ORDER BY timestamp DESC LIMIT ?",
        (g.current_org_id, limit)
    )
    return jsonify({"events": events, "count": len(events)})


# ============================================================
# MISSING ENDPOINTS — approvals + capability revoke
# ============================================================

@app.route('/approvals/pending', methods=['GET'])
@require_admin
def get_pending_approvals():
    approvals = ApprovalGate.get_pending_approvals(g.current_org_id)
    return jsonify({"approvals": approvals, "count": len(approvals)})


@app.route('/approvals/<approval_id>/approve', methods=['POST'])
@require_admin
def approve_action(approval_id):
    result = ApprovalGate.approve(approval_id, g.current_user_id, g.current_org_id)
    if result:
        publish_event("approval.approved", {
            "approval_id": approval_id,
            "approved_by": g.current_user_id
        }, g.current_org_id)
        audit(g.current_user_id, "approve_action", "SUCCESS", None,
              str(uuid.uuid4()), g.current_org_id, f"approval_id={approval_id}")
        return jsonify({"status": "approved", "approval_id": approval_id})
    return jsonify({"error": "Approval not found or already processed"}), 404


@app.route('/approvals/<approval_id>/deny', methods=['POST'])
@require_admin
def deny_action(approval_id):
    reason = (request.json or {}).get('reason', 'Denied by admin')
    db_write(
        "UPDATE approval_requests SET status = 'denied' WHERE id = ? AND org_id = ? AND status = 'pending'",
        (approval_id, g.current_org_id)
    )
    publish_event("approval.denied", {
        "approval_id": approval_id,
        "denied_by":   g.current_user_id,
        "reason":      reason
    }, g.current_org_id)
    audit(g.current_user_id, "deny_action", "SUCCESS", None,
          str(uuid.uuid4()), g.current_org_id, f"approval_id={approval_id}")
    return jsonify({"status": "denied", "approval_id": approval_id})


@app.route('/capabilities/revoke', methods=['POST'])
@require_admin
def revoke_cap():
    data   = request.json or {}
    jti    = data.get('jti')
    reason = data.get('reason', 'Manually revoked')
    if not jti:
        return jsonify({"error": "jti required"}), 400
    revoke_capability(jti, g.current_user_id, reason, str(uuid.uuid4()))
    publish_event("capability.revoked", {"jti": jti, "reason": reason}, g.current_org_id)
    audit(g.current_user_id, "revoke_capability", "SUCCESS", None,
          str(uuid.uuid4()), g.current_org_id, f"jti={jti}")
    return jsonify({"status": "revoked", "jti": jti})


if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("🚀 DKBK v25.3 STARTING...")
    print("="*50)
    print("📍 http://localhost:5000")
    print("📍 Health: http://localhost:5000/health")
    print("\n📝 Default users: admin/admin123, alice/alice123, bob/bob123")
    print("="*50 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)