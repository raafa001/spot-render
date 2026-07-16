"""
Knowledge Base - Learns from past incidents, runbooks, and postmortems

This module provides a knowledge base that agents can query to:
- Find similar past incidents
- Get recommendations from postmortems
- Learn from previous resolutions
"""

import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import re


class KnowledgeBase:
    """
    Knowledge base for AIOps agents.
    
    Stores and retrieves:
    - Past incidents and resolutions
    - Runbooks and playbooks
    - Postmortems
    - Security findings
    - Common patterns
    
    Usage:
        kb = KnowledgeBase("/path/to/docs")
        similar = kb.find_similar_incidents("high latency")
        recommendations = kb.get_recommendations("database")
    """
    
    def __init__(self, base_path: str = "docs"):
        self.base_path = Path(base_path)
        self._cache: Dict[str, Any] = {}
    
    def find_similar_incidents(
        self,
        query: str,
        limit: int = 5,
        category: str = "postmortems"
    ) -> List[Dict[str, Any]]:
        """
        Find incidents similar to the query.
        
        Uses keyword matching and pattern recognition.
        """
        results = []
        query_lower = query.lower()
        
        # Keywords to look for
        keywords = self._extract_keywords(query_lower)
        
        postmortem_dir = self.base_path / category
        if not postmortem_dir.exists():
            return results
        
        for md_file in postmortem_dir.glob("*.md"):
            try:
                content = md_file.read_text().lower()
                
                # Calculate relevance score
                score = 0
                for keyword in keywords:
                    if keyword in content:
                        score += content.count(keyword)
                
                # Check for exact phrase match
                if query_lower in content:
                    score += 10
                
                if score > 0:
                    results.append({
                        "file": str(md_file),
                        "title": self._extract_title(md_file.read_text()),
                        "score": score,
                        "date": self._extract_date(md_file)
                    })
            except Exception:
                continue
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]
    
    def get_recommendations(
        self,
        topic: str,
        doc_type: str = "postmortems"
    ) -> List[str]:
        """
        Get action item recommendations for a topic.
        
        Extracts action items and preventive measures related to the topic.
        """
        recommendations = []
        topic_lower = topic.lower()
        
        doc_dir = self.base_path / doc_type
        if not doc_dir.exists():
            return recommendations
        
        for md_file in doc_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                
                # Look for action items section
                in_actions = False
                for line in content.split("\n"):
                    if "## Action Items" in line or "## Action Items" in line:
                        in_actions = True
                        continue
                    
                    if in_actions:
                        if line.startswith("## "):
                            break
                        if line.strip().startswith("- [ ]") or line.strip().startswith("- "):
                            if topic_lower in line.lower():
                                recommendations.append(line.strip())
            except Exception:
                continue
        
        return list(set(recommendations))[:10]  # Dedupe and limit
    
    def get_preventive_measures(
        self,
        incident_type: str
    ) -> List[str]:
        """
        Get preventive measures for a type of incident.
        """
        measures = []
        
        postmortems = self.find_similar_incidents(incident_type, limit=10)
        
        for pm in postmortems:
            try:
                content = Path(pm["file"]).read_text()
                
                # Extract preventive measures section
                in_section = False
                for line in content.split("\n"):
                    if "## Preventive Measures" in line or "## Preventive" in line:
                        in_section = True
                        continue
                    
                    if in_section:
                        if line.startswith("## "):
                            break
                        if line.strip().startswith("- ") or line.strip().startswith("* "):
                            measure = line.strip().lstrip("-* ").strip()
                            if measure:
                                measures.append(measure)
            except Exception:
                continue
        
        return list(set(measures))[:10]
    
    def get_runbook(self, topic: str) -> Optional[str]:
        """
        Get runbook for a topic.
        """
        runbook_dir = self.base_path / "runbooks"
        if not runbook_dir.exists():
            return None
        
        topic_lower = topic.lower()
        
        for md_file in runbook_dir.glob("*.md"):
            if topic_lower in md_file.stem.lower():
                return md_file.read_text()
        
        return None
    
    def store_incident(
        self,
        incident: Dict[str, Any],
        category: str = "incidents"
    ) -> str:
        """
        Store a new incident in the knowledge base.
        """
        incident_dir = self.base_path / category
        incident_dir.mkdir(parents=True, exist_ok=True)
        
        incident_id = incident.get("id", datetime.now().strftime("%Y%m%d-%H%M%S"))
        filename = f"{incident_id}.json"
        filepath = incident_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(incident, f, indent=2, default=str)
        
        return str(filepath)
    
    def store_postmortem(
        self,
        postmortem: str,
        incident_id: str
    ) -> str:
        """
        Store a generated postmortem.
        """
        pm_dir = self.base_path / "postmortems"
        pm_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"postmortem-{incident_id}-{datetime.now().strftime('%Y%m%d')}.md"
        filepath = pm_dir / filename
        
        with open(filepath, "w") as f:
            f.write(postmortem)
        
        return str(filepath)
    
    def get_incident_history(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get recent incident history.
        """
        incidents = []
        
        incident_dir = self.base_path / "incidents"
        if not incident_dir.exists():
            return incidents
        
        for json_file in sorted(incident_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
            try:
                with open(json_file) as f:
                    incidents.append(json.load(f))
            except Exception:
                continue
        
        return incidents
    
    def find_root_causes(self, pattern: str) -> List[str]:
        """
        Find known root causes matching a pattern.
        """
        root_causes = []
        pattern_lower = pattern.lower()
        
        postmortem_dir = self.base_path / "postmortems"
        if not postmortem_dir.exists():
            return root_causes
        
        for md_file in postmortem_dir.glob("*.md"):
            try:
                content = md_file.read_text()
                
                # Look for root cause section
                in_section = False
                for line in content.split("\n"):
                    if "## Root Cause" in line or "**Root Cause:**" in line:
                        in_section = True
                        continue
                    
                    if in_section:
                        if line.startswith("## "):
                            break
                        if pattern_lower in line.lower():
                            # Clean and add
                            cause = line.replace("**Root Cause:**", "").replace("*", "").strip()
                            if cause and cause != "Root Cause":
                                root_causes.append(cause)
            except Exception:
                continue
        
        return list(set(root_causes))[:10]
    
    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract important keywords from text"""
        # Remove common words
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "when", "where", "why", "how"
        }
        
        # Extract words
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter short words and stopwords
        keywords = [w for w in words if len(w) > 3 and w not in stopwords]
        
        # Return unique keywords
        return list(set(keywords))[:20]
    
    @staticmethod
    def _extract_title(content: str) -> str:
        """Extract title from markdown content"""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return "Untitled"
    
    @staticmethod
    def _extract_date(filepath: Path) -> str:
        """Extract date from filename or metadata"""
        filename = filepath.stem
        # Try to extract date from filename
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', filename)
        if date_match:
            return date_match.group()
        return str(filepath.stat().st_mtime)


# Global instance
_knowledge_base: Optional[KnowledgeBase] = None

def get_knowledge_base(base_path: str = "docs") -> KnowledgeBase:
    """Get the global knowledge base instance"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = KnowledgeBase(base_path)
    return _knowledge_base
