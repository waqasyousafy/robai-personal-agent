import uuid
from typing import Dict, Any
from models import PlanStep, EvidenceReceipt

class MCPGateway:
    @staticmethod
    def dispatch(step: PlanStep) -> Dict[str, Any]:
        if "calendar" in step.connector_id or "availability" in step.action:
            return {
                "status": "success",
                "available_slots": ["2026-09-21T12:00:00Z", "2026-09-21T15:00:00Z"]
            }
        elif "event" in step.action or "create" in step.action:
            return {
                "status": "created",
                "event_id": f"evt_{uuid.uuid4().hex[:6]}",
                "time": step.args.get("time", "12:00"),
                "details": step.args
            }
        else:
            return {"status": "success", "data": "Executed default MCP action", "args": step.args}

class EvidenceCollector:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.receipts: Dict[str, EvidenceReceipt] = {}

    def record_receipt(self, step_id: str, connector_id: str, raw_payload: Dict[str, Any]) -> EvidenceReceipt:
        receipt = EvidenceReceipt(
            run_id=self.run_id,
            step_id=step_id,
            connector_id=connector_id,
            raw_payload=raw_payload
        )
        self.receipts[receipt.receipt_id] = receipt
        return receipt

    def verify_claim(self, claim_text: str, receipt_id: str) -> bool:
        receipt = self.receipts.get(receipt_id)
        if not receipt:
            return False
        return True
