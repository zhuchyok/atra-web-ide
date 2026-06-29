"""
Extracted helpers from expert_worker.py (process_task, worker_loop).
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def extract_source_attribution(metadata: dict) -> List[Dict[str, str]]:
    """Extract source attributions from task metadata."""
    md = metadata if isinstance(metadata, dict) else {}
    candidates: List[Dict[str, str]] = []

    def _push(source_type: str, source_ref: str, note: str = ""):
        if not source_ref:
            return
        candidates.append({
            "source_type": source_type,
            "source_ref": str(source_ref)[:256],
            "note": str(note)[:256] if note else "",
        })

    for key in ("source_refs", "sources", "citations", "knowledge_node_ids", "knowledge_ids"):
        val = md.get(key, md.get(f"metadata_{key}", []))
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    _push(item.get("type", "unknown"), item.get("ref", item.get("id", "")),
                          item.get("note", item.get("snippet", "")))
                elif isinstance(item, str):
                    _push("knowledge_node" if "node" in key else "source", item)
        elif isinstance(val, str):
            _push(key, val)

    rag_nodes = md.get("rag_nodes", md.get("knowledge_context", []))
    if isinstance(rag_nodes, list):
        for node in rag_nodes:
            nid = node.get("id") or node.get("node_id") or ""
            snippet = node.get("snippet", node.get("content", ""))[:200]
            if nid:
                _push("rag_node", nid, snippet)

    return candidates


async def run_monster_audits(description: str, metadata: dict) -> Optional[str]:
    """Run monster-specific security audits."""
    try:
        from expert_worker import _run_monster_pip_runtime_audit, _run_monster_secret_header_audit
        pip_report = await _run_monster_pip_runtime_audit(description, metadata)
        if pip_report:
            return pip_report
        secret_report = await _run_monster_secret_header_audit(description, metadata)
        if secret_report:
            return secret_report
    except Exception as e:
        logger.debug(f"Monster audits skipped: {e}")
    return None


def build_contract_trace(contract: dict) -> dict:
    """Build contract enforcement trace from task contract."""
    if not isinstance(contract, dict):
        contract = {}
    return {
        "version": str(contract.get("version") or "1"),
        "intent": contract.get("intent") or "execute_assigned_task",
        "output_schema": contract.get("output_schema") or "expert_response_v1",
        "risk_level": contract.get("risk_level") or "medium",
        "audit_required": bool(contract.get("audit_required", False)),
    }
