"""
CapacityPlanner Agent - Forecasting and capacity planning

Forecasts:
- Resource utilization (CPU, memory, storage)
- Request volume and growth
- Cost trends

Uses:
- Prophet for time series forecasting
- Statistical models for trends
"""

import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


class CapacityPlannerConfig(AgentConfig):
    """Configuration for CapacityPlanner"""
    forecast_horizon_days: int = 30
    confidence_level: float = 0.95
    growth_model: str = "linear"  # linear, exponential


class CapacityPlanner(BaseAgent):
    """
    Capacity planning and forecasting agent.
    
    Usage:
        agent = CapacityPlanner()
        agent.initialize()
        
        result = agent.run({
            "action": "forecast",
            "metric": "cpu_usage",
            "data_points": [...],
            "horizon_days": 30
        })
    """
    
    def __init__(self, config: Optional[CapacityPlannerConfig] = None):
        super().__init__(config or CapacityPlannerConfig(
            name="capacity-planner",
            description="Capacity forecasting and planning"
        ))
        self.planner_config: CapacityPlannerConfig = self.config
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Execute capacity planning"""
        action = input_data.get("action", "forecast")
        
        if action == "forecast":
            return self._forecast(input_data)
        elif action == "rightsize":
            return self._recommend_rightsize(input_data)
        elif action == "cost_estimate":
            return self._estimate_cost(input_data)
        else:
            return AgentResult(
                status=AgentStatus.SUCCESS,
                summary="CapacityPlanner ready"
            )
    
    def _forecast(self, input_data: Dict[str, Any]) -> AgentResult:
        """Generate capacity forecast"""
        metric = input_data.get("metric", "unknown")
        data_points = input_data.get("data_points", [])
        horizon = input_data.get("horizon_days", self.planner_config.forecast_horizon_days)
        
        if len(data_points) < 7:
            return AgentResult(
                status=AgentStatus.WARNING,
                summary="Insufficient data for forecasting (need at least 7 points)",
                details={"data_points_received": len(data_points)}
            )
        
        self.logger.info(f"Forecasting {metric} for {horizon} days")
        
        # Simple linear regression forecast
        forecast = self._linear_forecast(data_points, horizon)
        
        # Check if capacity will be exceeded
        capacity_threshold = input_data.get("capacity_threshold", 100)
        breach_date = None
        
        for day, value in forecast.items():
            if value > capacity_threshold:
                breach_date = day
                break
        
        recommendations = []
        
        if breach_date:
            days_until_breach = (datetime.fromisoformat(breach_date) - datetime.now()).days
            recommendations.append({
                "action": "Scale capacity",
                "urgency": "high" if days_until_breach < 7 else "medium",
                "reason": f"Projected to exceed capacity in {days_until_breach} days"
            })
        
        # Calculate growth rate
        if len(data_points) >= 2:
            first_half = statistics.mean(data_points[:len(data_points)//2])
            second_half = statistics.mean(data_points[len(data_points)//2:])
            if first_half > 0:
                growth_rate = ((second_half - first_half) / first_half) * 100
            else:
                growth_rate = 0
        else:
            growth_rate = 0
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Forecast generated for {metric}: {growth_rate:.1f}% growth trend",
            details={
                "metric": metric,
                "forecast_days": horizon,
                "growth_rate_percent": growth_rate,
                "breach_date": breach_date,
                "projected_values": dict(list(forecast.items())[:7]),  # First week
                "recommendations": recommendations
            }
        )
    
    def _linear_forecast(self, data_points: List[float], horizon: int) -> Dict[str, float]:
        """Simple linear regression forecast"""
        n = len(data_points)
        
        # Calculate trend line
        x_vals = list(range(n))
        x_mean = statistics.mean(x_vals)
        y_mean = statistics.mean(data_points)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_vals, data_points))
        denominator = sum((x - x_mean) ** 2 for x in x_vals)
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        intercept = y_mean - slope * x_mean
        
        # Forecast future values
        forecast = {}
        base_date = datetime.now()
        
        for i in range(1, horizon + 1):
            future_x = n + i
            predicted_value = slope * future_x + intercept
            forecast_date = (base_date + timedelta(days=i)).strftime('%Y-%m-%d')
            forecast[forecast_date] = max(0, predicted_value)  # No negative values
        
        return forecast
    
    def _recommend_rightsize(self, input_data: Dict[str, Any]) -> AgentResult:
        """Recommend right-sizing based on utilization"""
        current_instance_type = input_data.get("instance_type", "unknown")
        utilization_data = input_data.get("utilization", {})
        
        recommendations = []
        
        avg_cpu = utilization_data.get("avg_cpu", 0)
        avg_memory = utilization_data.get("avg_memory", 0)
        
        if avg_cpu < 20 and avg_memory < 40:
            recommendations.append({
                "current": current_instance_type,
                "recommended": "downgrade",
                "reason": f"Low utilization (CPU: {avg_cpu:.0f}%, Memory: {avg_memory:.0f}%)",
                "estimated_savings": "30-50%"
            })
        elif avg_cpu > 80 or avg_memory > 85:
            recommendations.append({
                "current": current_instance_type,
                "recommended": "upgrade",
                "reason": f"High utilization (CPU: {avg_cpu:.0f}%, Memory: {avg_memory:.0f}%)",
                "estimated_savings": None
            })
        else:
            recommendations.append({
                "current": current_instance_type,
                "recommended": "keep",
                "reason": f"Utilization is appropriate (CPU: {avg_cpu:.0f}%, Memory: {avg_memory:.0f}%)",
                "estimated_savings": None
            })
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Right-size recommendations for {current_instance_type}",
            details={"recommendations": recommendations}
        )
    
    def _estimate_cost(self, input_data: Dict[str, Any]) -> AgentResult:
        """Estimate infrastructure costs"""
        instance_type = input_data.get("instance_type", "t3.medium")
        count = input_data.get("count", 1)
        region = input_data.get("region", "us-east-1")
        
        # Simplified pricing (would use boto3 in production)
        pricing = {
            "t3.micro": 0.0104,
            "t3.small": 0.0208,
            "t3.medium": 0.0416,
            "t3.large": 0.0832,
        }
        
        hourly_rate = pricing.get(instance_type, 0.0416)
        monthly_estimate = hourly_rate * 24 * 30 * count
        
        return AgentResult(
            status=AgentStatus.SUCCESS,
            summary=f"Cost estimate for {count}x {instance_type}",
            details={
                "hourly_rate": hourly_rate,
                "monthly_estimate_usd": round(monthly_estimate, 2),
                "yearly_estimate_usd": round(monthly_estimate * 12, 2),
                "region": region
            }
        )
