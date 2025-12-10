from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Enum, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base, DATABASE_SCHEMA
import enum

class PolicySetStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class RuleType(str, enum.Enum):
    do = "do"
    dont = "dont"


class Severity(str, enum.Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


STATUS_ENUM = Enum(
    PolicySetStatus,
    name="policy_set_status",
    schema=DATABASE_SCHEMA
)

RULE_TYPE_ENUM = Enum(
    RuleType,
    name="rule_type_enum",
    schema=DATABASE_SCHEMA
)

SEVERITY_ENUM = Enum(
    Severity,
    name="severity_enum",
    schema=DATABASE_SCHEMA
)

class CompliancePolicySet(Base):
    __tablename__ = "compliance_policy_sets"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False)
    status = Column(STATUS_ENUM, default=PolicySetStatus.draft, index=True)  # Add index
    name = Column(String(255), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), index=True)  # Add index
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    documents = relationship("CompliancePolicyDocument", cascade="all, delete-orphan")
    rules = relationship("ComplianceRule", cascade="all, delete-orphan")

class CompliancePolicyDocument(Base):
    __tablename__ = "compliance_policy_documents"
 

    id = Column(Integer, primary_key=True)
    policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id"))
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)

    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ComplianceRule(Base):
    __tablename__ = "compliance_rules"


    id = Column(Integer, primary_key=True)
    policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id", ondelete="CASCADE"))

    category = Column(String)
    rule_type = Column(RULE_TYPE_ENUM)
    title = Column(String, nullable=False)
    description = Column(Text)
    severity = Column(SEVERITY_ENUM, default=Severity.info)
    enabled = Column(Boolean, default=True)

    ai_generated = Column(Boolean, default=True)
    example_snippets = Column(JSON, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ConversationComplianceEvaluation(Base):
    __tablename__ = "conversation_compliance_evaluations"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String, nullable=False, index=True)
    policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id"), nullable=False)
    overall_score = Column(Integer)  
    compliance_status = Column(String)  
    summary = Column(Text)  
    compliance_findings = Column(JSON)  
    violations_summary = Column(JSON)  
    applicable_rules_summary = Column(JSON)  
    llm_metadata = Column(JSON) 
    evaluated_by_user_id = Column(Integer, ForeignKey("users.id"))
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())
    policy_set = relationship("CompliancePolicySet", foreign_keys=[policy_set_id])
    evaluated_by = relationship("User", foreign_keys=[evaluated_by_user_id])
