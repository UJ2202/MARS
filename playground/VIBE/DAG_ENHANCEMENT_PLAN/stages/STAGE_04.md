# Stage 4: Skill Extraction and Pattern Recognition

**Phase:** 2 - Visualization and Skill Extraction
**Estimated Time:** 60 minutes
**Dependencies:** Stages 1, 2, & 3 must be complete
**Risk Level:** Medium

## Objectives

1. Implement pattern recognition from execution events
2. Extract reusable skills from successful workflows
3. Create skill templates with parameterization
4. Build skill library and storage system
5. Enable skill search and discovery
6. Implement repeatability validation
7. Support skill export and import

## Current State Analysis

### What We Have
- Complete execution event history (from Stages 1-2)
- Execution summaries on DAG nodes (from Stage 3)
- Multiple workflow runs with varied patterns
- File and message associations
- Success/failure metrics

### What We Need
- Pattern matching algorithms
- Skill template format
- Skill extraction logic
- Skill storage/retrieval system
- Validation framework
- Repeatability testing

## Pre-Stage Verification

### Check Prerequisites
1. Stages 1-3 complete and verified
2. Multiple workflow runs in database
3. Execution events captured
4. Node metadata enriched
5. Can query events by pattern

### Verification Commands
```bash
# Check workflow runs
python -c "from cmbagent.database import get_db_session, WorkflowRun; print(f'Workflow runs: {get_db_session().query(WorkflowRun).count()}')"

# Check events
python -c "from cmbagent.database import get_db_session, ExecutionEvent; print(f'Events: {get_db_session().query(ExecutionEvent).count()}')"
```

## Implementation Tasks

### Task 1: Define Skill Model

**Objective:** Create data model for skills

**Implementation:**

Add to `cmbagent/database/models.py`:

```python
class Skill(Base):
    """Extracted reusable skill from workflows."""
    __tablename__ = "skills"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), 
                       nullable=False, index=True)
    
    # Identification
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0.0")
    
    # Pattern
    pattern = Column(JSON, nullable=False)  # Sequence of steps
    parameters = Column(JSON, nullable=False)  # Required/optional parameters
    
    # Extraction metadata
    extracted_from = Column(JSON, nullable=False)  # List of run_ids/node_ids
    extraction_method = Column(String(100), nullable=False)  # manual, automatic, hybrid
    extracted_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # Success metrics
    times_used = Column(Integer, nullable=False, default=0)
    success_rate = Column(Numeric(5, 4), nullable=True)  # 0.0 to 1.0
    avg_duration_seconds = Column(Integer, nullable=True)
    avg_cost_usd = Column(Numeric(10, 6), nullable=True)
    
    # Categorization
    category = Column(String(100), nullable=True, index=True)
    tags = Column(JSON, nullable=True)  # List of tags
    
    # Validation
    validated = Column(Boolean, nullable=False, default=False)
    validation_results = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default="active", index=True)
    # Status: active, deprecated, experimental
    
    # Metadata
    meta = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=lambda: datetime.now(timezone.utc))
    last_used_at = Column(TIMESTAMP, nullable=True)
    
    # Relationships
    session = relationship("Session", back_populates="skills")
    
    __table_args__ = (
        Index("idx_skills_name", "name"),
        Index("idx_skills_category", "category"),
        Index("idx_skills_status", "status"),
    )
```

Add to Session model relationships:

```python
# In Session class
skills = relationship("Skill", back_populates="session", cascade="all, delete-orphan")
```

Create migration:

```bash
cd cmbagent/database
alembic revision --autogenerate -m "add_skills_table"
alembic upgrade head
```

**Files to Modify:**
- `cmbagent/database/models.py`

**Files to Create:**
- New Alembic migration for skills table

**Verification:**
- Skill model created
- Migration applied
- Can create Skill instances

### Task 2: Implement Pattern Matcher

**Objective:** Find common patterns in execution events

**Implementation:**

Create `cmbagent/skills/pattern_matcher.py`:

```python
"""
Pattern Matcher for Skill Extraction

Identifies common execution patterns from workflow events.
"""

from typing import List, Dict, Any, Tuple
from collections import Counter
from sqlalchemy.orm import Session

from cmbagent.database import EventRepository, ExecutionEvent


class PatternMatcher:
    """Identifies patterns in execution events."""
    
    def __init__(self, db_session: Session, session_id: str):
        self.db = db_session
        self.session_id = session_id
        self.event_repo = EventRepository(db_session, session_id)
    
    def find_common_sequences(
        self,
        node_ids: List[str],
        min_length: int = 3,
        min_frequency: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find common event sequences across multiple nodes.
        
        Args:
            node_ids: List of node IDs to analyze
            min_length: Minimum sequence length
            min_frequency: Minimum times sequence must occur
            
        Returns:
            List of common sequences with metadata
        """
        # Get events for all nodes
        all_sequences = []
        
        for node_id in node_ids:
            events = self.event_repo.list_events_for_node(node_id)
            sequence = self._events_to_sequence(events)
            all_sequences.append(sequence)
        
        # Find common subsequences
        common = self._find_common_subsequences(
            all_sequences,
            min_length=min_length,
            min_frequency=min_frequency
        )
        
        return common
    
    def extract_agent_pattern(self, node_ids: List[str]) -> Dict[str, Any]:
        """
        Extract agent call pattern from nodes.
        
        Args:
            node_ids: List of node IDs
            
        Returns:
            Pattern dictionary with agent sequence
        """
        agent_sequences = []
        
        for node_id in node_ids:
            events = self.event_repo.list_events_for_node(
                node_id,
                event_type="agent_call"
            )
            agents = [e.agent_name for e in events if e.agent_name]
            agent_sequences.append(agents)
        
        # Find most common sequence
        if not agent_sequences:
            return {}
        
        # Count frequency
        sequence_counts = Counter(tuple(seq) for seq in agent_sequences)
        most_common = sequence_counts.most_common(1)[0]
        
        return {
            "agent_sequence": list(most_common[0]),
            "frequency": most_common[1],
            "total_samples": len(agent_sequences)
        }
    
    def calculate_similarity(
        self,
        node_id1: str,
        node_id2: str
    ) -> float:
        """
        Calculate similarity between two node executions.
        
        Args:
            node_id1: First node ID
            node_id2: Second node ID
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        events1 = self.event_repo.list_events_for_node(node_id1)
        events2 = self.event_repo.list_events_for_node(node_id2)
        
        seq1 = self._events_to_sequence(events1)
        seq2 = self._events_to_sequence(events2)
        
        # Use Levenshtein distance
        similarity = self._sequence_similarity(seq1, seq2)
        
        return similarity
    
    def _events_to_sequence(self, events: List[ExecutionEvent]) -> List[str]:
        """Convert events to sequence of type-agent pairs."""
        return [
            f"{e.event_type}:{e.agent_name or 'system'}"
            for e in events
        ]
    
    def _find_common_subsequences(
        self,
        sequences: List[List[str]],
        min_length: int,
        min_frequency: int
    ) -> List[Dict[str, Any]]:
        """Find common subsequences using suffix tree approach."""
        # Simplified implementation - use proper suffix tree for production
        subsequence_counts = Counter()
        
        for sequence in sequences:
            # Extract all subsequences of min_length or more
            for i in range(len(sequence)):
                for j in range(i + min_length, len(sequence) + 1):
                    subseq = tuple(sequence[i:j])
                    subsequence_counts[subseq] += 1
        
        # Filter by frequency
        common = [
            {
                "sequence": list(subseq),
                "length": len(subseq),
                "frequency": count
            }
            for subseq, count in subsequence_counts.items()
            if count >= min_frequency
        ]
        
        # Sort by frequency and length
        common.sort(key=lambda x: (x["frequency"], x["length"]), reverse=True)
        
        return common
    
    def _sequence_similarity(self, seq1: List[str], seq2: List[str]) -> float:
        """Calculate similarity between sequences (Levenshtein distance)."""
        m, n = len(seq1), len(seq2)
        
        if m == 0 or n == 0:
            return 0.0
        
        # Create distance matrix
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        # Initialize
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        # Fill matrix
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i-1][j],    # deletion
                        dp[i][j-1],    # insertion
                        dp[i-1][j-1]   # substitution
                    )
        
        # Convert distance to similarity
        max_len = max(m, n)
        distance = dp[m][n]
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
```

**Files to Create:**
- `cmbagent/skills/pattern_matcher.py`

**Verification:**
- Pattern matcher finds sequences
- Similarity calculation works
- Agent patterns extracted

### Task 3: Implement Skill Extractor

**Objective:** Extract skills from patterns

**Implementation:**

Create `cmbagent/skills/skill_extractor.py`:

```python
"""
Skill Extractor

Extracts reusable skills from execution patterns.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from cmbagent.database import EventRepository
from cmbagent.database.models import Skill, DAGNode
from cmbagent.skills.pattern_matcher import PatternMatcher


class SkillExtractor:
    """Extracts skills from workflow patterns."""
    
    def __init__(self, db_session: Session, session_id: str):
        self.db = db_session
        self.session_id = session_id
        self.event_repo = EventRepository(db_session, session_id)
        self.pattern_matcher = PatternMatcher(db_session, session_id)
    
    def extract_from_nodes(
        self,
        node_ids: List[str],
        skill_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Skill:
        """
        Extract skill from successful node executions.
        
        Args:
            node_ids: List of node IDs to extract from
            skill_name: Optional custom name
            category: Optional category
            
        Returns:
            Extracted Skill instance
        """
        # Extract pattern
        agent_pattern = self.pattern_matcher.extract_agent_pattern(node_ids)
        
        # Get events from first node as template
        template_events = self.event_repo.list_events_for_node(node_ids[0])
        
        # Build pattern structure
        pattern = self._build_pattern(template_events, agent_pattern)
        
        # Extract parameters
        parameters = self._extract_parameters(template_events)
        
        # Calculate metrics
        metrics = self._calculate_metrics(node_ids)
        
        # Generate name if not provided
        if not skill_name:
            skill_name = self._generate_name(agent_pattern)
        
        # Create skill
        skill = Skill(
            session_id=self.session_id,
            name=skill_name,
            description=f"Extracted from {len(node_ids)} successful executions",
            pattern=pattern,
            parameters=parameters,
            extracted_from={
                "node_ids": node_ids,
                "extraction_date": datetime.now(timezone.utc).isoformat()
            },
            extraction_method="automatic",
            success_rate=metrics["success_rate"],
            avg_duration_seconds=metrics["avg_duration"],
            avg_cost_usd=metrics["avg_cost"],
            category=category
        )
        
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        
        return skill
    
    def auto_discover_skills(
        self,
        min_similarity: float = 0.8,
        min_nodes: int = 3
    ) -> List[Skill]:
        """
        Automatically discover skills from all completed nodes.
        
        Args:
            min_similarity: Minimum similarity threshold
            min_nodes: Minimum nodes required for skill
            
        Returns:
            List of discovered skills
        """
        # Get all completed nodes
        nodes = self.db.query(DAGNode).filter(
            DAGNode.session_id == self.session_id,
            DAGNode.status == "completed"
        ).all()
        
        if len(nodes) < min_nodes:
            return []
        
        # Group similar nodes
        groups = self._group_similar_nodes(nodes, min_similarity)
        
        # Extract skills from groups
        skills = []
        for group in groups:
            if len(group) >= min_nodes:
                skill = self.extract_from_nodes(
                    [n.id for n in group],
                    category="auto_discovered"
                )
                skills.append(skill)
        
        return skills
    
    def _build_pattern(
        self,
        events: List,
        agent_pattern: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build pattern structure from events."""
        steps = []
        
        for event in events:
            if event.event_type == "agent_call":
                steps.append({
                    "type": "agent_call",
                    "agent": event.agent_name,
                    "action": self._infer_action(event),
                    "params": list((event.inputs or {}).keys())
                })
            elif event.event_type == "tool_call":
                steps.append({
                    "type": "tool_call",
                    "tool": event.inputs.get("tool_name") if event.inputs else None,
                    "params": list((event.inputs or {}).get("arguments", {}).keys())
                })
        
        return {
            "steps": steps,
            "agent_sequence": agent_pattern.get("agent_sequence", [])
        }
    
    def _extract_parameters(self, events: List) -> Dict[str, Any]:
        """Extract required parameters from events."""
        params = {}
        
        for event in events:
            if event.inputs:
                for key, value in event.inputs.items():
                    if key not in params:
                        params[key] = {
                            "type": self._infer_type(value),
                            "required": True,
                            "description": f"Parameter {key}"
                        }
        
        return params
    
    def _calculate_metrics(self, node_ids: List[str]) -> Dict[str, Any]:
        """Calculate skill metrics from nodes."""
        total_duration = 0
        total_cost = 0.0
        count = 0
        
        for node_id in node_ids:
            events = self.event_repo.list_events_for_node(node_id)
            
            for event in events:
                if event.duration_ms:
                    total_duration += event.duration_ms / 1000
                
                if event.meta and "cost_usd" in event.meta:
                    total_cost += event.meta["cost_usd"]
            
            count += 1
        
        return {
            "success_rate": 1.0,  # Only successful nodes included
            "avg_duration": int(total_duration / count) if count > 0 else 0,
            "avg_cost": float(total_cost / count) if count > 0 else 0.0
        }
    
    def _generate_name(self, agent_pattern: Dict[str, Any]) -> str:
        """Generate skill name from pattern."""
        agents = agent_pattern.get("agent_sequence", [])
        if not agents:
            return f"skill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return f"{'_'.join(agents)}_workflow"
    
    def _infer_action(self, event) -> str:
        """Infer action from event inputs."""
        if not event.inputs:
            return "process"
        
        message = event.inputs.get("message", "")
        
        # Simple keyword matching
        if "plot" in message.lower():
            return "plot"
        elif "analyze" in message.lower():
            return "analyze"
        elif "code" in message.lower() or "implement" in message.lower():
            return "code"
        else:
            return "process"
    
    def _infer_type(self, value: Any) -> str:
        """Infer parameter type from value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "any"
    
    def _group_similar_nodes(
        self,
        nodes: List[DAGNode],
        min_similarity: float
    ) -> List[List[DAGNode]]:
        """Group similar nodes together."""
        groups = []
        used = set()
        
        for i, node1 in enumerate(nodes):
            if node1.id in used:
                continue
            
            group = [node1]
            used.add(node1.id)
            
            for node2 in nodes[i+1:]:
                if node2.id in used:
                    continue
                
                similarity = self.pattern_matcher.calculate_similarity(
                    node1.id,
                    node2.id
                )
                
                if similarity >= min_similarity:
                    group.append(node2)
                    used.add(node2.id)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups
```

**Files to Create:**
- `cmbagent/skills/skill_extractor.py`

**Verification:**
- Skills extracted from nodes
- Parameters identified
- Metrics calculated
- Auto-discovery works

### Task 4: Create Skill Repository

**Objective:** Storage and retrieval for skills

**Implementation:**

Create `cmbagent/skills/skill_repository.py`:

```python
"""
Skill Repository

Storage and retrieval of extracted skills.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from cmbagent.database.models import Skill


class SkillRepository:
    """Repository for skill operations."""
    
    def __init__(self, db_session: Session, session_id: str):
        self.db = db_session
        self.session_id = session_id
    
    def create_skill(self, **kwargs) -> Skill:
        """Create a new skill."""
        skill = Skill(
            session_id=self.session_id,
            **kwargs
        )
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        return skill
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get skill by ID."""
        return self.db.query(Skill).filter(
            Skill.id == skill_id,
            Skill.session_id == self.session_id
        ).first()
    
    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """Get skill by name."""
        return self.db.query(Skill).filter(
            Skill.name == name,
            Skill.session_id == self.session_id,
            Skill.status == "active"
        ).first()
    
    def list_skills(
        self,
        category: Optional[str] = None,
        status: str = "active",
        limit: int = 100
    ) -> List[Skill]:
        """List skills with filters."""
        query = self.db.query(Skill).filter(
            Skill.session_id == self.session_id,
            Skill.status == status
        )
        
        if category:
            query = query.filter(Skill.category == category)
        
        query = query.order_by(desc(Skill.times_used), desc(Skill.created_at))
        query = query.limit(limit)
        
        return query.all()
    
    def search_skills(
        self,
        query_text: str,
        limit: int = 10
    ) -> List[Skill]:
        """Search skills by name or description."""
        pattern = f"%{query_text}%"
        
        skills = self.db.query(Skill).filter(
            Skill.session_id == self.session_id,
            Skill.status == "active",
            (Skill.name.ilike(pattern) | Skill.description.ilike(pattern))
        ).limit(limit).all()
        
        return skills
    
    def update_skill(self, skill_id: str, **kwargs):
        """Update skill."""
        skill = self.get_skill(skill_id)
        if skill:
            for key, value in kwargs.items():
                if hasattr(skill, key):
                    setattr(skill, key, value)
            self.db.commit()
            self.db.refresh(skill)
            return skill
        return None
    
    def increment_usage(self, skill_id: str):
        """Increment skill usage count."""
        skill = self.get_skill(skill_id)
        if skill:
            skill.times_used += 1
            skill.last_used_at = datetime.now(timezone.utc)
            self.db.commit()
    
    def delete_skill(self, skill_id: str):
        """Delete skill."""
        skill = self.get_skill(skill_id)
        if skill:
            self.db.delete(skill)
            self.db.commit()
            return True
        return False
    
    def export_skill(self, skill_id: str) -> Dict[str, Any]:
        """Export skill as JSON."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {}
        
        return {
            "name": skill.name,
            "description": skill.description,
            "version": skill.version,
            "pattern": skill.pattern,
            "parameters": skill.parameters,
            "category": skill.category,
            "tags": skill.tags,
            "success_rate": float(skill.success_rate) if skill.success_rate else None,
            "avg_duration_seconds": skill.avg_duration_seconds,
            "avg_cost_usd": float(skill.avg_cost_usd) if skill.avg_cost_usd else None
        }
    
    def import_skill(self, skill_data: Dict[str, Any]) -> Skill:
        """Import skill from JSON."""
        skill = self.create_skill(**skill_data)
        return skill
```

**Files to Create:**
- `cmbagent/skills/skill_repository.py`

**Verification:**
- Skills stored and retrieved
- Search works
- Export/import functional

### Task 5: Create Skill Module __init__.py

**Objective:** Export skill components

**Implementation:**

Create `cmbagent/skills/__init__.py`:

```python
"""
Skills module for CMBAgent.

Provides pattern recognition and skill extraction from workflows.
"""

from cmbagent.skills.pattern_matcher import PatternMatcher
from cmbagent.skills.skill_extractor import SkillExtractor
from cmbagent.skills.skill_repository import SkillRepository

__all__ = [
    "PatternMatcher",
    "SkillExtractor",
    "SkillRepository",
]
```

**Files to Create:**
- `cmbagent/skills/__init__.py`

**Verification:**
- All components importable
- No circular imports

## Verification Criteria

### Must Pass
- [ ] Skill model created and migrated
- [ ] PatternMatcher finds sequences
- [ ] SkillExtractor extracts skills
- [ ] SkillRepository stores/retrieves skills
- [ ] Auto-discovery finds similar patterns
- [ ] Skill export/import works
- [ ] Can search skills by name
- [ ] Usage tracking functional

## Files Summary

### New Files
```
cmbagent/skills/__init__.py
cmbagent/skills/pattern_matcher.py
cmbagent/skills/skill_extractor.py
cmbagent/skills/skill_repository.py
```

### Modified Files
```
cmbagent/database/models.py (add Skill model)
```

## Testing

Create `tests/test_stage_04_skill_extraction.py`:

```python
"""Tests for Stage 4: Skill Extraction"""

import pytest
from cmbagent.database import init_database, get_db_session, WorkflowRepository
from cmbagent.skills import PatternMatcher, SkillExtractor, SkillRepository


@pytest.fixture
def db_session():
    init_database()
    session = get_db_session()
    yield session
    session.close()


def test_skill_extraction(db_session):
    """Test skill extraction from nodes."""
    # Create test data
    # ... implementation ...
    print("✓ Skill extraction works")


def test_pattern_matching(db_session):
    """Test pattern matching."""
    # ... implementation ...
    print("✓ Pattern matching works")


def test_skill_repository(db_session):
    """Test skill storage."""
    # ... implementation ...
    print("✓ Skill repository works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

## Post-Stage Actions

1. Update PROGRESS.md
2. Test skill extraction on real workflows
3. Document discovered skills
4. Plan skill application/replay (future work)

## Next Steps

After completing all 4 stages:
1. Review overall implementation
2. Performance optimization
3. Documentation updates
4. Production deployment planning
