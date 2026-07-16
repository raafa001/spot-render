"""
RootCauseAnalyzer Agent - Automated root cause analysis

Uses:
- LLM for causal reasoning
- Structured data (metrics, logs, events)
- 5 Whys methodology
- Dependency graphs

Analyzes:
- What happened
- Timeline of events
- Correlated changes
- Likely causes
"""

import os
import json
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


@dataclass
class TimelineEvent:
    """An event in the incident timeline"""
    timestamp: datetime
    event_type: str  # alert, deploy, config_change, error, metric_spike
    description: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalFactor:
    """A contributing factor to the incident"""
    factor: str
    evidence: str
    impact: str  # high, medium, low
    related_events: List[str] = field(default_factory=list)


@dataclass
class RCAReport:
    """Root cause analysis report"""
    incident_id: str
    title: str
    summary: str
    root_cause: str
    causal_factors: List[CausalFactor]
    timeline: List[TimelineEvent]
    action_items: List[Dict[str, str]]  # {action, priority, owner}
    preventive_measures: List[str]
    detection_improvements: List[str]
    confidence: float  # 0.0 to 1.0


class RootCauseAnalyzer(BaseAgent):
    """
    Automated root cause analysis using LLM and structured data.
    
    Uses the 5 Whys technique and causal reasoning to determine
    root causes of incidents.
    
    Usage:
        agent = RootCauseAnalyzer()
        agent.initialize()
        
        result = agent.run({
            "incident": {
                "title": "High latency in API",
                "symptoms": ["p99 > 2s", "error rate 5%"],
                "alerts": [...],
                "logs": "...",
            }
        })
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config or AgentConfig(
            name="root-cause-analyzer",
            description="Automated root cause analysis"
        ))
        self.incident_id_counter = 0
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Analyze an incident and determine root cause.
        
        Args:
            input_data: {
                "incident": {
                    "title": str,
                    "severity": str,
                    "start_time": str (ISO),
                    "end_time": str (ISO),
                    "symptoms": List[str],
                    "alerts": List[Dict],
                    "logs": str,
                    "metrics": Dict,
                    "recent_changes": List[Dict],
                    "related_incidents": List[Dict],
                }
            }
        """
        incident = input_data.get("incident", {})
        
        self.logger.info(f"Analyzing incident: {incident.get('title', 'Unknown')}")
        
        # Build timeline from alerts and events
        timeline = self._build_timeline(incident)
        
        # Correlate events
        correlations = self._correlate_events(timeline)
        
        # Generate root cause analysis using LLM
        if self.llm:
            rca_report = self._analyze_with_llm(incident, timeline, correlations)
        else:
            rca_report = self._analyze_structured(incident, timeline)
        
        # Generate postmortem
        postmortem_path = self._generate_postmortem(rca_report)
        
        # Send notification
        self.notify(
            title=f"🔍 RCA Complete: {rca_report.title}",
            message=f"""
**Root Cause:** {rca_report.root_cause[:200]}

**Confidence:** {rca_report.confidence:.0%}

**Action Items:** {len(rca_report.action_items)}
""".strip(),
            severity="info"
        )
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=rca_report.summary,
            details={
                "root_cause": rca_report.root_cause,
                "confidence": rca_report.confidence,
                "causal_factors": [
                    {"factor": cf.factor, "impact": cf.impact}
                    for cf in rca_report.causal_factors
                ],
                "action_items_count": len(rca_report.action_items),
            },
            artifacts=[postmortem_path]
        )
    
    def _build_timeline(self, incident: Dict) -> List[TimelineEvent]:
        """Build timeline from incident data"""
        timeline = []
        
        # Add alert events
        for alert in incident.get("alerts", []):
            timeline.append(TimelineEvent(
                timestamp=datetime.fromisoformat(alert.get("fired_at", datetime.utcnow().isoformat())),
                event_type="alert",
                description=f"Alert: {alert.get('name', 'Unknown')}",
                source=alert.get("source", "monitoring"),
                metadata=alert
            ))
        
        # Add recent changes
        for change in incident.get("recent_changes", []):
            timeline.append(TimelineEvent(
                timestamp=datetime.fromisoformat(change.get("timestamp", datetime.utcnow().isoformat())),
                event_type="config_change",
                description=f"Change: {change.get('description', 'Unknown')}",
                source=change.get("source", "unknown"),
                metadata=change
            ))
        
        # Add related incidents
        for rel_inc in incident.get("related_incidents", []):
            timeline.append(TimelineEvent(
                timestamp=datetime.fromisoformat(rel_inc.get("start_time", datetime.utcnow().isoformat())),
                event_type="related_incident",
                description=f"Related: {rel_inc.get('title', 'Unknown')}",
                source="incident_db",
                metadata=rel_inc
            ))
        
        # Sort by timestamp
        timeline.sort(key=lambda e: e.timestamp)
        
        return timeline
    
    def _correlate_events(self, timeline: List[TimelineEvent]) -> Dict[str, Any]:
        """Find correlations between events"""
        correlations = {
            "time_clusters": [],
            "related_pairs": [],
            "common_sources": {}
        }
        
        # Cluster events by time (within 5 min windows)
        if len(timeline) > 1:
            clusters = []
            current_cluster = [timeline[0]]
            
            for i in range(1, len(timeline)):
                time_diff = (timeline[i].timestamp - timeline[i-1].timestamp).total_seconds()
                
                if time_diff < 300:  # 5 minutes
                    current_cluster.append(timeline[i])
                else:
                    if len(current_cluster) > 1:
                        clusters.append(current_cluster)
                    current_cluster = [timeline[i]]
            
            if len(current_cluster) > 1:
                clusters.append(current_cluster)
            
            correlations["time_clusters"] = [
                {
                    "count": len(c),
                    "time_range": f"{c[0].timestamp} to {c[-1].timestamp}",
                    "events": [e.description for e in c]
                }
                for c in clusters
            ]
        
        # Find common sources
        for event in timeline:
            source = event.source
            correlations["common_sources"][source] = correlations["common_sources"].get(source, 0) + 1
        
        return correlations
    
    def _analyze_with_llm(
        self,
        incident: Dict,
        timeline: List[TimelineEvent],
        correlations: Dict
    ) -> RCAReport:
        """Analyze incident using LLM"""
        
        timeline_text = "\n".join([
            f"- {e.timestamp.isoformat()} [{e.event_type}] {e.description}"
            for e in timeline
        ])
        
        correlations_text = json.dumps(correlations, indent=2, default=str)
        
        prompt = f"""Perform root cause analysis for this incident using the 5 Whys technique.

## Incident
- Title: {incident.get('title', 'Unknown')}
- Severity: {incident.get('severity', 'Unknown')}
- Start: {incident.get('start_time', 'Unknown')}
- End: {incident.get('end_time', 'Unknown')}

## Symptoms
{chr(10).join([f"- {s}" for s in incident.get('symptoms', [])])}

## Alerts
{incident.get('alerts', 'None')}

## Timeline of Events
{timeline_text}

## Correlations
{correlations_text}

## Recent Changes
{incident.get('recent_changes', 'None')}

## Logs (last 50 lines)
{incident.get('logs', 'Not available')[:2000]}

Using the 5 Whys technique, analyze this incident and provide:
1. Root Cause (clear statement)
2. 3-5 Contributing Factors with evidence
3. 5-7 SMART Action Items (Specific, Measurable, Achievable, Relevant, Time-bound)
4. 3-5 Preventive Measures
5. 3 Detection Improvements
6. Confidence level (0.0 to 1.0) in the analysis

Format as JSON with these keys:
- root_cause: string
- causal_factors: [{{factor, evidence, impact}}]
- action_items: [{{action, priority, owner}}]
- preventive_measures: [string]
- detection_improvements: [string]
- confidence: float
- summary: string (2-3 sentences)
"""
        
        try:
            response = self.llm.generate(prompt)
            
            # Parse LLM response
            # Try to extract JSON from response
            json_match = None
            for line in response.split('\n'):
                if line.strip().startswith('{'):
                    json_match = line
                    break
            
            if json_match:
                # Find the JSON block
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                analysis = json.loads(json_str)
            else:
                # Use the whole response as summary
                analysis = {
                    "summary": response[:500],
                    "root_cause": response[:200],
                    "causal_factors": [],
                    "action_items": [],
                    "preventive_measures": [],
                    "detection_improvements": [],
                    "confidence": 0.5
                }
            
            # Build RCA report
            self.incident_id_counter += 1
            
            return RCAReport(
                incident_id=f"INC-{self.incident_id_counter:04d}",
                title=incident.get("title", "Unknown Incident"),
                summary=analysis.get("summary", "Analysis complete"),
                root_cause=analysis.get("root_cause", "Unknown"),
                causal_factors=[
                    CausalFactor(
                        factor=cf.get("factor", "Unknown"),
                        evidence=cf.get("evidence", ""),
                        impact=cf.get("impact", "medium")
                    )
                    for cf in analysis.get("causal_factors", [])
                ],
                timeline=timeline,
                action_items=analysis.get("action_items", []),
                preventive_measures=analysis.get("preventive_measures", []),
                detection_improvements=analysis.get("detection_improvements", []),
                confidence=analysis.get("confidence", 0.5)
            )
            
        except Exception as e:
            self.logger.warning(f"LLM analysis failed: {e}")
            return self._analyze_structured(incident, timeline)
    
    def _analyze_structured(self, incident: Dict, timeline: List[TimelineEvent]) -> RCAReport:
        """Fallback structured analysis without LLM"""
        
        # Simple correlation: most recent config change before alerts
        root_cause = "Unknown"
        causal_factors = []
        
        alerts = incident.get("alerts", [])
        changes = incident.get("recent_changes", [])
        
        if changes and alerts:
            # Find the most recent change before first alert
            first_alert = min(
                datetime.fromisoformat(a.get("fired_at", datetime.utcnow().isoformat()))
                for a in alerts
            )
            
            recent_changes = [
                c for c in changes
                if datetime.fromisoformat(c.get("timestamp", "")) < first_alert
            ]
            
            if recent_changes:
                latest_change = recent_changes[-1]
                root_cause = f"Change in {latest_change.get('component', 'unknown')}: {latest_change.get('description', '')}"
                causal_factors.append(CausalFactor(
                    factor="Recent configuration change",
                    evidence=latest_change.get("description", ""),
                    impact="high"
                ))
        
        self.incident_id_counter += 1
        
        return RCAReport(
            incident_id=f"INC-{self.incident_id_counter:04d}",
            title=incident.get("title", "Unknown Incident"),
            summary=f"Analyzed {len(timeline)} events, identified root cause",
            root_cause=root_cause,
            causal_factors=causal_factors,
            timeline=timeline,
            action_items=[
                {"action": "Investigate logs for further details", "priority": "medium", "owner": "on-call"}
            ],
            preventive_measures=[
                "Add more granular alerting",
                "Implement canary deployments"
            ],
            detection_improvements=[
                "Add metric correlation analysis",
                "Improve alert latency"
            ],
            confidence=0.4
        )
    
    def _generate_postmortem(self, report: RCAReport) -> str:
        """Generate postmortem document"""
        
        postmortem = f"""# Postmortem: {report.title}

**Incident ID:** {report.incident_id}  
**Date:** {datetime.utcnow().strftime('%Y-%m-%d')}  
**Status:** Resolved

---

## Executive Summary

{report.summary}

---

## Impact

| Metric | Value |
|--------|-------|
| Duration | {self._calc_duration(report.timeline)} |
| Severity | Medium |
| Root Cause Confidence | {report.confidence:.0%} |

---

## Timeline

| Time | Event | Description |
|------|-------|-------------|
"""
        
        for event in report.timeline:
            postmortem += f"| {event.timestamp.strftime('%H:%M:%S')} | {event.event_type} | {event.description} |\n"
        
        postmortem += f"""
---

## Root Cause Analysis (5 Whys)

**Root Cause:** {report.root_cause}

### Contributing Factors

"""
        
        for cf in report.causal_factors:
            postmortem += f"### {cf.factor}\n"
            postmortem += f"- **Evidence:** {cf.evidence}\n"
            postmortem += f"- **Impact:** {cf.impact}\n\n"
        
        postmortem += """---

## Action Items

| # | Action | Priority | Owner | Status |
|---|--------|----------|-------|--------|
"""
        
        for i, item in enumerate(report.action_items, 1):
            postmortem += f"| {i} | {item.get('action', '')} | {item.get('priority', 'medium')} | {item.get('owner', 'unassigned')} | open |\n"
        
        postmortem += """

---

## Preventive Measures

"""
        
        for i, measure in enumerate(report.preventive_measures, 1):
            postmortem += f"{i}. {measure}\n"
        
        postmortem += """

---

## Detection Improvements

"""
        
        for i, improvement in enumerate(report.detection_improvements, 1):
            postmortem += f"{i}. {improvement}\n"
        
        postmortem += """

---

## Lessons Learned

> What went well?
> What could be improved?
> What will we do differently next time?

---
*Generated by AIOps RootCauseAnalyzer*
"""
        
        # Save postmortem
        docs_dir = os.path.join(os.getcwd(), "docs", "postmortems")
        os.makedirs(docs_dir, exist_ok=True)
        
        filename = f"postmortem-{report.incident_id}-{datetime.utcnow().strftime('%Y%m%d')}.md"
        filepath = os.path.join(docs_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(postmortem)
        
        self.logger.info(f"Postmortem saved: {filepath}")
        return filepath
    
    def _calc_duration(self, timeline: List[TimelineEvent]) -> str:
        """Calculate incident duration from timeline"""
        if len(timeline) < 2:
            return "Unknown"
        
        start = min(e.timestamp for e in timeline)
        end = max(e.timestamp for e in timeline)
        
        duration = end - start
        
        if duration.total_seconds() < 60:
            return f"{duration.total_seconds():.0f} seconds"
        elif duration.total_seconds() < 3600:
            return f"{duration.total_seconds() / 60:.0f} minutes"
        else:
            return f"{duration.total_seconds() / 3600:.1f} hours"
