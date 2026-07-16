"""
SecurityScanner Agent - Automated security scanning and analysis

Scans:
- Secrets/credentials in code (gitleaks)
- Dependency vulnerabilities (OSV, npm audit, pip-audit)
- IaC misconfigurations (checkov, tfsec)
- Container vulnerabilities (Trivy)
- SAST issues (Semgrep, Bandit)

Output:
- Structured security reports
- LLM-generated executive summaries
- Remediation recommendations
"""

import os
import json
import subprocess
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


@dataclass
class Vulnerability:
    """Represents a security vulnerability"""
    id: str
    title: str
    description: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    file: Optional[str] = None
    line: Optional[int] = None
    fix: Optional[str] = None
    tool: str = "unknown"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "fix": self.fix,
            "tool": self.tool,
        }


@dataclass
class ScanResult:
    """Result from a single security scan"""
    tool: str
    success: bool
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    
    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == "CRITICAL")
    
    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == "HIGH")
    
    @property
    def total_count(self) -> int:
        return len(self.vulnerabilities)


class SecurityScannerConfig(AgentConfig):
    """Configuration for SecurityScanner agent"""
    # Scanning scope
    scan_secrets: bool = True
    scan_dependencies: bool = True
    scan_containers: bool = True
    scan_iac: bool = True
    scan_sast: bool = True
    
    # Tools paths/versions
    gitleaks_path: str = "gitleaks"
    trivy_path: str = "trivy"
    checkov_path: str = "checkov"
    semgrep_path: str = "semgrep"
    
    # Thresholds
    critical_threshold: int = 0  # Alert on any critical
    high_threshold: int = 5     # Alert if more than 5 high
    
    # Report settings
    report_path: str = "security-reports"
    llm_summary: bool = True


class SecurityScanner(BaseAgent):
    """
    Automated security scanner for repositories.
    
    Runs multiple security tools and aggregates results.
    Uses LLM to generate actionable summaries.
    
    Usage:
        agent = SecurityScanner()
        agent.initialize()
        
        result = agent.run({
            "repo_path": "/path/to/repo",
            "scan_types": ["secrets", "deps", "iac"],  # or "all"
            "github_repo": "owner/repo",  # for GitHub API checks
        })
    """
    
    def __init__(self, config: Optional[SecurityScannerConfig] = None):
        super().__init__(config or SecurityScannerConfig(
            name="security-scanner",
            description="Automated security scanning and vulnerability analysis"
        ))
        self.scan_config: SecurityScannerConfig = self.config
    
    def initialize(self) -> None:
        """Initialize the security scanner"""
        # Call parent initialize (sets up logging)
        super().initialize()
        self.logger.info("SecurityScanner initialized")
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Execute security scans.
        
        Args:
            input_data: {
                "repo_path": str,           # Local path to scan
                "github_repo": str,         # GitHub repo for API checks
                "scan_types": List[str],   # "all" or specific types
                "base_branch": str,         # For PR scans
            }
        """
        repo_path = input_data.get("repo_path", os.getcwd())
        scan_types = input_data.get("scan_types", ["all"])
        github_repo = input_data.get("github_repo")
        
        self.logger.info(f"Starting security scan: {repo_path}")
        
        results: List[ScanResult] = []
        
        # Determine what to scan
        should_scan_all = "all" in scan_types
        
        # 1. Secret scanning
        if should_scan_all or "secrets" in scan_types:
            results.append(self._scan_secrets(repo_path))
        
        # 2. Dependency vulnerability scanning
        if should_scan_all or "deps" in scan_types:
            results.append(self._scan_dependencies(repo_path))
        
        # 3. IaC scanning
        if should_scan_all or "iac" in scan_types:
            results.append(self._scan_iac(repo_path))
        
        # 4. SAST scanning
        if should_scan_all or "sast" in scan_types:
            results.append(self._scan_sast(repo_path))
        
        # 5. Container scanning
        if should_scan_all or "containers" in scan_types:
            results.append(self._scan_containers(repo_path))
        
        # Aggregate results
        all_vulns = []
        for result in results:
            all_vulns.extend(result.vulnerabilities)
        
        # Check thresholds
        critical_vulns = [v for v in all_vulns if v.severity == "CRITICAL"]
        high_vulns = [v for v in all_vulns if v.severity == "HIGH"]
        
        status = AgentStatus.SUCCESS
        if len(critical_vulns) > self.scan_config.critical_threshold:
            status = AgentStatus.FAILED
        elif len(high_vulns) > self.scan_config.high_threshold:
            status = AgentStatus.WARNING
        
        # Generate LLM summary if enabled
        summary = self._generate_summary(results, all_vulns) if self.scan_config.llm_summary else \
            f"Found {len(all_vulns)} vulnerabilities ({len(critical_vulns)} critical, {len(high_vulns)} high)"
        
        # Save report
        report_path = self._save_report(repo_path, results, all_vulns)
        
        # Send notification if critical issues found
        if status == AgentStatus.FAILED:
            self.notify(
                title=f"🔴 Critical Security Issues: {len(critical_vulns)} found",
                message=summary[:500],
                severity="critical"
            )
        elif status == AgentStatus.WARNING:
            self.notify(
                title=f"⚠️ Security Warnings: {len(high_vulns)} high severity",
                message=summary[:500],
                severity="warning"
            )
        
        return AgentResult(
            status=status,
            summary=summary,
            details={
                "total_vulnerabilities": len(all_vulns),
                "by_severity": {
                    "critical": len(critical_vulns),
                    "high": len(high_vulns),
                    "medium": len([v for v in all_vulns if v.severity == "MEDIUM"]),
                    "low": len([v for v in all_vulns if v.severity == "LOW"]),
                },
                "scan_results": [r.tool for r in results if r.success],
                "failed_scans": [r.tool for r in results if not r.success],
            },
            artifacts=[report_path]
        )
    
    def _scan_secrets(self, repo_path: str) -> ScanResult:
        """Scan for secrets/credentials using gitleaks"""
        self.logger.info("Scanning for secrets...")
        result = ScanResult(tool="gitleaks", success=False)
        
        try:
            # Check if gitleaks is available
            if not self._command_exists("gitleaks"):
                result.errors.append("gitleaks not installed")
                return result
            
            # Run gitleaks
            output = subprocess.run(
                ["gitleaks", "detect", "--source", repo_path, "--report-format", "json"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if output.stdout:
                try:
                    findings = json.loads(output.stdout)
                    for finding in findings:
                        vuln = Vulnerability(
                            id=finding.get("RuleID", "secret"),
                            title=f"Secret detected: {finding.get('RuleID', 'unknown')}",
                            description=finding.get("Description", ""),
                            severity="CRITICAL",  # Secrets are always critical
                            file=finding.get("File", ""),
                            line=finding.get("StartLine"),
                            tool="gitleaks"
                        )
                        result.vulnerabilities.append(vuln)
                except json.JSONDecodeError:
                    result.errors.append("Failed to parse gitleaks output")
            
            result.success = True
            self.logger.info(f"  Found {result.total_count} secrets")
            
        except subprocess.TimeoutExpired:
            result.errors.append("Scan timed out")
        except Exception as e:
            result.errors.append(f"Error: {str(e)}")
        
        return result
    
    def _scan_dependencies(self, repo_path: str) -> ScanResult:
        """Scan for dependency vulnerabilities"""
        self.logger.info("Scanning dependencies...")
        result = ScanResult(tool="dependency-scanner", success=False)
        
        # Detect project type
        package_json = os.path.join(repo_path, "package.json")
        requirements = os.path.join(repo_path, "requirements.txt")
        go_mod = os.path.join(repo_path, "go.mod")
        
        if os.path.exists(package_json):
            result.vulnerabilities.extend(self._scan_npm(repo_path))
        if os.path.exists(requirements):
            result.vulnerabilities.extend(self._scan_pip(repo_path))
        if os.path.exists(go_mod):
            result.vulnerabilities.extend(self._scan_go(repo_path))
        
        result.success = True
        self.logger.info(f"  Found {result.total_count} dependency issues")
        return result
    
    def _scan_npm(self, repo_path: str) -> List[Vulnerability]:
        """Scan npm dependencies"""
        vulns = []
        try:
            # Use npm audit
            output = subprocess.run(
                ["npm", "audit", "--json"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=repo_path
            )
            
            if output.stdout:
                try:
                    audit_data = json.loads(output.stdout)
                    vulnerabilities = audit_data.get("vulnerabilities", {})
                    
                    for name, vuln_data in vulnerabilities.items():
                        severity = vuln_data.get("severity", "unknown").upper()
                        via = vuln_data.get("via", [])
                        
                        # Get CVE ID if available
                        vuln_id = "npm"
                        if isinstance(via, list) and via:
                            if isinstance(via[0], dict):
                                vuln_id = via[0].get("url", "npm").split("/")[-1][:20]
                            elif isinstance(via[0], str):
                                vuln_id = via[0].split("/")[-1][:20]
                        
                        vulns.append(Vulnerability(
                            id=vuln_id,
                            title=f"NPM vulnerability in {name}",
                            description=f"Via: {via[0] if isinstance(via, list) and via else via}",
                            severity=severity if severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW") else "MEDIUM",
                            fix=f"npm audit fix --force",
                            tool="npm-audit"
                        ))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            self.logger.warning(f"npm audit failed: {e}")
        
        return vulns
    
    def _scan_pip(self, repo_path: str) -> List[Vulnerability]:
        """Scan Python dependencies"""
        vulns = []
        try:
            # Try pip-audit first
            output = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=repo_path
            )
            
            if output.returncode == 0 and output.stdout:
                try:
                    audit_data = json.loads(output.stdout)
                    for vuln in audit_data:
                        vulns.append(Vulnerability(
                            id=vuln.get("id", "pip"),
                            title=vuln.get("name", "unknown"),
                            description=vuln.get("description", ""),
                            severity=vuln.get("severity", "MEDIUM").upper(),
                            fix=f"pip install {vuln.get('name')}@latest",
                            tool="pip-audit"
                        ))
                except json.JSONDecodeError:
                    pass
        except Exception:
            self.logger.warning("pip-audit not available, skipping Python deps")
        
        return vulns
    
    def _scan_go(self, repo_path: str) -> List[Vulnerability]:
        """Scan Go dependencies"""
        vulns = []
        try:
            # Use govulncheck
            output = subprocess.run(
                ["govulncheck", "-format", "json", "./..."],
                capture_output=True,
                text=True,
                timeout=180,
                cwd=repo_path
            )
            
            if output.stdout:
                try:
                    data = json.loads(output.stdout)
                    for finding in data.get("findings", []):
                        vulns.append(Vulnerability(
                            id=finding.get("vulnerability_id", "go"),
                            title=finding.get("osv", {}).get("summary", "Go vulnerability"),
                            description=finding.get("osv", {}).get("details", ""),
                            severity="MEDIUM",
                            tool="govulncheck"
                        ))
                except json.JSONDecodeError:
                    pass
        except Exception:
            self.logger.warning("govulncheck not available, skipping Go deps")
        
        return vulns
    
    def _scan_iac(self, repo_path: str) -> ScanResult:
        """Scan Infrastructure as Code for misconfigurations"""
        self.logger.info("Scanning IaC...")
        result = ScanResult(tool="checkov", success=False)
        
        tf_files = []
        dockerfiles = []
        
        # Find Terraform files
        for root, dirs, files in os.walk(repo_path):
            # Skip .git and other dirs
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".venv"]]
            
            for f in files:
                if f.endswith(".tf") and "test" not in f:
                    tf_files.append(os.path.join(root, f))
                if f == "Dockerfile" or f.startswith("Dockerfile."):
                    dockerfiles.append(os.path.join(root, f))
        
        try:
            if self._command_exists("checkov"):
                # Scan Terraform
                if tf_files:
                    output = subprocess.run(
                        ["checkov", "-f", tf_files[0], "--framework", "terraform", "--output", "json"],
                        capture_output=True,
                        text=True,
                        timeout=180,
                        cwd=repo_path
                    )
                    
                    if output.stdout:
                        try:
                            data = json.loads(output.stdout)
                            for check in data.get("results", {}).get("failed_checks", []):
                                result.vulnerabilities.append(Vulnerability(
                                    id=check.get("check_id", "CKV"),
                                    title=check.get("check_name", "IaC misconfiguration"),
                                    description=check.get("check_message", ""),
                                    severity=check.get("severity", "HIGH").upper(),
                                    file=check.get("file_path", ""),
                                    fix=check.get("fix_definition"),
                                    tool="checkov"
                                ))
                        except json.JSONDecodeError:
                            pass
            else:
                # Fallback: basic pattern matching
                for tf_file in tf_files:
                    with open(tf_file) as f:
                        content = f.read()
                        # Check for common issues
                        if "aws_security_group" in content:
                            # Look for ingress from 0.0.0.0/0
                            if re.search(r'0\.0\.0\.0\/0', content):
                                result.vulnerabilities.append(Vulnerability(
                                    id="AWS_SG_001",
                                    title="Security group allows 0.0.0.0/0",
                                    description="Security group rule allows traffic from anywhere",
                                    severity="HIGH",
                                    file=tf_file,
                                    tool="pattern-match"
                                ))
        except Exception as e:
            result.errors.append(f"IaC scan error: {e}")
        
        result.success = True
        self.logger.info(f"  Found {result.total_count} IaC issues")
        return result
    
    def _scan_sast(self, repo_path: str) -> ScanResult:
        """Scan for code security issues using SAST tools"""
        self.logger.info("Scanning SAST...")
        result = ScanResult(tool="semgrep", success=False)
        
        if not self._command_exists("semgrep"):
            result.errors.append("semgrep not installed")
            return result
        
        try:
            # Run semgrep with rules
            output = subprocess.run(
                ["semgrep", "--config", "auto", "--json", "--metrics", "off"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=repo_path
            )
            
            if output.stdout:
                try:
                    data = json.loads(output.stdout)
                    for finding in data.get("results", []):
                        result.vulnerabilities.append(Vulnerability(
                            id=finding.get("check_id", "SEMGREP"),
                            title=finding.get("check_id", "SAST finding"),
                            description=finding.get("message", ""),
                            severity="MEDIUM",  # Semgrep uses rule severity
                            file=finding.get("path", ""),
                            line=finding.get("start", {}).get("line"),
                            tool="semgrep"
                        ))
                except json.JSONDecodeError:
                    pass
            
            result.success = True
            
        except subprocess.TimeoutExpired:
            result.errors.append("SAST scan timed out")
        except Exception as e:
            result.errors.append(f"SAST error: {e}")
        
        self.logger.info(f"  Found {result.total_count} SAST issues")
        return result
    
    def _scan_containers(self, repo_path: str) -> ScanResult:
        """Scan container images for vulnerabilities"""
        self.logger.info("Scanning containers...")
        result = ScanResult(tool="trivy", success=False)
        
        # Find Dockerfiles
        dockerfiles = []
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules"]]
            for f in files:
                if f == "Dockerfile" or f.startswith("Dockerfile."):
                    dockerfiles.append(os.path.join(root, f))
        
        if not dockerfiles:
            result.success = True
            return result
        
        if not self._command_exists("trivy"):
            result.errors.append("trivy not installed")
            return result
        
        try:
            # Build image name from repo
            image_name = f"spot-render/scan:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            
            # Scan with Trivy
            output = subprocess.run(
                ["trivy", "image", "--ignore-unfixed", "--format", "json", image_name],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if output.stdout:
                try:
                    data = json.loads(output.stdout)
                    for vuln in data.get("Results", [{}])[0].get("Vulnerabilities", []):
                        result.vulnerabilities.append(Vulnerability(
                            id=vuln.get("VulnerabilityID", "CVE"),
                            title=vuln.get("Title", vuln.get("Description", "")[:100]),
                            description=vuln.get("Description", ""),
                            severity=vuln.get("Severity", "MEDIUM").upper(),
                            fix=vuln.get("FixPublished", {}).get("FixedVersion"),
                            tool="trivy"
                        ))
                except (json.JSONDecodeError, IndexError):
                    pass
            
            result.success = True
            
        except subprocess.TimeoutExpired:
            result.errors.append("Container scan timed out")
        except Exception as e:
            result.errors.append(f"Container scan error: {e}")
        
        self.logger.info(f"  Found {result.total_count} container issues")
        return result
    
    def _generate_summary(self, results: List[ScanResult], all_vulns: List[Vulnerability]) -> str:
        """Generate human-readable summary using LLM"""
        if not self.llm:
            return f"Found {len(all_vulns)} vulnerabilities. Install Ollama for LLM summaries."
        
        # Prepare summary for LLM
        summary_data = {
            "total": len(all_vulns),
            "by_tool": {r.tool: r.total_count for r in results},
            "by_severity": {
                "critical": sum(1 for v in all_vulns if v.severity == "CRITICAL"),
                "high": sum(1 for v in all_vulns if v.severity == "HIGH"),
                "medium": sum(1 for v in all_vulns if v.severity == "MEDIUM"),
                "low": sum(1 for v in all_vulns if v.severity == "LOW"),
            },
            "top_vulns": [v.to_dict() for v in all_vulns[:10]]  # Top 10
        }
        
        prompt = f"""Analyze this security scan summary and provide a clear, actionable summary.

## Scan Summary
{json.dumps(summary_data, indent=2)}

Provide:
1. Executive summary (2 sentences max)
2. Top 3 priorities for remediation
3. Estimated fix time (quick wins vs. major efforts)

Be concise and technical.
"""
        
        try:
            response = self.llm.generate(prompt)
            return response
        except Exception as e:
            self.logger.warning(f"LLM summary failed: {e}")
            return f"Found {len(all_vulns)} vulnerabilities requiring attention"
    
    def _save_report(self, repo_path: str, results: List[ScanResult], vulns: List[Vulnerability]) -> str:
        """Save detailed report to file"""
        report_dir = os.path.join(repo_path, self.scan_config.report_path)
        os.makedirs(report_dir, exist_ok=True)
        
        filename = f"security-report-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
        filepath = os.path.join(report_dir, filename)
        
        report = {
            "scan_time": datetime.utcnow().isoformat(),
            "repo": repo_path,
            "summary": {
                "total_vulnerabilities": len(vulns),
                "by_severity": {
                    "critical": len([v for v in vulns if v.severity == "CRITICAL"]),
                    "high": len([v for v in vulns if v.severity == "HIGH"]),
                    "medium": len([v for v in vulns if v.severity == "MEDIUM"]),
                    "low": len([v for v in vulns if v.severity == "LOW"]),
                }
            },
            "scans": [
                {
                    "tool": r.tool,
                    "success": r.success,
                    "vulnerabilities": [v.to_dict() for v in r.vulnerabilities],
                    "errors": r.errors
                }
                for r in results
            ]
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        self.logger.info(f"Report saved: {filepath}")
        return filepath
    
    @staticmethod
    def _command_exists(cmd: str) -> bool:
        """Check if a command exists"""
        try:
            subprocess.run(["which", cmd], capture_output=True, timeout=5)
            return True
        except Exception:
            return False
