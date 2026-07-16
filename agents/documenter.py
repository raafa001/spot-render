"""
Documenter Agent - Automated documentation generation

Generates:
- README.md from code structure
- API documentation from code
- Architecture diagrams (Mermaid)
- Runbooks from workflows
- Changelog from git history

Uses LLM to analyze code and produce human-readable docs.
"""

import os
import re
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

from agents.base import BaseAgent, AgentConfig, AgentResult, AgentStatus


@dataclass
class DocConfig(AgentConfig):
    """Configuration for Documenter agent"""
    docs_path: str = "docs"
    readme_template: str = "default"
    include_api: bool = True
    include_architecture: bool = True
    include_runbooks: bool = True
    output_format: str = "markdown"


class Documenter(BaseAgent):
    """
    Automated documentation generator.
    
    Analyzes repository structure, code, and workflows
    to generate comprehensive documentation.
    
    Usage:
        agent = Documenter()
        agent.initialize()
        
        result = agent.run({
            "repo_path": "/path/to/repo",
            "doc_types": ["readme", "api", "architecture"],
        })
    """
    
    # File patterns for language detection
    LANGUAGE_PATTERNS = {
        "python": ["*.py", "requirements*.txt", "setup.py", "pyproject.toml"],
        "javascript": ["*.js", "*.ts", "package.json", "*.jsx", "*.tsx"],
        "go": ["*.go", "go.mod", "go.sum"],
        "terraform": ["*.tf", "*.tfvars"],
        "docker": ["Dockerfile*", "docker-compose*.yml"],
        "kubernetes": ["*.yaml", "*.yml", "helm/**"],
    }
    
    # API endpoint patterns
    API_PATTERNS = {
        "python": {
            "fastapi": r"@(app|router)\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]",
            "flask": r"@(app|blueprint)\.(route|get|post|put|delete)\(['\"]([^'\"]+)['\"]",
            "django": r"@(path|route)['\"]([^'\"]+)['\"",
        },
        "javascript": {
            "express": r"(app|router)\.(get|post|put|patch|delete)\(['\"]([^'\"]+)['\"]",
            "next": r"(get|post|put|delete)['\s]*\(['\"]([^'\"]+)['\"]",
        }
    }
    
    def __init__(self, config: Optional[DocConfig] = None):
        super().__init__(config or DocConfig(
            name="documenter",
            description="Automated documentation generation"
        ))
        self.doc_config: DocConfig = self.config
    
    def execute(self, input_data: Dict[str, Any]) -> AgentResult:
        """
        Generate documentation for a repository.
        
        Args:
            input_data: {
                "repo_path": str,
                "doc_types": List[str],  # "readme", "api", "architecture", "all"
                "output_path": str,      # Optional custom path
            }
        """
        repo_path = input_data.get("repo_path", os.getcwd())
        doc_types = input_data.get("doc_types", ["all"])
        output_path = input_data.get("output_path", self.doc_config.docs_path)
        
        self.logger.info(f"Generating documentation for: {repo_path}")
        
        docs_generated = []
        errors = []
        
        should_generate_all = "all" in doc_types
        
        # Detect language/framework
        language = self._detect_language(repo_path)
        self.logger.info(f"Detected language: {language}")
        
        # Generate README
        if should_generate_all or "readme" in doc_types:
            try:
                readme_path = self._generate_readme(repo_path, language)
                if readme_path:
                    docs_generated.append(readme_path)
            except Exception as e:
                errors.append(f"README generation failed: {e}")
        
        # Generate API docs
        if should_generate_all or "api" in doc_types:
            try:
                api_docs = self._generate_api_docs(repo_path, language)
                if api_docs:
                    docs_generated.extend(api_docs)
            except Exception as e:
                errors.append(f"API docs generation failed: {e}")
        
        # Generate architecture docs
        if should_generate_all or "architecture" in doc_types:
            try:
                arch_path = self._generate_architecture_docs(repo_path)
                if arch_path:
                    docs_generated.append(arch_path)
            except Exception as e:
                errors.append(f"Architecture docs generation failed: {e}")
        
        # Generate runbooks from workflows
        if should_generate_all or "runbooks" in doc_types:
            try:
                runbook_path = self._generate_runbooks(repo_path)
                if runbook_path:
                    docs_generated.append(runbook_path)
            except Exception as e:
                errors.append(f"Runbook generation failed: {e}")
        
        status = AgentStatus.SUCCESS if len(errors) == 0 else AgentStatus.WARNING
        
        return AgentResult(
            status=status,
            summary=f"Generated {len(docs_generated)} documentation files",
            details={
                "language": language,
                "docs_generated": docs_generated,
                "doc_types": doc_types,
            },
            errors=errors,
            artifacts=docs_generated
        )
    
    def _detect_language(self, repo_path: str) -> str:
        """Detect the primary language of the repository"""
        language_counts = {}
        
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            count = 0
            for pattern in patterns:
                # Simple file existence check
                if "*" in pattern:
                    # Glob pattern
                    import glob
                    files = glob.glob(os.path.join(repo_path, "**", pattern), recursive=True)
                    count += len(files)
                else:
                    if os.path.exists(os.path.join(repo_path, pattern)):
                        count += 1
            
            if count > 0:
                language_counts[lang] = count
        
        if not language_counts:
            return "unknown"
        
        return max(language_counts, key=language_counts.get)
    
    def _generate_readme(self, repo_path: str, language: str) -> Optional[str]:
        """Generate README.md for the repository"""
        # Check if README already exists
        readme_path = os.path.join(repo_path, "README.md")
        has_existing_readme = os.path.exists(readme_path)
        
        if has_existing_readme:
            self.logger.info("README.md exists, analyzing for update...")
            with open(readme_path) as f:
                existing_content = f.read()
        else:
            existing_content = ""
        
        # Gather repo info
        info = self._gather_repo_info(repo_path, language)
        
        # Use LLM to generate or update README
        if self.llm:
            prompt = self._build_readme_prompt(info, language, existing_content)
            
            try:
                new_content = self.llm.generate(prompt)
                
                with open(readme_path, "w") as f:
                    f.write(new_content)
                
                self.logger.info(f"README.md generated/updated: {readme_path}")
                return readme_path
            except Exception as e:
                self.logger.warning(f"LLM README generation failed: {e}")
        
        # Fallback: basic README
        return self._generate_basic_readme(repo_path, info)
    
    def _gather_repo_info(self, repo_path: str, language: str) -> Dict[str, Any]:
        """Gather information about the repository"""
        info = {
            "name": os.path.basename(repo_path),
            "language": language,
            "files": [],
            "dependencies": [],
            "endpoints": [],
            "workflows": [],
            "structure": [],
        }
        
        # List key files
        for root, dirs, files in os.walk(repo_path):
            # Skip unnecessary directories
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".venv", ".pytest_cache"]]
            
            rel_root = os.path.relpath(root, repo_path)
            for f in files:
                if f.startswith("."):
                    continue
                
                filepath = os.path.join(rel_root, f)
                info["files"].append(filepath)
                
                # Check for dependencies
                if f == "requirements.txt":
                    info["dependencies"].extend(self._parse_requirements(os.path.join(root, f)))
                elif f == "package.json":
                    info["dependencies"].extend(self._parse_package_json(os.path.join(root, f)))
        
        # Find API endpoints
        info["endpoints"] = self._find_api_endpoints(repo_path, language)
        
        # Find workflows
        workflow_dir = os.path.join(repo_path, ".github", "workflows")
        if os.path.exists(workflow_dir):
            for f in os.listdir(workflow_dir):
                if f.endswith(".yml") or f.endswith(".yaml"):
                    info["workflows"].append(f)
        
        # Get git description if available
        try:
            desc = subprocess.run(
                ["git", "describe", "--all", "--long"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=repo_path
            )
            if desc.returncode == 0:
                info["version"] = desc.stdout.strip()
        except Exception:
            pass
        
        return info
    
    def _find_api_endpoints(self, repo_path: str, language: str) -> List[Dict[str, str]]:
        """Find API endpoints in the codebase"""
        endpoints = []
        
        if language not in ["python", "javascript"]:
            return endpoints
        
        patterns = self.API_PATTERNS.get(language, {})
        
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules"]]
            
            for f in files:
                filepath = os.path.join(root, f)
                
                # Determine framework
                framework = "unknown"
                if "fastapi" in f or "flask" in f or language == "python":
                    if f.endswith(".py"):
                        framework = "python"
                elif f.endswith((".js", ".ts", ".jsx", ".tsx")):
                    if "express" in f or "next" in f:
                        framework = "javascript"
                
                if framework == "unknown":
                    continue
                
                try:
                    with open(filepath) as file:
                        content = file.read()
                    
                    # Find route patterns
                    route_pattern = None
                    if framework == "python":
                        if "fastapi" in content:
                            route_pattern = self.API_PATTERNS["python"]["fastapi"]
                        elif "flask" in content:
                            route_pattern = self.API_PATTERNS["python"]["flask"]
                    elif framework == "javascript":
                        if "express" in content:
                            route_pattern = self.API_PATTERNS["javascript"]["express"]
                    
                    if route_pattern:
                        for match in re.finditer(route_pattern, content):
                            endpoints.append({
                                "path": match.group(2) if len(match.groups()) > 1 else match.group(1),
                                "method": match.group(1).upper() if len(match.groups()) > 1 else "GET",
                                "file": os.path.relpath(filepath, repo_path)
                            })
                except Exception:
                    pass
        
        return endpoints[:20]  # Limit to 20 endpoints
    
    def _parse_requirements(self, filepath: str) -> List[str]:
        """Parse requirements.txt"""
        deps = []
        try:
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("-"):
                        # Remove version specifiers
                        dep = re.split(r"[=<>!~]", line)[0].strip()
                        if dep:
                            deps.append(dep)
        except Exception:
            pass
        return deps[:10]  # Limit to 10
    
    def _parse_package_json(self, filepath: str) -> List[str]:
        """Parse package.json for dependencies"""
        import json
        deps = []
        try:
            with open(filepath) as f:
                data = json.load(f)
                deps = list(data.get("dependencies", {}).keys())[:10]
        except Exception:
            pass
        return deps
    
    def _build_readme_prompt(self, info: Dict, language: str, existing: str) -> str:
        """Build prompt for LLM to generate README"""
        
        endpoints_md = ""
        if info.get("endpoints"):
            endpoints_md = "## API Endpoints\n\n"
            endpoints_md += "| Method | Path | File |\n|--------|------|------|\n"
            for ep in info["endpoints"]:
                endpoints_md += f"| {ep['method']} | {ep['path']} | `{ep['file']}` |\n"
        
        dependencies_md = ""
        if info.get("dependencies"):
            dependencies_md = "## Dependencies\n\n" + ", ".join([f"`{d}`" for d in info["dependencies"]]) + "\n"
        
        workflows_md = ""
        if info.get("workflows"):
            workflows_md = "## CI/CD Workflows\n\n" + "\n".join([f"- {w}" for w in info["workflows"]]) + "\n"
        
        prompt = f"""Generate a comprehensive README.md for this project.

## Project Info
- Name: {info['name']}
- Language: {info['language']}
- Version: {info.get('version', 'N/A')}

## File Structure
```
{chr(10).join(info['files'][:30])}
```

{dependencies_md}

{endpoints_md}

{workflows_md}

## Requirements
- Generate in English
- Include: Overview, Quick Start, Configuration, Architecture, API (if applicable)
- Use badges where appropriate (license, build status, version)
- Make it professional and complete

{f"## Existing README (for updates)\n\n{existing[:500]}...\n\n" if existing else ""}

Generate the complete README.md content.
"""
        return prompt
    
    def _generate_basic_readme(self, repo_path: str, info: Dict) -> str:
        """Generate a basic README without LLM"""
        readme_path = os.path.join(repo_path, "README.md")
        
        content = f"""# {info['name']}

> Generated documentation

## Overview

{info['language'].title()} project.

## Quick Start

```bash
# Install dependencies
{"pip install -r requirements.txt" if info['language'] == 'python' else "npm install"}
```

## Project Structure

"""
        for f in info["files"][:20]:
            content += f"- `{f}`\n"
        
        with open(readme_path, "w") as f:
            f.write(content)
        
        return readme_path
    
    def _generate_api_docs(self, repo_path: str, language: str) -> List[str]:
        """Generate API documentation"""
        docs_generated = []
        
        if language not in ["python", "javascript"]:
            return docs_generated
        
        endpoints = self._find_api_endpoints(repo_path, language)
        
        if not endpoints:
            return docs_generated
        
        # Generate API docs using LLM
        if self.llm:
            prompt = f"""Generate API documentation in Markdown for these endpoints:

{chr(10).join([f"- {ep['method']} {ep['path']} ({ep['file']})" for ep in endpoints])}

Include:
1. Overview section
2. Endpoint table with descriptions
3. Request/Response examples (placeholder)
4. Error codes

Format as proper Markdown API documentation.
"""
            try:
                docs_content = self.llm.generate(prompt)
                
                docs_dir = os.path.join(repo_path, self.doc_config.docs_path, "api")
                os.makedirs(docs_dir, exist_ok=True)
                
                api_docs_path = os.path.join(docs_dir, "README.md")
                with open(api_docs_path, "w") as f:
                    f.write(docs_content)
                
                docs_generated.append(api_docs_path)
            except Exception as e:
                self.logger.warning(f"LLM API docs generation failed: {e}")
        
        return docs_generated
    
    def _generate_architecture_docs(self, repo_path: str) -> Optional[str]:
        """Generate architecture documentation with diagrams"""
        # Gather architecture info
        structure = self._get_directory_tree(repo_path)
        
        # Detect services/components
        components = self._detect_components(repo_path)
        
        # Generate Mermaid diagram
        mermaid_diagram = self._generate_mermaid_diagram(components)
        
        prompt = f"""Generate architecture documentation for this project.

## Directory Structure
```
{structure}
```

## Detected Components
{chr(10).join([f"- {c}" for c in components])}

## Mermaid Diagram
```mermaid
{mermaid_diagram}
```

Generate:
1. Architecture Overview
2. Component Description
3. Data Flow
4. Infrastructure notes (if applicable)

Use the Mermaid diagram provided.
"""
        
        if self.llm:
            try:
                docs_content = self.llm.generate(prompt)
                
                docs_dir = os.path.join(repo_path, self.doc_config.docs_path, "architecture")
                os.makedirs(docs_dir, exist_ok=True)
                
                arch_docs_path = os.path.join(docs_dir, "README.md")
                with open(arch_docs_path, "w") as f:
                    f.write(docs_content)
                
                return arch_docs_path
            except Exception as e:
                self.logger.warning(f"LLM architecture docs generation failed: {e}")
        
        return None
    
    def _get_directory_tree(self, repo_path: str, max_depth: int = 3) -> str:
        """Get directory tree structure"""
        tree = []
        
        for root, dirs, files in os.walk(repo_path):
            depth = root[len(repo_path):].count(os.sep)
            if depth > max_depth:
                continue
            
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", "__pycache__", ".venv"]]
            
            indent = "  " * depth
            tree.append(f"{indent}{os.path.basename(root)}/")
            
            for f in files[:5]:  # Limit files per directory
                if not f.startswith("."):
                    tree.append(f"{indent}  {f}")
            if len(files) > 5:
                tree.append(f"{indent}  ... ({len(files) - 5} more)")
        
        return "\n".join(tree)
    
    def _detect_components(self, repo_path: str) -> List[str]:
        """Detect components/services in the codebase"""
        components = []
        
        # Look for service patterns
        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules"]]
            
            # Check for specific patterns
            if "api" in root.lower():
                components.append("API Service")
            if "web" in root.lower() or "frontend" in root.lower() or "portal" in root.lower():
                components.append("Frontend/Web UI")
            if "worker" in root.lower() or "job" in root.lower():
                components.append("Background Worker")
            if "scheduler" in root.lower():
                components.append("Job Scheduler")
            if "terraform" in root.lower() or "infra" in root.lower():
                components.append("Infrastructure")
        
        return list(set(components))[:10]
    
    def _generate_mermaid_diagram(self, components: List[str]) -> str:
        """Generate a Mermaid diagram for the architecture"""
        diagram = "graph TD\n"
        
        # Add nodes
        for i, comp in enumerate(components):
            node_id = f"C{i+1}"
            diagram += f"    {node_id}[{comp}]\n"
        
        # Add basic relationships if multiple components
        if len(components) > 1:
            for i in range(len(components) - 1):
                diagram += f"    C{i+1} --> C{i+2}\n"
        
        return diagram
    
    def _generate_runbooks(self, repo_path: str) -> Optional[str]:
        """Generate runbooks from GitHub workflows"""
        workflow_dir = os.path.join(repo_path, ".github", "workflows")
        
        if not os.path.exists(workflow_dir):
            return None
        
        workflows = []
        for f in os.listdir(workflow_dir):
            if f.endswith((".yml", ".yaml")):
                workflows.append(f)
        
        if not workflows:
            return None
        
        # Generate runbook content
        prompt = f"""Generate operational runbooks based on these CI/CD workflows:

{chr(10).join([f"- {w}" for w in workflows])}

For each workflow, document:
1. What it does
2. When it runs (trigger)
3. How to troubleshoot failures
4. Common issues and fixes

Format as a Markdown runbook document.
"""
        
        if self.llm:
            try:
                runbook_content = self.llm.generate(prompt)
                
                docs_dir = os.path.join(repo_path, self.doc_config.docs_path, "runbooks")
                os.makedirs(docs_dir, exist_ok=True)
                
                runbook_path = os.path.join(docs_dir, "README.md")
                with open(runbook_path, "w") as f:
                    f.write(runbook_content)
                
                return runbook_path
            except Exception as e:
                self.logger.warning(f"LLM runbook generation failed: {e}")
        
        return None
