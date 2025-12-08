from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum


class PolicySetStatus(str, Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class RuleType(str, Enum):
    do = "do"
    dont = "dont"


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------- POLICY SET ----------------

class PolicySetCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=255, description="Optional name for the policy set")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Q1 2024 Compliance Policies"
            }
        }


class PolicySetOut(BaseModel):
    id: int
    version: int
    status: PolicySetStatus
    name: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


# Add this new schema for listing
class PolicySetListItem(BaseModel):
    """Simplified policy set info for listing."""
    id: int
    name: Optional[str] = None
    version: int
    status: PolicySetStatus
    created_at: str
    
    class Config:
        from_attributes = True


# ---------------- RULES ----------------

class RuleOut(BaseModel):
    id: int
    category: Optional[str]
    rule_type: RuleType
    title: str
    description: Optional[str]
    severity: Severity
    enabled: bool
    ai_generated: bool

    class Config:
        from_attributes = True


class RuleCreate(BaseModel):
    category: Optional[str] = Field(None, description="Category of the rule (e.g., 'Security', 'Data Privacy')")
    rule_type: RuleType = Field(..., description="Type of rule: 'do' or 'dont'")
    title: str = Field(..., min_length=1, max_length=255, description="Title of the rule")
    description: Optional[str] = Field(None, description="Detailed description of the rule")
    severity: Severity = Field(default=Severity.info, description="Severity level of the rule")
    enabled: bool = Field(default=True, description="Whether the rule is enabled")
    example_snippets: Optional[List[str]] = Field(default=None, description="Example code snippets demonstrating the rule")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "Security",
                "rule_type": "dont",
                "title": "Do not hardcode API keys in source code",
                "description": "API keys, secrets, and credentials should never be hardcoded in the source code. Use environment variables or secure secret management systems.",
                "severity": "critical",
                "enabled": True,
                "example_snippets": ["api_key = 'sk-1234567890abcdef'", "password = 'admin123'"]
            }
        }


class RuleUpdate(BaseModel):
    category: Optional[str]
    rule_type: Optional[RuleType]
    title: Optional[str]
    description: Optional[str]
    severity: Optional[Severity]
    enabled: Optional[bool]


# ---------------- DOCUMENTS ----------------

class DocumentOut(BaseModel):
    id: int
    file_name: str
    file_path: str

    class Config:
        from_attributes = True


# ---------------- EXTRACTION ----------------

class PolicyExtractionRequest(BaseModel):
    """Request schema for policy extraction with optional raw text."""
    raw_text: str | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "raw_text": "Optional raw text to include in extraction along with uploaded documents"
            }
        }


class ExtractionResponse(BaseModel):
    """Response schema for policy extraction results."""
    rules_extracted: int
    rules_saved: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "rules_extracted": 15,
                "rules_saved": 15
            }
        }


# ---------------- EVALUATION ----------------

class ConversationEvaluationRequest(BaseModel):
    """Request schema for conversation compliance evaluation."""
    policy_set_id: Optional[int] = Field(
        None, 
        description="Policy set ID to evaluate against. If not provided, uses active policy set."
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "policy_set_id": 5
            }
        }


class AnnotationContext(BaseModel):
    """Context information for a compliance annotation."""
    related_event_ids: Optional[List[str]] = None
    tool_name: Optional[str] = None
    expected_action: Optional[str] = None


class ComplianceAnnotation(BaseModel):
    """Single compliance annotation for an event."""
    status: str = Field(..., description="compliant | violated | warning")
    severity: str = Field(..., description="critical | high | medium | low")
    rule_id: int
    rule_title: str
    rule_category: str
    message: str = Field(..., description="Concise message for UI display")
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: Optional[str] = None
    recommendation: Optional[str] = None
    context: Optional[AnnotationContext] = None


class ComplianceFinding(BaseModel):
    """Compliance finding for a specific event."""
    event_id: str
    annotations: List[ComplianceAnnotation]


class ViolationsSummary(BaseModel):
    """Summary of violations and warnings."""
    total_violations: int
    total_warnings: int
    total_compliant: int
    by_severity: Dict[str, int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_violations": 1,
                "total_warnings": 2,
                "total_compliant": 5,
                "by_severity": {
                    "critical": 1,
                    "high": 0,
                    "medium": 2,
                    "low": 0
                }
            }
        }


class ApplicableRuleSummary(BaseModel):
    """Summary of how a rule was applied."""
    rule_id: int
    rule_title: str
    category: str
    severity: str
    result: str = Field(..., description="compliant | violated | warning | not_applicable")
    event_count: Optional[int] = None
    reason: Optional[str] = None


class ConversationMetadata(BaseModel):
    """Metadata about the evaluated conversation."""
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    total_events: int
    total_turns: int
    total_tool_calls: int


class LLMMetadata(BaseModel):
    """LLM processing metadata."""
    model_used: str
    processing_time_ms: int
    prompt_length: Optional[int] = None
    response_length: Optional[int] = None


class ConversationEvaluationResponse(BaseModel):
    """Complete conversation evaluation response."""
    conversation_id: str
    policy_set_id: int
    policy_set_name: Optional[str] = None
    
    overall_score: int = Field(..., ge=0, le=100)
    compliance_status: str = Field(..., description="compliant | partially_compliant | non_compliant")
    
    conversation_metadata: ConversationMetadata
    compliance_findings: List[ComplianceFinding]
    violations_summary: ViolationsSummary
    applicable_rules_summary: List[ApplicableRuleSummary]
    
    summary: str
    
    llm_metadata: LLMMetadata
    evaluated_by_user_id: int
    evaluated_at: str
    evaluation_id: Optional[int] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "conv_abc123",
                "policy_set_id": 5,
                "policy_set_name": "Customer Service Standards Q4 2024",
                "overall_score": 75,
                "compliance_status": "partially_compliant",
                "conversation_metadata": {
                    "started_at": "2025-12-04T10:00:00Z",
                    "ended_at": "2025-12-04T10:05:30Z",
                    "duration_seconds": 330,
                    "total_events": 18,
                    "total_turns": 14,
                    "total_tool_calls": 4
                },
                "compliance_findings": [],
                "violations_summary": {
                    "total_violations": 1,
                    "total_warnings": 1,
                    "total_compliant": 3,
                    "by_severity": {
                        "critical": 1,
                        "high": 0,
                        "medium": 1,
                        "low": 0
                    }
                },
                "applicable_rules_summary": [],
                "summary": "Call scored 75/100 with 1 critical violation...",
                "llm_metadata": {
                    "model_used": "gpt-4o",
                    "processing_time_ms": 4532
                },
                "evaluated_by_user_id": 42,
                "evaluated_at": "2025-12-04T10:10:00Z"
            }
        }