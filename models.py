from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
from datetime import datetime, timezone

class ExecutionProfile(str, Enum):
    STANDARD = "standard"
    DEEP = "deep"

class ActionType(str, Enum):
    READ = "read"
    PROPOSAL = "proposal"
    WRITE = "write"

class BudgetLimits(BaseModel):
    max_model_decisions: int
    max_read_calls: int
    max_proposal_calls: int
    wall_clock_seconds: int

    @classmethod
    def get_profile(cls, profile: ExecutionProfile) -> "BudgetLimits":
        if profile == ExecutionProfile.DEEP:
            return cls(
                max_model_decisions=30,
                max_read_calls=50,
                max_proposal_calls=2,
                wall_clock_seconds=900,
            )
        return cls(
            max_model_decisions=12,
            max_read_calls=20,
            max_proposal_calls=2,
            wall_clock_seconds=300,
        )

class BudgetTracker(BaseModel):
    profile: ExecutionProfile
    limits: BudgetLimits
    used_model_decisions: int = 0
    used_read_calls: int = 0
    used_proposal_calls: int = 0
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def check_budget(self, action_type: Optional[ActionType] = None):
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        if elapsed > self.limits.wall_clock_seconds:
            raise TimeoutError(f"Execution exceeded wall-clock limit of {self.limits.wall_clock_seconds}s")

        if self.used_model_decisions > self.limits.max_model_decisions:
            raise RuntimeError("Exceeded maximum allowed model decisions.")

        if action_type == ActionType.READ and self.used_read_calls >= self.limits.max_read_calls:
            raise RuntimeError("Exceeded maximum allowed read calls.")

        if action_type == ActionType.PROPOSAL and self.used_proposal_calls >= self.limits.max_proposal_calls:
            raise RuntimeError("Exceeded maximum allowed proposal calls.")

class PlanStep(BaseModel):
    id: str
    action: str
    connector_id: str
    action_type: ActionType
    depends_on: List[str] = Field(default_factory=list)
    expected_evidence: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    args: Dict[str, Any] = Field(default_factory=dict)

class StructuredPlan(BaseModel):
    goal: str
    steps: List[PlanStep]

    @model_validator(mode="after")
    def validate_plan_dag(self):
        steps = self.steps
        if not steps or len(steps) > 12:
            raise ValueError("Plan must contain between 1 and 12 steps.")

        seen_ids = set()
        for step in steps:
            if step.id in seen_ids:
                raise ValueError(f"Duplicate step ID detected: {step.id}")
            
            for dep in step.depends_on:
                if dep not in seen_ids:
                    raise ValueError(f"Step '{step.id}' depends on '{dep}', which appears later or does not exist.")
            
            seen_ids.add(step.id)
        
        return self

class EvidenceReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    step_id: str
    connector_id: str
    raw_payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
