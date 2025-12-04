from pydantic import BaseModel, Field
from typing import Optional, List
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