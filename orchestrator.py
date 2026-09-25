import uuid
from typing import Dict, Any, Optional
from models import (
    ExecutionProfile,
    BudgetLimits,
    BudgetTracker,
    StructuredPlan,
    ActionType,
)
from validator import validate_llm_plan
from governor import Governor, PolicyViolationError
from mcp_gateway import MCPGateway, EvidenceCollector
from approval import ApprovalEngine

class RobAIAgentRuntime:
    def __init__(self, user_id: str, profile: ExecutionProfile = ExecutionProfile.STANDARD):
        self.run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.user_id = user_id
        
        limits = BudgetLimits.get_profile(profile)
        self.budget_tracker = BudgetTracker(profile=profile, limits=limits)
        self.governor = Governor(user_id=self.user_id, budget_tracker=self.budget_tracker)
        
        self.collector = EvidenceCollector(run_id=self.run_id)
        self.approval_engine = ApprovalEngine()

    def run_pipeline(self, raw_plan_payload: Dict[str, Any], user_approved_token: Optional[str] = None):
        print(f"\n================ STARTING AGENT RUN [{self.run_id}] ================")
        
        self.budget_tracker.used_model_decisions += 1
        
        print("\n--- Phase 1: Structural Plan Validation ---")
        try:
            plan: StructuredPlan = validate_llm_plan(raw_plan_payload)
            print(f" Plan Schema & DAG Validated. Goal: '{plan.goal}' ({len(plan.steps)} steps)")
        except Exception as e:
            print(f" Plan Validation Failed: {e}")
            return {"status": "FAILED", "reason": str(e)}

        print("\n--- Phase 2: Governor Authorization & Execution Loop ---")
        for step in plan.steps:
            print(f"\nProcessing Step '{step.id}' -> Action: '{step.action}' [{step.action_type.upper()}]")
            
            if step.action_type == ActionType.WRITE and not user_approved_token:
                proposal = self.approval_engine.create_proposal(
                    step=step,
                    exact_description=f"Create appointment via {step.connector_id} with arguments: {step.args}"
                )
                print(f" PAUSED FOR USER APPROVAL!")
                print(f"   Proposal ID: {proposal.proposal_id}")
                print(f"   Exact Proposal: {proposal.exact_description}")
                return {
                    "status": "PAUSED_AWAITING_APPROVAL",
                    "proposal_id": proposal.proposal_id,
                    "exact_description": proposal.exact_description
                }

            try:
                self.governor.authorize_step(step, single_use_approval_token=user_approved_token)
                print(f"  Governor & OPA Policy Approved step '{step.id}'")
            except PolicyViolationError as pve:
                print(f" Governor Policy Denied Execution: {pve}")
                return {"status": "BLOCKED", "reason": str(pve)}

            if step.action_type == ActionType.READ:
                self.budget_tracker.used_read_calls += 1
            elif step.action_type == ActionType.PROPOSAL:
                self.budget_tracker.used_proposal_calls += 1

            if step.action_type == ActionType.WRITE:
                receipt = self.approval_engine.execute_write_with_readback(
                    step=step,
                    token=user_approved_token,
                    governor=self.governor,
                    collector=self.collector
                )
                print(f"  WRITE Executed & Verified with Provider Readback!")
                print(f"   Evidence Receipt Minted: {receipt.receipt_id}")
            else:
                raw_payload = MCPGateway.dispatch(step)
                receipt = self.collector.record_receipt(
                    step_id=step.id,
                    connector_id=step.connector_id,
                    raw_payload=raw_payload
                )
                print(f"  MCP Tool Dispatched Successfully. Evidence Receipt Minted: {receipt.receipt_id}")

        print(f"\n================ RUN [{self.run_id}] COMPLETED SUCCESSFULLY ================")
        return {
            "status": "COMPLETED",
            "evidence_receipts": list(self.collector.receipts.keys())
        }
