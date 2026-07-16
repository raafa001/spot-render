"""
Human Approval Workflow - Ensures critical changes get human review

This module implements the approval workflow for:
1. Production environment changes
2. Critical infrastructure modifications  
3. Destructive actions (delete, terminate, drop)
4. Security-related changes

All such actions require explicit human approval before execution.
"""

import os
import json
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class ApprovalLevel(Enum):
    """Approval level based on risk/criticality"""
    NONE = "none"           # No approval needed
    INFO = "info"           # Just informational
    LOW = "low"             # Minor changes, can auto-approve with notification
    MEDIUM = "medium"       # Moderate risk, requires approval
    HIGH = "high"          # High risk, requires senior approval
    CRITICAL = "critical"   # Production/critical systems, requires explicit approval


class ActionType(Enum):
    """Types of actions that require approval"""
    # Safe actions (no approval)
    READ = "read"
    QUERY = "query"
    LIST = "list"
    STATUS = "status"
    
    # Actions requiring approval
    CREATE = "create"
    UPDATE = "update"
    DEPLOY = "deploy"
    
    # High-risk actions (always require approval)
    DELETE = "delete"
    TERMINATE = "terminate"
    DROP = "drop"
    RESTART = "restart"  # Can cause downtime
    ROLLBACK = "rollback"
    SCALE_DOWN = "scale_down"
    
    # Production changes
    PRODUCTION_CHANGE = "production_change"
    SECURITY_CHANGE = "security_change"
    CONFIG_CHANGE = "config_change"


@dataclass
class ApprovalRequest:
    """Request for human approval"""
    id: str
    action: str
    description: str
    target: str  # What is being affected
    environment: str  # dev, staging, production
    risk_level: ApprovalLevel
    requested_by: str  # Agent name
    requested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "pending"  # pending, approved, rejected, expired
    approver: Optional[str] = None
    approved_at: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "action": self.action,
            "description": self.description,
            "target": self.target,
            "environment": self.environment,
            "risk_level": self.risk_level.value,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "status": self.status,
            "approver": self.approver,
            "approved_at": self.approved_at,
            "reason": self.reason,
            "metadata": self.metadata
        }


class ApprovalWorkflow:
    """
    Human approval workflow for production changes.
    
    Usage:
        workflow = ApprovalWorkflow()
        
        # Check if approval is needed
        if workflow.requires_approval("delete", "production"):
            # Create approval request
            request = workflow.create_request(
                action="delete",
                target="api-database",
                environment="production",
                description="Remove unused database"
            )
            
            # Wait for approval
            if workflow.wait_for_approval(request, timeout=3600):
                # Execute the action
                execute_deletion()
            else:
                # Handle rejection/timeout
                pass
    """
    
    # Risk mapping: action -> minimum approval level by environment
    RISK_MATRIX = {
        # (action, environment) -> risk level
        ("read", "any"): ApprovalLevel.NONE,
        ("query", "any"): ApprovalLevel.NONE,
        ("list", "any"): ApprovalLevel.NONE,
        ("status", "any"): ApprovalLevel.NONE,
        
        ("create", "dev"): ApprovalLevel.LOW,
        ("create", "staging"): ApprovalLevel.MEDIUM,
        ("create", "production"): ApprovalLevel.HIGH,
        
        ("update", "dev"): ApprovalLevel.LOW,
        ("update", "staging"): ApprovalLevel.MEDIUM,
        ("update", "production"): ApprovalLevel.HIGH,
        
        ("deploy", "dev"): ApprovalLevel.LOW,
        ("deploy", "staging"): ApprovalLevel.MEDIUM,
        ("deploy", "production"): ApprovalLevel.CRITICAL,
        
        ("delete", "any"): ApprovalLevel.CRITICAL,
        ("terminate", "any"): ApprovalLevel.CRITICAL,
        ("drop", "any"): ApprovalLevel.CRITICAL,
        ("restart", "any"): ApprovalLevel.HIGH,
        ("rollback", "any"): ApprovalLevel.HIGH,
        ("scale_down", "any"): ApprovalLevel.MEDIUM,
        
        ("production_change", "any"): ApprovalLevel.CRITICAL,
        ("security_change", "any"): ApprovalLevel.CRITICAL,
        ("config_change", "production"): ApprovalLevel.HIGH,
    }
    
    # Keywords that indicate high-risk actions
    HIGH_RISK_KEYWORDS = [
        "delete", "drop", "terminate", "kill", "remove",
        "destroy", "truncate", "shutdown", "critical", "production"
    ]
    
    def __init__(self, approval_callback: Optional[Callable] = None):
        """
        Initialize approval workflow.
        
        Args:
            approval_callback: Function to call when approval is needed.
                             Should return True (approved) or False (rejected).
        """
        self.approval_callback = approval_callback
        self.pending_requests: Dict[str, ApprovalRequest] = {}
        self.approval_history: List[ApprovalRequest] = []
    
    def requires_approval(
        self,
        action: str,
        environment: str = "production"
    ) -> bool:
        """
        Check if an action requires human approval.
        """
        risk = self.get_risk_level(action, environment)
        return risk != ApprovalLevel.NONE
    
    def get_risk_level(
        self,
        action: str,
        environment: str = "production"
    ) -> ApprovalLevel:
        """
        Get the risk level for an action.
        """
        # Check specific action + environment
        key = (action.lower(), environment.lower())
        if key in self.RISK_MATRIX:
            return self.RISK_MATRIX[key]
        
        # Check generic action
        generic_key = (action.lower(), "any")
        if generic_key in self.RISK_MATRIX:
            return self.RISK_MATRIX[generic_key]
        
        # Check if action matches high-risk keywords
        action_lower = action.lower()
        if any(kw in action_lower for kw in self.HIGH_RISK_KEYWORDS):
            return ApprovalLevel.HIGH
        
        # Default to MEDIUM for unknown actions
        return ApprovalLevel.MEDIUM
    
    def create_request(
        self,
        action: str,
        description: str,
        target: str,
        environment: str = "production",
        requested_by: str = "aiops-agent",
        metadata: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """
        Create an approval request.
        """
        risk_level = self.get_risk_level(action, environment)
        
        # Generate unique ID
        request_id = hashlib.md5(
            f"{action}{target}{datetime.utcnow().isoformat()}".encode()
        ).hexdigest()[:8]
        
        request = ApprovalRequest(
            id=request_id,
            action=action,
            description=description,
            target=target,
            environment=environment,
            risk_level=risk_level,
            requested_by=requested_by,
            metadata=metadata or {}
        )
        
        self.pending_requests[request_id] = request
        
        return request
    
    def approve(
        self,
        request_id: str,
        approver: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Approve a request.
        """
        if request_id not in self.pending_requests:
            return False
        
        request = self.pending_requests[request_id]
        request.status = "approved"
        request.approver = approver
        request.approved_at = datetime.utcnow().isoformat()
        request.reason = reason
        
        self.approval_history.append(request)
        del self.pending_requests[request_id]
        
        return True
    
    def reject(
        self,
        request_id: str,
        approver: str,
        reason: str
    ) -> bool:
        """
        Reject a request.
        """
        if request_id not in self.pending_requests:
            return False
        
        request = self.pending_requests[request_id]
        request.status = "rejected"
        request.approver = approver
        request.approved_at = datetime.utcnow().isoformat()
        request.reason = reason
        
        self.approval_history.append(request)
        del self.pending_requests[request_id]
        
        return True
    
    def wait_for_approval(
        self,
        request: ApprovalRequest,
        timeout: int = 3600
    ) -> bool:
        """
        Wait for approval (blocking).
        
        In production, this would integrate with Slack, PagerDuty, etc.
        For now, it checks self.approval_callback periodically.
        """
        import time
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if request.id not in self.pending_requests:
                # Request was processed
                return request.status == "approved"
            
            if self.approval_callback:
                # Try callback
                result = self.approval_callback(request)
                if result is not None:
                    if result:
                        self.approve(request.id, "human-approver", "Approved via callback")
                    else:
                        self.reject(request.id, "human-approver", "Rejected via callback")
                    return result
            
            time.sleep(10)  # Check every 10 seconds
        
        # Timeout - expire the request
        request.status = "expired"
        return False
    
    def auto_approve_if_safe(
        self,
        action: str,
        environment: str
    ) -> bool:
        """
        Check if action can be auto-approved.
        
        Returns True if the action is safe enough to auto-approve.
        """
        risk = self.get_risk_level(action, environment)
        
        # None and Info can always auto-approve
        if risk in (ApprovalLevel.NONE, ApprovalLevel.INFO):
            return True
        
        # Low risk can auto-approve in dev/staging
        if risk == ApprovalLevel.LOW and environment in ("dev", "local"):
            return True
        
        return False
    
    def format_approval_message(self, request: ApprovalRequest) -> str:
        """
        Format an approval request as a Slack/notification message.
        """
        risk_emoji = {
            ApprovalLevel.NONE: "✅",
            ApprovalLevel.INFO: "ℹ️",
            ApprovalLevel.LOW: "🟢",
            ApprovalLevel.MEDIUM: "🟡",
            ApprovalLevel.HIGH: "🟠",
            ApprovalLevel.CRITICAL: "🔴"
        }
        
        emoji = risk_emoji.get(request.risk_level, "⚠️")
        
        return f"""
{emoji} *Approval Required*

*Action:* `{request.action}`
*Target:* `{request.target}`
*Environment:* `{request.environment}`
*Risk Level:* `{request.risk_level.value.upper()}`
*Requested By:* `{request.requested_by}`

*Description:*
{request.description}

*Request ID:* `{request.id}`

React with ✅ to approve or ❌ to reject.
"""


# Global instance
_approval_workflow: Optional[ApprovalWorkflow] = None

def get_approval_workflow() -> ApprovalWorkflow:
    """Get the global approval workflow instance"""
    global _approval_workflow
    if _approval_workflow is None:
        _approval_workflow = ApprovalWorkflow()
    return _approval_workflow
