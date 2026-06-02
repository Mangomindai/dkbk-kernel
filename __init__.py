"""
AgentGuard — Constitutional Governance Kernel for AI Agents
============================================================
"Your AI agents are only as safe as the system governing them."

Usage:
    from agentguard import TrustEngine

    engine = TrustEngine(db_path="trust.db")
    level = engine.get_trust_level("my-agent-001")
    engine.apply_penalty("my-agent-001", "spam")
    engine.upgrade_trust("my-agent-001", reason="passed_review")
"""

from .kernel import TrustEngine

__version__ = "0.1.0"
__author__ = "Dheeraj Kumar Biswakarma"
__email__ = "bkdk62309@gmail.com"
__license__ = "MIT"

__all__ = ["TrustEngine"]
