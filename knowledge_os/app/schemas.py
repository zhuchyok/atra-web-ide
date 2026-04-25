from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, Union
from datetime import datetime

class AgentResponse(BaseModel):
    """Schema for raw agent response validation."""
    status: str = Field(..., description="Status of the response (success, processing, error)")
    output: Optional[str] = Field(None, description="The actual text output from the agent")
    error: Optional[str] = Field(None, description="Error message if status is error")
    used_model: Optional[str] = Field(None, description="The model that generated this response")
    job_id: Optional[str] = Field(None, description="Job ID for async tasks")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TaskResult(BaseModel):
    """Schema for final task result stored in DB."""
    task_id: str
    status: str
    result: str
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

def parse_agent_response(raw_response: Union[str, Dict, Any]) -> AgentResponse:
    """Robustly parses various response formats into a unified AgentResponse."""
    if isinstance(raw_response, str):
        # Check for error markers in string
        error_indicators = ["⚠️", "❌", "Error", "failed", "недоступен"]
        if any(ind in raw_response for ind in error_indicators):
            return AgentResponse(status="error", error=raw_response)
        return AgentResponse(status="success", output=raw_response)
    
    if isinstance(raw_response, dict):
        # Handle standard status/output format
        status = raw_response.get("status", "success")
        output = raw_response.get("output") or raw_response.get("response") or raw_response.get("text")
        error = raw_response.get("error")
        
        # If it's a processing status, mark it clearly
        if status == "processing":
            return AgentResponse(status="processing", job_id=raw_response.get("job_id"), output=output)
            
        return AgentResponse(
            status=status,
            output=str(output) if output is not None else None,
            error=str(error) if error is not None else None,
            used_model=raw_response.get("used_model"),
            metadata=raw_response.get("metadata", {})
        )
        
    return AgentResponse(status="error", error=f"Unknown response type: {type(raw_response)}")
