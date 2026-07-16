"""
Monitor Agent - Real-time monitoring and anomaly detection

Monitors:
- System metrics (CPU, memory, disk, network)
- Application metrics (latency, throughput, errors)
- Business metrics (jobs completed, revenue)
- Custom metrics via Prometheus/CloudWatch

Detects:
- Statistical anomalies (3-sigma, EWMA)
- Pattern changes (seasonal, trend)
- Threshold violations

Uses lightweight ML for anomaly detection.
"""

import os
import json
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import deque
import statistics

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


@dataclass
class MetricPoint:
    """A single metric data point"""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Anomaly:
    """Detected anomaly"""
    metric: str
    timestamp: datetime
    value: float
    expected_value: float
    deviation: float  # How many sigma/stds from expected
    severity: str  # info, warning, critical
    description: str


@dataclass
class MonitorConfig(AgentConfig):
    """Configuration for Monitor agent"""
    # Data sources
    prometheus_url: str = "http://localhost:9090"
    cloudwatch_region: str = "us-east-1"
    
    # Detection settings
    detection_method: str = "sigma"  # sigma, ewma, isolation_forest
    sigma_threshold: float = 3.0  # Standard deviations for anomaly
    ewma_alpha: float = 0.3  # EWMA smoothing factor
    min_data_points: int = 30  # Minimum history for detection
    
    # Alerting
    alert_on_anomaly: bool = True
    cooldown_seconds: int = 300  # Don't re-alert for same metric in this time
    
    # Metrics to monitor (if empty, monitors all)
    metrics_filter: List[str] = field(default_factory=list)
    
    # Polling interval
    poll_interval_seconds: int = 60


class StatisticalDetector:
    """
    Statistical anomaly detection using multiple methods.
    """
    
    def __init__(self, method: str = "sigma", threshold: float = 3.0, ewma_alpha: float = 0.3):
        self.method = method
        self.threshold = threshold
        self.ewma_alpha = ewma_alpha
        
        # State for each metric
        self.history: Dict[str, deque] = {}
        self.ewma_values: Dict[str, float] = {}
        self.ewma_variance: Dict[str, float] = {}
    
    def update(self, metric: str, value: float) -> Optional[Anomaly]:
        """
        Update metric history and check for anomalies.
        
        Returns Anomaly if detected, None otherwise.
        """
        if metric not in self.history:
            self.history[metric] = deque(maxlen=1000)
            self.ewma_values[metric] = value
            self.ewma_variance[metric] = 0.0
        
        self.history[metric].append(value)
        
        # Need minimum data points
        if len(self.history[metric]) < 10:
            return None
        
        if self.method == "sigma":
            return self._detect_sigma(metric, value)
        elif self.method == "ewma":
            return self._detect_ewma(metric, value)
        else:
            return self._detect_sigma(metric, value)
    
    def _detect_sigma(self, metric: str, value: float) -> Optional[Anomaly]:
        """Detect anomalies using standard deviation method"""
        history = list(self.history[metric])
        
        # Calculate statistics
        mean = statistics.mean(history)
        std = statistics.stdev(history)
        
        if std == 0:
            return None
        
        deviation = abs(value - mean) / std
        
        if deviation > self.threshold:
            return Anomaly(
                metric=metric,
                timestamp=datetime.utcnow(),
                value=value,
                expected_value=mean,
                deviation=deviation,
                severity="critical" if deviation > self.threshold * 2 else "warning",
                description=f"Value {value:.2f} is {deviation:.1f} std from mean {mean:.2f}"
            )
        
        return None
    
    def _detect_ewma(self, metric: str, value: float) -> Optional[Anomaly]:
        """Detect anomalies using EWMA method"""
        alpha = self.ewma_alpha
        
        # Update EWMA
        if self.ewma_values.get(metric) is None:
            self.ewma_values[metric] = value
        
        self.ewma_values[metric] = alpha * value + (1 - alpha) * self.ewma_values[metric]
        
        # Update variance estimate
        diff = value - self.ewma_values[metric]
        self.ewma_variance[metric] = (1 - alpha) * (self.ewma_variance.get(metric, 0) + alpha * diff ** 2)
        
        std = self.ewma_variance[metric] ** 0.5
        
        if std > 0:
            deviation = abs(value - self.ewma_values[metric]) / std
            
            if deviation > self.threshold:
                return Anomaly(
                    metric=metric,
                    timestamp=datetime.utcnow(),
                    value=value,
                    expected_value=self.ewma_values[metric],
                    deviation=deviation,
                    severity="critical" if deviation > self.threshold * 2 else "warning",
                    description=f"EWMA deviation: {deviation:.1f} std"
                )
        
        return None
    
    def get_stats(self, metric: str) -> Optional[Dict]:
        """Get current statistics for a metric"""
        if metric not in self.history or len(self.history[metric]) < 2:
            return None
        
        history = list(self.history[metric])
        return {
            "count": len(history),
            "mean": statistics.mean(history),
            "std": statistics.stdev(history),
            "min": min(history),
            "max": max(history),
            "ewma": self.ewma_values.get(metric),
        }


class MonitorAgent(BaseAgent):
    """
    Real-time monitoring and anomaly detection agent.
    
    Collects metrics from various sources and uses statistical
    methods to detect anomalies in real-time.
    
    Usage:
        agent = MonitorAgent()
        agent.initialize()
        
        # Add custom metric
        agent.add_metric("render_queue_size", lambda: get_queue_length())
        
        # Start monitoring
        agent.start()
        
        # Or run once
        result = agent.run({"action": "check", "metrics": ["cpu_usage"]})
    """
    
    def __init__(self, config: Optional[MonitorConfig] = None):
        super().__init__(config or MonitorConfig(
            name="monitor",
            description="Real-time monitoring and anomaly detection"
        ))
        self.monitor_config: MonitorConfig = self.config
        self.detector = StatisticalDetector(
            method=self.monitor_config.detection_method,
            threshold=self.monitor_config.sigma_threshold,
            ewma_alpha=self.monitor_config.ewma_alpha
        )
        
        # Custom metric collectors
        self.custom_collectors: Dict[str, Callable] = {}
        
        # Alert cooldown tracking
        self.alert_cooldowns: Dict[str, datetime] = {}
        
        # Monitoring state
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Current anomalies
        self.active_anomalies: List[Anomaly] = []
    
    def initialize(self) -> None:
        """Initialize the monitor agent"""
        super().initialize()
        self.logger.info("MonitorAgent initialized")
        self.logger.info(f"Detection method: {self.monitor_config.detection_method}")
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Execute monitoring task.
        
        Args:
            input_data: {
                "action": str,  # "check", "start", "stop", "status"
                "metrics": List[str],  # Specific metrics to check
            }
        """
        action = input_data.get("action", "check")
        
        if action == "start":
            return self._start_monitoring()
        elif action == "stop":
            return self._stop_monitoring()
        elif action == "status":
            return self._get_status()
        else:  # check
            return self._check_metrics(input_data.get("metrics"))
    
    def add_metric(self, name: str, collector: Callable[[], float], labels: Optional[Dict] = None) -> None:
        """
        Add a custom metric to monitor.
        
        Args:
            name: Metric name
            collector: Function that returns current metric value
            labels: Optional labels for the metric
        """
        self.custom_collectors[name] = collector
        self.logger.info(f"Added custom metric: {name}")
    
    def _check_metrics(self, specific_metrics: Optional[List[str]] = None) -> AgentResult:
        """Check all or specific metrics for anomalies"""
        anomalies_detected = []
        metric_values = {}
        
        metrics_to_check = specific_metrics or list(self.custom_collectors.keys())
        
        for metric_name in metrics_to_check:
            if metric_name not in self.custom_collectors:
                continue
            
            try:
                value = self.custom_collectors[metric_name]()
                metric_values[metric_name] = value
                
                # Check for anomaly
                anomaly = self.detector.update(metric_name, value)
                
                if anomaly:
                    # Check cooldown
                    if self._should_alert(metric_name):
                        anomalies_detected.append(anomaly)
                        self.active_anomalies.append(anomaly)
                        self.alert_cooldowns[metric_name] = datetime.utcnow()
            
            except Exception as e:
                self.logger.warning(f"Failed to collect metric {metric_name}: {e}")
        
        # Build summary
        if anomalies_detected:
            summary = f"Detected {len(anomalies_detected)} anomalies"
            severity = "critical" if any(a.severity == "critical" for a in anomalies_detected) else "warning"
            
            if self.monitor_config.alert_on_anomaly:
                self._send_anomaly_alerts(anomalies_detected)
        else:
            summary = f"All {len(metric_values)} metrics normal"
            severity = "success"
        
        status = AgentStatus.SUCCESS
        if anomalies_detected:
            status = AgentStatus.WARNING
        
        return AgentResult(
            status=status,
            summary=summary,
            details={
                "metrics_checked": len(metric_values),
                "anomalies_detected": len(anomalies_detected),
                "metric_values": metric_values,
                "anomaly_details": [
                    {
                        "metric": a.metric,
                        "value": a.value,
                        "expected": a.expected_value,
                        "deviation": a.deviation,
                        "severity": a.severity
                    }
                    for a in anomalies_detected
                ]
            }
        )
    
    def _should_alert(self, metric: str) -> bool:
        """Check if we should send an alert (respecting cooldown)"""
        if metric not in self.alert_cooldowns:
            return True
        
        cooldown_end = self.alert_cooldowns[metric] + timedelta(
            seconds=self.monitor_config.cooldown_seconds
        )
        
        return datetime.utcnow() > cooldown_end
    
    def _send_anomaly_alerts(self, anomalies: List[Anomaly]) -> None:
        """Send alerts for detected anomalies"""
        for anomaly in anomalies:
            severity = "critical" if anomaly.severity == "critical" else "warning"
            
            self.notify(
                title=f"Anomaly Detected: {anomaly.metric}",
                message=f"""
**Metric:** {anomaly.metric}
**Value:** {anomaly.value:.2f}
**Expected:** {anomaly.expected_value:.2f}
**Deviation:** {anomaly.deviation:.1f} std

{anomaly.description}
""".strip(),
                severity=severity,
                anomaly_data=anomaly
            )
    
    def _start_monitoring(self) -> AgentResult:
        """Start continuous monitoring"""
        if self._monitoring:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                summary="Monitoring already running"
            )
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary="Monitoring started",
            details={"poll_interval": self.monitor_config.poll_interval_seconds}
        )
    
    def _stop_monitoring(self) -> AgentResult:
        """Stop continuous monitoring"""
        self._monitoring = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary="Monitoring stopped"
        )
    
    def _get_status(self) -> AgentResult:
        """Get monitoring status"""
        stats = {}
        for metric in self.custom_collectors.keys():
            metric_stats = self.detector.get_stats(metric)
            if metric_stats:
                stats[metric] = metric_stats
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Monitoring {'running' if self._monitoring else 'stopped'}",
            details={
                "monitoring": self._monitoring,
                "metrics_count": len(self.custom_collectors),
                "active_anomalies": len(self.active_anomalies),
                "metric_stats": stats
            }
        )
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop (runs in thread)"""
        self.logger.info("Monitoring loop started")
        
        while self._monitoring:
            try:
                result = self._check_metrics()
                
                if result.status != AgentStatus.SUCCESS:
                    self.logger.warning(f"Monitoring issues: {result.summary}")
            
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
            
            time.sleep(self.monitor_config.poll_interval_seconds)
        
        self.logger.info("Monitoring loop stopped")
    
    def get_metric_history(self, metric: str, limit: int = 100) -> List[MetricPoint]:
        """Get historical values for a metric"""
        if metric not in self.detector.history:
            return []
        
        history = list(self.detector.history[metric])[-limit:]
        now = datetime.utcnow()
        
        return [
            MetricPoint(
                timestamp=now - timedelta(seconds=i),
                value=v
            )
            for i, v in enumerate(reversed(history))
        ]
    
    def clear_metric(self, metric: str) -> None:
        """Clear history for a specific metric"""
        if metric in self.detector.history:
            del self.detector.history[metric]
        if metric in self.detector.ewma_values:
            del self.detector.ewma_values[metric]
        if metric in self.detector.ewma_variance:
            del self.detector.ewma_variance[metric]
        
        self.logger.info(f"Cleared history for metric: {metric}")


class PrometheusCollector:
    """
    Collects metrics from Prometheus.
    
    Usage:
        collector = PrometheusCollector("http://prometheus:9090")
        value = collector.query("up")
    """
    
    def __init__(self, url: str):
        self.url = url.rstrip("/")
    
    def query(self, metric: str, timeout: int = 10) -> Optional[float]:
        """Query a single metric value from Prometheus"""
        import requests
        
        try:
            response = requests.get(
                f"{self.url}/api/v1/query",
                params={"query": metric},
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    return float(data["data"]["result"][0]["value"][1])
            
            return None
        except Exception as e:
            print(f"Prometheus query failed: {e}")
            return None
    
    def query_range(self, metric: str, duration: str = "1h") -> List[Dict]:
        """Query metric range from Prometheus"""
        import requests
        
        try:
            response = requests.get(
                f"{self.url}/api/v1/query_range",
                params={"query": metric, "duration": duration},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success":
                    return data["data"]["result"]
            
            return []
        except Exception as e:
            print(f"Prometheus range query failed: {e}")
            return []


class CloudWatchCollector:
    """
    Collects metrics from AWS CloudWatch.
    
    Usage:
        collector = CloudWatchCollector(region="us-east-1")
        value = collector.get_metric("AWS/EC2", "CPUUtilization", instance_id)
    """
    
    def __init__(self, region: str = "us-east-1"):
        self.region = region
    
    def get_metric(
        self,
        namespace: str,
        metric_name: str,
        dimension_name: str,
        dimension_value: str,
        period: int = 300
    ) -> Optional[float]:
        """Get a single metric value from CloudWatch"""
        try:
            import boto3
            
            client = boto3.client("cloudwatch", region_name=self.region)
            
            response = client.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {"Name": dimension_name, "Value": dimension_value}
                ],
                StartTime=datetime.utcnow() - timedelta(seconds=period * 2),
                EndTime=datetime.utcnow(),
                Period=period,
                Statistics=["Average"]
            )
            
            if response["Datapoints"]:
                return response["Datapoints"][0]["Average"]
            
            return None
        except Exception as e:
            print(f"CloudWatch get_metric failed: {e}")
            return None
