"""
Notifications - Slack, PagerDuty, and Webhook integrations

Usage:
    from lib.notifications import NotificationClient
    
    client = NotificationClient()
    
    # Send Slack message
    client.slack(
        channel="#aiops",
        message="Anomaly detected in render queue",
        severity="warning"
    )
    
    # Create PagerDuty incident
    client.pagerduty(
        title="High Error Rate in spot-render-api",
        severity="critical",
        source="monitor-agent"
    )
"""

import os
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import requests


class Severity(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class NotificationConfig:
    """Configuration for notifications"""
    # Slack
    slack_webhook: Optional[str] = None
    slack_token: Optional[str] = None
    slack_default_channel: str = "#aiops"
    
    # PagerDuty
    pagerduty_routing_key: Optional[str] = None
    pagerduty_api_key: Optional[str] = None
    
    # Webhook
    webhook_url: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "NotificationConfig":
        return cls(
            slack_webhook=os.getenv("SLACK_WEBHOOK_URL"),
            slack_token=os.getenv("SLACK_BOT_TOKEN"),
            slack_default_channel=os.getenv("SLACK_DEFAULT_CHANNEL", "#aiops"),
            pagerduty_routing_key=os.getenv("PAGERDUTY_ROUTING_KEY"),
            pagerduty_api_key=os.getenv("PAGERDUTY_API_KEY"),
            webhook_url=os.getenv("AIOPS_WEBHOOK_URL"),
        )


class NotificationClient:
    """Client for sending notifications to various channels"""
    
    # Severity to emoji mapping
    SEVERITY_EMOJI = {
        Severity.DEBUG: "🔍",
        Severity.INFO: "ℹ️",
        Severity.WARNING: "⚠️",
        Severity.ERROR: "🚨",
        Severity.CRITICAL: "🔴",
    }
    
    # Severity to PagerDuty mapping
    PD_SEVERITY = {
        Severity.DEBUG: "info",
        Severity.INFO: "info",
        Severity.WARNING: "warning",
        Severity.ERROR: "error",
        Severity.CRITICAL: "critical",
    }
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        self.config = config or NotificationConfig.from_env()
    
    def slack(
        self,
        message: str,
        channel: Optional[str] = None,
        severity: Severity = Severity.INFO,
        blocks: Optional[List[Dict]] = None,
        **kwargs
    ) -> bool:
        """
        Send Slack notification.
        
        Args:
            message: Message text (max 3000 chars)
            channel: Slack channel (without #)
            severity: Message severity
            blocks: Slack block kit blocks (optional)
            
        Returns:
            True if sent successfully
        """
        if not self.config.slack_webhook and not self.config.slack_token:
            print(f"[SLACK] No webhook configured, skipping: {message[:50]}...")
            return False
        
        emoji = self.SEVERITY_EMOJI.get(severity, "ℹ️")
        
        if blocks:
            payload = {
                "channel": channel or self.config.slack_default_channel,
                "blocks": blocks
            }
        else:
            payload = {
                "channel": channel or self.config.slack_default_channel,
                "text": f"{emoji} {message}",
                "mrkdwn": True
            }
        
        try:
            if self.config.slack_webhook:
                # Webhook method
                response = requests.post(
                    self.config.slack_webhook,
                    json=payload,
                    timeout=10
                )
            else:
                # Token method
                headers = {"Authorization": f"Bearer {self.config.slack_token}"}
                response = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    json=payload,
                    headers=headers,
                    timeout=10
                )
            
            return response.status_code == 200
        except Exception as e:
            print(f"[SLACK] Error sending notification: {e}")
            return False
    
    def pagerduty(
        self,
        title: str,
        severity: Severity = Severity.ERROR,
        source: str = "aiops-agent",
        custom_details: Optional[Dict] = None,
        **kwargs
    ) -> Optional[str]:
        """
        Create PagerDuty incident.
        
        Args:
            title: Incident title
            severity: Incident severity
            source: Source system/component
            custom_details: Additional incident details
            
        Returns:
            Incident ID if created successfully
        """
        if not self.config.pagerduty_routing_key:
            print(f"[PAGERDUTY] No routing key configured, skipping: {title[:50]}...")
            return None
        
        pd_severity = self.PD_SEVERITY.get(severity, "error")
        
        payload = {
            "routing_key": self.config.pagerduty_routing_key,
            "event_action": "trigger",
            "dedup_key": f"aiops-{source}-{hash(title) % 10000}",
            "payload": {
                "summary": title,
                "severity": pd_severity,
                "source": source,
                "custom_details": custom_details or {},
                "timestamp": kwargs.get("timestamp")
            }
        }
        
        try:
            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 202:
                data = response.json()
                return data.get("dedup_key")
            
            return None
        except Exception as e:
            print(f"[PAGERDUTY] Error creating incident: {e}")
            return None
    
    def webhook(
        self,
        event_type: str,
        data: Dict[str, Any],
        **kwargs
    ) -> bool:
        """
        Send webhook notification.
        
        Args:
            event_type: Type of event
            data: Event data
            
        Returns:
            True if sent successfully
        """
        if not self.config.webhook_url:
            return False
        
        payload = {
            "event_type": event_type,
            "data": data,
            "timestamp": kwargs.get("timestamp")
        }
        
        try:
            response = requests.post(
                self.config.webhook_url,
                json=payload,
                timeout=10
            )
            return response.status_code in (200, 201, 202)
        except Exception as e:
            print(f"[WEBHOOK] Error sending notification: {e}")
            return False
    
    def notify(
        self,
        title: str,
        message: str,
        severity: Severity = Severity.INFO,
        channels: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, bool]:
        """
        Send notification to all configured channels.
        
        Args:
            title: Notification title
            message: Notification body
            severity: Severity level
            channels: List of channels ("slack", "pagerduty", "webhook")
            
        Returns:
            Dict with channel -> success status
        """
        channels = channels or ["slack"]
        results = {}
        
        if "slack" in channels:
            results["slack"] = self.slack(
                message=f"*{title}*\n{message}",
                severity=severity,
                **kwargs
            )
        
        if "pagerduty" in channels and severity in (Severity.ERROR, Severity.CRITICAL):
            results["pagerduty"] = self.pagerduty(
                title=title,
                severity=severity,
                custom_details={"message": message, **kwargs}
            ) is not None
        
        if "webhook" in channels:
            results["webhook"] = self.webhook(
                event_type=title,
                data={"message": message, "severity": severity.value, **kwargs}
            )
        
        return results


# Factory function
def create_notification_client() -> NotificationClient:
    """Create a notification client from environment variables"""
    return NotificationClient(NotificationConfig.from_env())
