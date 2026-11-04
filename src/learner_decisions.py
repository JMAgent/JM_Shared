"""The decisions you implement.

The graph is already wired. Finish these functions so each check stays in
application code, not in the model. Keep the function names and the failure
codes exactly as written. Use contracts.failed(...) for every failure.
"""
from .contracts import Settings, failed


def load_settings(values: dict | None = None) -> Settings:
    """Build Settings from a dictionary.

    Reject max_model_calls below 1 with ValueError whose message contains
    "at least 1". A zero-call setting must fail before any workflow starts.
    Missing keys keep the Settings defaults: 3 calls, 6000 token budget,
    2000 tokens reserved per call, and a 900 second approval window.
    """
    if values["max_model_calls"] < 1:
        raise ValueError("at least 1")
    elif values is None:
        return Settings(
                    max_model_calls=3, 
                    total_token_budget=  6000,
                    reserve_tokens= 2000,  
                    approval_ttl_seconds= 900)
    else :
        return Settings(
                    max_model_calls=values.get("max_model_calls"), 
                    total_token_budget=  6000,
                    reserve_tokens=  2000,  
                    approval_ttl_seconds=  900)


def check_access(principal, tenant_id: str):
    """Return None when this identity may read the case.

    Refuse with failed("ACCESS_DENIED", ...) when the principal's tenant_id
    differs from tenant_id, or when "case:read" is missing from permissions.
    A viewer and another company's employee both stop here, before any model call.
    """
    if (principal.tenant_id != tenant_id) or ("case:read" not in principal.permissions):
        return (failed (
            "ACCESS_DENIED", "You are not allowed to read this case.",
             "Please check your permissions and tenant."
             )
             )
    elif (principal.tenant_id == tenant_id) and ("case:read" in principal.permissions) :
        return None 
    

def reserve_call(state: dict, settings: Settings) -> dict:
    """Admit one model call, or stop with a typed failure.

    Read model_calls and reserved_tokens from state. Missing values mean 0.

    If model_calls is already at settings.max_model_calls, return
    failed("ITERATION_LIMIT", ...). Do not increment the counters.

    If reserved_tokens + settings.reserve_tokens would pass
    settings.total_token_budget, return failed("TOKEN_BUDGET", ...).
    Do not increment the counters.

    Otherwise return a partial update:
    model_calls increased by 1, reserved_tokens increased by
    settings.reserve_tokens, and status "planning".
    """
    model_calls = state.get("model_calls", 0)
    reserved_tokens = state.get("reserved_tokens", 0)

    if model_calls >= settings.max_model_calls:
        return failed(
            "ITERATION_LIMIT",
            f"Model calls {model_calls} reached the limit of {settings.max_model_calls}."
            #"Please check your settings.",
            #"False"
        )
    if reserved_tokens + settings.reserve_tokens > settings.total_token_budget:
        return failed(
            "TOKEN_BUDGET",
            f"Reserved tokens {reserved_tokens} plus reserve {settings.reserve_tokens} exceeds total token budget {settings.total_token_budget}."
            #,"Please check your settings.",      
            #"False"
        )
    return {
        "model_calls": model_calls + 1,
        "reserved_tokens": reserved_tokens + settings.reserve_tokens,
        "status": "planning"
    }


def validate_proposal(evidence: dict, proposal: dict):
    """Return None when the proposal may be shown to a manager.

    The model drafts the summary. Your code checks the facts.

    Return failed("EVIDENCE_MISMATCH", ...) unless all of these are true:
    - proposal["action"] is exactly "create_review_task"
    - proposal["case_id"] equals evidence["case_id"]
    - proposal["invoice_id"] equals evidence["invoice_id"]
    - both of those identifiers appear in proposal["evidence_refs"]

    A convincing summary cannot replace a matching invoice id.
    """
    if (proposal["action"] == "create_review_task") and (proposal["case_id"] == evidence["case_id"]) and (proposal["invoice_id"] == evidence["invoice_id"]) and (proposal["case_id"] in proposal["evidence_refs"] and proposal["invoice_id"] in proposal["evidence_refs"]):
            return None
    else:
        return failed(
            "EVIDENCE_MISMATCH",
            "The proposal does not match the evidence."
            #,"Please check the proposal and evidence.",
            #"False"
        )


def approval_decision(principal, reply: dict, expected_hash: str, now: int, expires_at: int, tenant_id: str) -> dict:
    """Decide what the current person is allowed to do with this exact proposal.

    Check in this order:

    1. reply["approved"] must be a real boolean. The string "yes" is not enough.
       Return {"ok": False, "failure": failed("INVALID_APPROVAL", ...)}.
    2. reply["proposal_hash"] must equal expected_hash.
       Return {"ok": False, "failure": failed("STALE_APPROVAL", ...)}.
    3. principal.permissions must include "task:approve", and
       principal.tenant_id must equal tenant_id.
       Return {"ok": False, "failure": failed("APPROVAL_FORBIDDEN", ...)}.
       The approver comes from the current principal, never from model text.
    4. If now >= expires_at, return
       {"ok": False, "failure": failed("APPROVAL_EXPIRED", ...)}.
    5. If approved is True, return
       {"ok": True, "decision": "approved", "approved_by": principal.subject}.
    6. If approved is False, return {"ok": True, "decision": "rejected"}.
    """
    if not isinstance(reply.get("approved"), bool):
        return {"ok": False, "failure": failed(
            "INVALID_APPROVAL",
            "The approval value must be a boolean."
            #,"Please provide a valid approval value.",
            #"False"
        )}
    if reply.get("proposal_hash") != expected_hash:
        return {"ok": False, "failure": failed(
            "STALE_APPROVAL",
            "The proposal hash does not match the expected hash."
            #,"Please check the proposal hash.",
            #"False"
        )}
    if ("task:approve" not in principal.permissions) or (principal.tenant_id != tenant_id):
        return {"ok": False, "failure": failed(
            "APPROVAL_FORBIDDEN",
            "You do not have permission to approve this task."
            #,"Please check your permissions and tenant.",
            #"False"
        )}
    if now >= expires_at:
        return {"ok": False, "failure": failed(
            "APPROVAL_EXPIRED",
            "The approval has expired."
            #,"Please request a new approval.",
            #"False"
        )}
    if reply.get("approved") is True:
        return {"ok": True, "decision": "approved", "approved_by": principal.subject}
    else:
        return {"ok": True, "decision": "rejected"}


def action_key(tenant_id: str, request_id: str, proposal_hash: str) -> str:
    """Stable identity for one approved action.

    Return tenant_id, request_id, and proposal_hash joined by colons:
    "acme-in:request-1:<64-character hash>".
    The same proposal must keep the same key after a restart.
    """
    return (f"{tenant_id}:{request_id}:{proposal_hash}")


class TaskLedger:
    """In-memory stand-in for the external task system."""

    def __init__(self):
        self._rows: dict[str, dict] = {}

    def create(self, key: str, payload: dict) -> dict:
        """Create one task, or return the receipt that already exists for key.

        Same key and same payload: return the original receipt. Do not add a row.
        Same key and a different payload: raise ValueError. The message must
        contain "payload".
        New key: store a copy of payload and return
        {"action_key": key, "task_id": "TASK-1"} for the first task,
        "TASK-2" for the second, and so on.
        """
        if key in self._rows:
            if self._rows[key] == payload:
                return {"action_key": key, "task_id": f"TASK-{len(self._rows)}"}
            else:
                raise ValueError("payload")
        else:
            self._rows[key] = payload.copy()
            return {"action_key": key, "task_id": f"TASK-{len(self._rows)}"}

    def all(self) -> list[dict]:
        """Return the receipts in insertion order."""
        return [{"action_key": k, "task_id": f"TASK-{i+1}"} for i, k in enumerate(self._rows.keys())]
