"""
Base Agent - Abstract base class for all AIOps agents

All agents inherit from this class and implement:
- initialize(): Setup agent-specific resources
- execute(input_data): Main logic
- cleanup(): Release resources
"""

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from lib.llm import LLMClient, get_llm
from lib.notifications import NotificationClient, NotificationConfig
from lib.knowledge_base import KnowledgeBase, get_knowledge_base
from lib.approval_workflow import ApprovalWorkflow, get_approval_workflow, ApprovalLevel, ApprovalRequest


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class AgentConfig:
    """Base configuration for all agents"""
    name: str = "agent"
    description: str = ""
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    notification_channels: List[str] = field(default_factory=lambda: ["slack"])
    log_level: str = "INFO"
    enabled: bool = True
    
    @classmethod
    def from_env(cls, prefix: str = "AIOPS") -> "AgentConfig":
        """Load config from environment variables with prefix"""
        return cls(
            name=os.getenv(f"{prefix}_NAME", cls.__name__),
            description=os.getenv(f"{prefix}_DESCRIPTION", ""),
            llm_provider=os.getenv(f"{prefix}_LLM_PROVIDER", "ollama"),
            llm_model=os.getenv(f"{prefix}_LLM_MODEL", "llama3.2"),
            notification_channels=os.getenv(
                f"{prefix}_CHANNELS", "slack"
            ).split(","),
            log_level=os.getenv(f"{prefix}_LOG_LEVEL", "INFO"),
            enabled=os.getenv(f"{prefix}_ENABLED", "true").lower() == "true",
        )


@dataclass
class AgentResult:
    """Result from agent execution"""
    status: AgentStatus
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "status": self.status.value,
            "summary": self.summary,
            "details": self.details,
            "errors": self.errors,
            "artifacts": self.artifacts,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


class BaseAgent(ABC):
    """
    Abstract base class for AIOps agents.
    
    Usage:
        class MyAgent(BaseAgent):
            def __init__(self):
                super().__init__(AgentConfig(name="my-agent"))
            
            def initialize(self):
                # Setup resources
                pass
            
            def execute(self, input_data: Dict[str, Any]) -> AgentResult:
                # Main logic
                return AgentResult(status=AgentStatus.SUCCESS, summary="Done")
        """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.llm: Optional[LLMClient] = None
        self.notifier: Optional[NotificationClient] = None
        self.logger: Optional[logging.Logger] = None
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize agent resources (LLM, notifier, etc.)"""
        self._setup_logging()
        self._initialized = True

    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Execute the main agent logic (override in subclass)"""
        raise NotImplementedError
    
    def cleanup(self) -> None:
        """Cleanup resources (override if needed)"""
        self._initialized = False
    
    def run(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Run the agent with standard lifecycle.
        
        Args:
            input_data: Input data for the agent
            
        Returns:
            AgentResult with execution results
        """
        if not self._initialized:
            self.initialize()
        
        start_time = datetime.utcnow()
        
        try:
            self.logger.info(f"[{self.config.name}] Starting execution")
            result = self.execute(input_data)
            
            if result.status == AgentStatus.FAILED:
                self.logger.error(f"[{self.config.name}] Execution failed: {result.errors}")
            else:
                self.logger.info(f"[{self.config.name}] Completed: {result.summary}")
            
            return result
            
        except Exception as e:
            self.logger.exception(f"[{self.config.name}] Unexpected error")
            return AgentResult(
                status=AgentStatus.FAILED,
                summary=f"Agent failed with exception: {str(e)}",
                errors=[str(e)]
            )
        finally:
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.logger.info(f"[{self.config.name}] Duration: {duration:.2f}s")
    
    def _setup_logging(self):
        """Setup logging for the agent"""
        logger = logging.getLogger(f"aiops.{self.config.name}")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        self.logger = logger
    
    def _setup_llm(self) -> Optional[LLMClient]:
        """Setup LLM client (uses Ollama by default)"""
        try:
            client = get_llm()

            if client.is_available():
                self.logger.info(f"LLM available: Ollama/{client.model}")
                return client
            else:
                self.logger.warning("LLM not available. Start Ollama with: ollama serve")
                return None
        except Exception as e:
            self.logger.warning(f"LLM setup failed: {e}")
            return None
    
    def _setup_notifier(self) -> NotificationClient:
        """Setup notification client"""
        return NotificationClient(NotificationConfig.from_env())
    
    def notify(
        self,
        title: str,
        message: str,
        severity: str = "info",
        **kwargs
    ) -> None:
        """Send notification"""
        if self.notifier:
            self.notifier.notify(
                title=title,
                message=message,
                channels=self.config.notification_channels,
                **kwargs
            )
    
    def save_artifact(self, name: str, data: Dict[str, Any], path: str = "artifacts") -> str:
        """
        Save artifact to file.
        
        Returns:
            Path to saved artifact
        """
        os.makedirs(path, exist_ok=True)
        filename = f"{name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(path, filename)
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        self.logger.info(f"Artifact saved: {filepath}")
        return filepath


class ReusableAgent(BaseAgent):
    """
    Agent that can be reused across multiple executions.

    Use this for agents that are called frequently.
    Features:
    - Knowledge base integration for learning from past incidents
    - Human approval workflow for production/critical changes
    - Automatic incident storage for future reference
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._initialized = False
        self.kb: Optional[KnowledgeBase] = None
        self.approval: Optional[ApprovalWorkflow] = None

    def initialize(self) -> None:
        """Setup agent resources once"""
        if self._initialized:
            return

        self._setup_logging()
        self.llm = self._setup_llm()
        self.notifier = self._setup_notifier()
        self.kb = get_knowledge_base()
        self.approval = get_approval_workflow()
        self._initialized = True

    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """Override in subclass"""
        raise NotImplementedError

    def find_similar_incidents(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar past incidents from the knowledge base.
        """
        if not self.kb:
            return []
        return self.kb.find_similar_incidents(query, limit=limit)

    def get_preventive_measures(self, incident_type: str) -> List[str]:
        """
        Get preventive measures for a type of incident.
        """
        if not self.kb:
            return []
        return self.kb.get_preventive_measures(incident_type)

    def store_incident(self, incident: Dict[str, Any]) -> str:
        """
        Store incident in knowledge base for future learning.
        """
        if not self.kb:
            return ""
        return self.kb.store_incident(incident)

    def requires_approval(
        self,
        action: str,
        environment: str = "production"
    ) -> bool:
        """
        Check if an action requires human approval.
        """
        if not self.approval:
            return True  # Default to requiring approval if not configured
        return self.approval.requires_approval(action, environment)

    def request_approval(
        self,
        action: str,
        description: str,
        target: str,
        environment: str = "production"
    ) -> Optional[ApprovalRequest]:
        """
        Request human approval for an action.

        Returns None if approval is not required or auto-approved.
        Returns ApprovalRequest if approval is needed.
        """
        if not self.approval:
            return None

        if not self.requires_approval(action, environment):
            return None

        # Check if can auto-approve
        if self.approval.auto_approve_if_safe(action, environment):
            self.logger.info(f"Action '{action}' auto-approved (low risk in {environment})")
            return None

        # Create approval request
        request = self.approval.create_request(
            action=action,
            description=description,
            target=target,
            environment=environment,
            requested_by=self.config.name
        )

        # Send notification for approval
        if self.notifier:
            message = self.approval.format_approval_message(request)
            self.notify(
                title=f"Approval Required: {action}",
                message=message,
                severity="warning"
            )

        return request

    def wait_for_approval(self, request, timeout: int = 3600) -> bool:
        """
        Wait for approval on a request.

        Returns True if approved, False otherwise.
        """
        if not self.approval:
            return False

        self.logger.info(f"Waiting for approval: {request.id}")

        # In a real implementation, this would integrate with
        # Slack reactions, PagerDuty, etc.
        # For now, we'll send a notification and wait.

        if self.notifier:
            self.notify(
                title=f"⏳ Awaiting Approval: {request.action}",
                message=f"Request ID: `{request.id}`\n\nPlease approve or reject.",
                severity="info"
            )

        return self.approval.wait_for_approval(request, timeout=timeout)
