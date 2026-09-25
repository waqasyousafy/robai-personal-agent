from typing import Dict, Any, Optional
from models import ActionType, BudgetTracker, PlanStep

class PolicyViolationError(Exception):
    pass

class OPAPolicyEngine:
    @staticmethod
    def evaluate(user_id: str, connector_id: str, action_type: ActionType, args: Dict[str, Any]) -> bool:
        if action_type == ActionType.WRITE:
            return False
            
        approved_connectors = ["calendar.personal", "calendar.work", "email.read_only", "system.default"]
        if connector_id not in approved_connectors:
            return False

        return True

class Governor:
    def __init__(self, user_id: str, budget_tracker: BudgetTracker):
        self.user_id = user_id
        self.budget_tracker = budget_tracker

    def authorize_step(self, step: PlanStep, single_use_approval_token: Optional[str] = None) -> bool:
        self.budget_tracker.check_budget(step.action_type)

        if step.action_type == ActionType.WRITE:
            if not single_use_approval_token:
                raise PolicyViolationError(
                    f"Action '{step.action}' is a WRITE operation and requires explicit user approval."
                )
            return True

        allowed = OPAPolicyEngine.evaluate(
            user_id=self.user_id,
            connector_id=step.connector_id,
            action_type=step.action_type,
            args=step.args
        )

        if not allowed:
            raise PolicyViolationError(f"OPA policy denied execution of action '{step.action}' on connector '{step.connector_id}'.")

        return True
