from pydantic import BaseModel
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
    pass


class PolicySetOut(BaseModel):
    id: int
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