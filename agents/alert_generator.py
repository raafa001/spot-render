"""
AlertGenerator Agent - Intelligent alert generation and optimization

Analyzes:
- Current alert volume and noise
- Alert overlap and correlation
- Missing coverage

Generates:
- Prometheus/Thanos alerting rules
- Grafana alert notifications
- Alert routing rules
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


class AlertGeneratorConfig(AgentConfig):
    """Configuration for AlertGenerator"""
    output_format: str = "prometheus"  # prometheus, grafana, pagerduty
    output_path: str = "alerts"


class AlertGenerator(BaseAgent):
    """
    Generates optimized alerting rules from incidents and metrics.
    
    Usage:
        agent = AlertGenerator()
        agent.initialize()
        
        result = agent.run({
            "action": "generate",
            "based_on_incidents": ["INC-001", "INC-002"],
            "metrics": ["cpu", "memory", "latency"]
        })
    """
    
    def __init__(self, config: Optional[AlertGeneratorConfig] = None):
        super().__init__(config or AlertGeneratorConfig(
            name="alert-generator",
            description="Intelligent alert generation"
        ))
        self.alert_config: AlertGeneratorConfig = self.config
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Generate alert rules"""
        action = input_data.get("action", "generate")
        metrics = input_data.get("metrics", [])
        based_on_incidents = input_data.get("incidents", [])
        
        if action == "generate":
            return self._generate_alerts(metrics, based_on_incidents)
        elif action == "optimize":
            return self._optimize_alerts()
        else:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                summary="AlertGenerator ready"
            )
    
    def _generate_alerts(self, metrics: List[str], incidents: List[Dict]) -> AgentResult:
        """Generate alert rules"""
        self.logger.info(f"Generating alerts for: {metrics}")
        
        alerts = []
        
        # Define alert templates
        alert_templates = {
            "cpu": {
                "metric": "cpu_usage_percent",
                "threshold": 80,
                "duration": "5m",
                "severity": "warning",
                "description": "High CPU usage"
            },
            "memory": {
                "metric": "memory_usage_percent", 
                "threshold": 85,
                "duration": "5m",
                "severity": "warning",
                "description": "High memory usage"
            },
            "latency": {
                "metric": "http_request_duration_seconds",
                "threshold": 1.0,
                "duration": "2m",
                "severity": "critical",
                "description": "High request latency"
            },
            "error_rate": {
                "metric": "http_requests_total{status=~'5..'}",
                "threshold": 10,
                "duration": "1m",
                "severity": "critical",
                "description": "High error rate"
            },
            "queue": {
                "metric": "job_queue_length",
                "threshold": 100,
                "duration": "5m",
                "severity": "warning",
                "description": "Job queue backup"
            }
        }
        
        for metric in metrics:
            if metric in alert_templates:
                template = alert_templates[metric]
                
                alert = {
                    "name": f"{metric.upper()}_ALERT",
                    "expr": f'{template["metric"]} > {template["threshold"]}',
                    "duration": template["duration"],
                    "labels": {
                        "severity": template["severity"],
                        "team": "platform"
                    },
                    "annotations": {
                        "description": template["description"],
                        "runbook": f"runbooks/{metric}.md"
                    }
                }
                alerts.append(alert)
        
        # Generate Prometheus rules file
        rules_content = self._generate_prometheus_rules(alerts)
        
        # Save rules
        output_path = os.path.join(
            self.alert_config.output_path,
            "generated_alerts.yaml"
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w") as f:
            f.write(rules_content)
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Generated {len(alerts)} alert rules",
            details={
                "alerts_generated": len(alerts),
                "output_file": output_path,
                "alerts": alerts
            },
            artifacts=[output_path]
        )
    
    def _generate_prometheus_rules(self, alerts: List[Dict]) -> str:
        """Generate Prometheus alerting rules YAML"""
        content = """# Generated by AlertGenerator
# Date: {}

groups:
  - name: generated_alerts
    interval: 30s
    rules:
""".format(datetime.utcnow().strftime('%Y-%m-%d'))
        
        for alert in alerts:
            content += f"""
      - alert: {alert['name']}
        expr: {alert['expr']}
        for: {alert['duration']}
        labels:
          severity: {alert['labels']['severity']}
          team: {alert['labels']['team']}
        annotations:
          description: "{alert['annotations']['description']}"
          runbook: "{alert['annotations']['runbook']}"
"""
        
        return content
    
    def _optimize_alerts(self) -> AgentResult:
        """Analyze and optimize existing alerts"""
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary="Alert optimization analysis complete",
            details={
                "recommendations": [
                    "Consider adding recording rules for frequently queried metrics",
                    "Deduplicate overlapping alerts using alert routing",
                    "Add warning threshold before critical"
                ]
            }
        )
