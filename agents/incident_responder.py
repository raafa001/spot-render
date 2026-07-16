"""
IncidentResponder Agent - Automated incident response

Provides:
- Intelligent runbook suggestions
- Automated remediation steps
- Escalation decisions
- Communication templates

DO NOT execute destructive actions without human approval.
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


@dataclass
class ResponseAction:
    """An action to take during incident response"""
    action: str
    description: str
    automated: bool  # Can be automated or requires approval
    estimated_duration: str
    risk_level: str  # low, medium, high, critical
    rollback_available: bool


class IncidentResponderConfig(AgentConfig):
    """Configuration for IncidentResponder"""
    auto_approve_low_risk: bool = True
    require_approval_for: List[str] = field(default_factory=lambda: ["delete", "terminate", "drop"])
    notification_channels: List[str] = field(default_factory=lambda: ["slack"])


class IncidentResponder(BaseAgent):
    """
    Automated incident response agent.
    
    Analyzes incidents and recommends/suggests response actions.
    NEVER automatically executes destructive actions.
    
    Usage:
        agent = IncidentResponder()
        agent.initialize()
        
        result = agent.run({
            "incident": {
                "title": "High latency",
                "symptoms": ["p99 > 2s"],
                "severity": "high"
            }
        })
    """
    
    # Known incident patterns and recommended responses
    RESPONSE_PLAYBOOKS = {
        "high_latency": {
            "checks": [
                "Check current CPU/memory utilization",
                "Review recent deployments",
                "Check database connection pool",
                "Review slow queries"
            ],
            "actions": [
                {"action": "scale_up", "description": "Scale up service", "automated": False},
                {"action": "restart_pods", "description": "Restart affected pods", "automated": True, "risk": "low"},
                {"action": "rollback", "description": "Rollback recent deployment", "automated": False}
            ]
        },
        "high_error_rate": {
            "checks": [
                "Check application logs",
                "Review recent config changes",
                "Check dependency health"
            ],
            "actions": [
                {"action": "restart_service", "description": "Restart service", "automated": True, "risk": "medium"},
                {"action": "failover", "description": "Failover to backup", "automated": False}
            ]
        },
        "queue_backup": {
            "checks": [
                "Check worker health",
                "Review job processing rate",
                "Check for dead letters"
            ],
            "actions": [
                {"action": "scale_workers", "description": "Scale up workers", "automated": True, "risk": "low"},
                {"action": "drain_queue", "description": "Drain and retry failed jobs", "automated": False}
            ]
        },
        "resource_exhaustion": {
            "checks": [
                "Check disk space",
                "Review log rotation",
                "Check for memory leaks"
            ],
            "actions": [
                {"action": "cleanup_logs", "description": "Clean up old logs", "automated": True, "risk": "low"},
                {"action": "restart_service", "description": "Restart affected service", "automated": True, "risk": "medium"}
            ]
        }
    }
    
    def __init__(self, config: Optional[IncidentResponderConfig] = None):
        super().__init__(config or IncidentResponderConfig(
            name="incident-responder",
            description="Automated incident response"
        ))
        self.responder_config: IncidentResponderConfig = self.config
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Respond to an incident"""
        incident = input_data.get("incident", {})
        
        self.logger.info(f"Responding to incident: {incident.get('title', 'Unknown')}")
        
        # Classify incident type
        incident_type = self._classify_incident(incident)
        
        # Get playbook
        playbook = self.RESPONSE_PLAYBOOKS.get(incident_type, {})
        
        # Generate response plan
        response_plan = self._generate_response_plan(incident, playbook)
        
        # Send initial response notification
        self._send_incident_notification(incident, response_plan)
        
        # If automated actions are safe, suggest them
        automated_actions = [a for a in response_plan.get("actions", []) if a["automated"]]
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Response plan generated for {incident_type}",
            details={
                "incident_type": incident_type,
                "checks": response_plan.get("checks", []),
                "recommended_actions": response_plan.get("actions", []),
                "automated_actions": automated_actions,
                "requires_approval": response_plan.get("requires_approval", [])
            }
        )
    
    def _classify_incident(self, incident: Dict) -> str:
        """Classify incident type based on symptoms"""
        symptoms = " ".join(incident.get("symptoms", [])).lower()
        title = incident.get("title", "").lower()
        
        text = symptoms + " " + title
        
        if "latency" in text or "slow" in text or "p99" in text:
            return "high_latency"
        elif "error" in text or "5.." in text or "exception" in text:
            return "high_error_rate"
        elif "queue" in text or "backlog" in text or "pending" in text:
            return "queue_backup"
        elif "memory" in text or "disk" in text or "cpu" in text or "resource" in text:
            return "resource_exhaustion"
        else:
            return "unknown"
    
    def _generate_response_plan(self, incident: Dict, playbook: Dict) -> Dict:
        """Generate response plan from playbook"""
        
        actions = []
        requires_approval = []
        
        for action_def in playbook.get("actions", []):
            action = ResponseAction(
                action=action_def.get("action", "unknown"),
                description=action_def.get("description", ""),
                automated=action_def.get("automated", False),
                estimated_duration=action_def.get("estimated_duration", "5-10 min"),
                risk_level=action_def.get("risk", "medium"),
                rollback_available=action_def.get.get("rollback_available", True)
            )
            
            # Check if action requires approval
            if any(dangerous in action.action for dangerous in self.responder_config.require_approval_for):
                requires_approval.append({
                    "action": action.action,
                    "description": action.description,
                    "reason": "Requires explicit approval (destructive action)"
                })
                action.automated = False
            elif action.risk_level in ["high", "critical"]:
                requires_approval.append({
                    "action": action.action,
                    "description": action.description,
                    "reason": f"Risk level: {action.risk_level}"
                })
                action.automated = False
            
            actions.append({
                "action": action.action,
                "description": action.description,
                "automated": action.automated,
                "estimated_duration": action.estimated_duration,
                "risk_level": action.risk_level,
                "rollback_available": action.rollback_available
            })
        
        return {
            "checks": playbook.get("checks", []),
            "actions": actions,
            "requires_approval": requires_approval
        }
    
    def _send_incident_notification(
        self,
        incident: Dict,
        response_plan: Dict
    ) -> None:
        """Send incident response notification"""
        severity = incident.get("severity", "medium")
        
        automated = [a for a in response_plan.get("actions", []) if a["automated"]]
        needs_approval = response_plan.get("requires_approval", [])
        
        message = f"""
**Incident:** {incident.get('title', 'Unknown')}

**Classification:** {incident.get('type', 'Unknown')}

**Automated Actions Suggested:** {len(automated)}
{chr(10).join([f"- {a['description']}" for a in automated[:3]])}

**Actions Requiring Approval:** {len(needs_approval)}
{chr(10).join([f"- {a['description']} ({a['reason']})" for a in needs_approval[:3]])}
""".strip()
        
        self.notify(
            title=f"🚨 Incident Response: {incident.get('title', 'New Incident')}",
            message=message,
            severity=severity,
            response_plan=response_plan
        )
    
    def get_playbook(self, incident_type: str) -> Optional[Dict]:
        """Get response playbook for incident type"""
        return self.RESPONSE_PLAYBOOKS.get(incident_type)
    
    def list_playbooks(self) -> List[str]:
        """List all available playbooks"""
        return list(self.RESPONSE_PLAYBOOKS.keys())
