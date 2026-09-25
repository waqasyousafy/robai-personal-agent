import uuid
from enum import Enum
from typing import Optional, Dict
from models import PlanStep, ActionType, EvidenceReceipt
from governor import Governor
from mcp_gateway import MCPGateway, EvidenceCollector

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class ProposalState:
    def __init__(self, proposal_id: str, step: PlanStep, exact_description: str):
        self.proposal_id = proposal_id
        self.step = step
        self.exact_description = exact_description
        self.status = ApprovalStatus.PENDING
        self.single_use_token: Optional[str] = None

class ApprovalEngine:
    def __init__(self):
        self.proposals: Dict[str, ProposalState] = {}

    def create_proposal(self, step: PlanStep, exact_description: str) -> ProposalState:
        proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
        proposal = ProposalState(proposal_id, step, exact_description)
        self.proposals[proposal_id] = proposal
        return proposal

    def approve_proposal(self, proposal_id: str) -> str:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Invalid proposal ID")

        proposal.status = ApprovalStatus.APPROVED
        proposal.single_use_token = f"tok_{uuid.uuid4().hex}"
        return proposal.single_use_token

    def execute_write_with_readback(self, step: PlanStep, token: str, governor: Governor, collector: EvidenceCollector) -> EvidenceReceipt:
        governor.authorize_step(step, single_use_approval_token=token)
        write_result = MCPGateway.dispatch(step)

        readback_step = PlanStep(
            id=f"{step.id}_readback",
            action="verify_event_created",
            connector_id=step.connector_id,
            action_type=ActionType.READ,
            depends_on=[step.id],
            expected_evidence=["event_details"],
            success_criteria=["event exists on provider"]
        )
        readback_result = MCPGateway.dispatch(readback_step)

        combined_payload = {
            "write_result": write_result,
            "readback_verification": readback_result
        }
        return collector.record_receipt(step.id, step.connector_id, combined_payload)
