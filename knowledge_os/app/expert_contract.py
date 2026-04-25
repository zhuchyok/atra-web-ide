from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime

class ExpertResponse(BaseModel):
    """
    [SINGULARITY 28.2] Standard Expert Response Contract.
    Enforces a strict protocol for all 86 experts.
    """
    expert_name: str = Field(..., description="Name of the expert providing the response")
    task_id: str = Field(..., description="Unique ID of the task")
    status: str = Field("success", pattern="^(success|failed|pending)$")
    content: str = Field(..., description="The main response content")
    reasoning_trace: Optional[str] = Field(None, description="Step-by-step reasoning")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ExpertContract:
    """
    Utility to validate and enforce expert communication.
    """
    @staticmethod
    def validate_response(data: Dict[str, Any]) -> ExpertResponse:
        return ExpertResponse(**data)

    @staticmethod
    def format_prompt_instruction() -> str:
        return """
### OUTPUT CONTRACT:
You MUST provide your response in a structured format. 
If you are returning a final answer, use the following JSON structure:
{
  "expert_name": "Your Name",
  "task_id": "Task ID",
  "status": "success",
  "content": "Your detailed answer",
  "reasoning_trace": "Step 1: ..., Step 2: ...",
  "confidence_score": 0.95
}
"""
