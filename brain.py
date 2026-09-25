import os
import json
from typing import Dict, Any
from groq import Groq

SYSTEM_PROMPT = """
You are the LLM Brain of a personal AI agent system governed by a runtime safety governor.
Your output MUST strictly be a single valid JSON object representing a structured plan.

JSON Schema format:
{
  "goal": "<user_goal>",
  "steps": [
    {
      "id": "step_1",
      "action": "<action_name>",
      "connector_id": "calendar.personal",
      "action_type": "read" | "proposal" | "write",
      "depends_on": [],
      "expected_evidence": ["<expected_output>"],
      "success_criteria": ["<criteria>"],
      "args": {}
    }
  ]
}

Rules:
1. Steps must be sequential and contain 1 to 12 steps maximum.
2. 'depends_on' can only reference step IDs that come BEFORE the current step.
3. Use action_type='write' for any mutation or external action.
4. Use connector_id='calendar.personal' for calendar operations.
5. Do NOT output markdown code blocks, prose, or extra text. Output ONLY raw JSON.
"""

class GroqBrain:
    def __init__(self, model_name: str = "qwen/qwen3.8-27b"):
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY environment variable is missing. Set it using: export GROQ_API_KEY='gsk_...'")
        self.client = Groq(api_key=self.api_key)
        self.model_name = model_name

    def generate_plan(self, user_goal: str) -> Dict[str, Any]:
        response = self.client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Create an execution plan for: '{user_goal}'"}
            ],
            model=self.model_name,
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return json.loads(content)
