#!/usr/bin/env python3
"""
AIOps Agents - Main Entry Point

Usage:
    python -m agents.main --agent security-scanner --repo /path/to/repo
    python -m agents.main --agent monitor --action status
    python -m agents.main --agent root-cause-analyzer --incident '{"title": "High latency"}'
"""

import os
import sys
import json
import argparse
import logging
from typing import Dict, Any

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.llm import LLMClient
from agents.security_scanner import SecurityScanner
from agents.documenter import Documenter
from agents.monitor import MonitorAgent
from agents.root_cause_analyzer import RootCauseAnalyzer
from agents.alert_generator import AlertGenerator
from agents.capacity_planner import CapacityPlanner
from agents.incident_responder import IncidentResponder


# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("aiops")


AGENTS = {
    "security-scanner": SecurityScanner,
    "documenter": Documenter,
    "monitor": MonitorAgent,
    "root-cause-analyzer": RootCauseAnalyzer,
    "alert-generator": AlertGenerator,
    "capacity-planner": CapacityPlanner,
    "incident-responder": IncidentResponder,
}


def run_agent(agent_name: str, agent_args: Dict[str, Any]) -> Dict[str, Any]:
    """Run an agent with the given arguments"""
    
    if agent_name not in AGENTS:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {list(AGENTS.keys())}")
    
    agent_class = AGENTS[agent_name]
    agent = agent_class()
    agent.initialize()
    
    result = agent.run(agent_args)
    
    return result.to_dict()


def main():
    parser = argparse.ArgumentParser(description="AIOps Agents")
    parser.add_argument(
        "--agent",
        "-a",
        choices=list(AGENTS.keys()),
        required=True,
        help="Agent to run"
    )
    parser.add_argument(
        "--repo",
        help="Repository path"
    )
    parser.add_argument(
        "--action",
        default="run",
        help="Action to perform"
    )
    parser.add_argument(
        "--incident",
        type=json.loads,
        help="Incident JSON"
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        help="Metrics to monitor"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Build input data
    input_data = {
        "action": args.action,
    }
    
    if args.repo:
        input_data["repo_path"] = args.repo
    if args.incident:
        input_data["incident"] = args.incident
    if args.metrics:
        input_data["metrics"] = args.metrics
    
    # Run agent
    try:
        result = run_agent(args.agent, input_data)
        
        print(json.dumps(result, indent=2, default=str))
        
        # Exit with error code if failed
        if result.get("status") == "failed":
            sys.exit(1)
        
    except Exception as e:
        logger.exception(f"Agent failed: {e}")
        print(json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
