# from sqlalchemy import (
#     Column, Integer, String, Text, Boolean, ForeignKey, DateTime, Enum, JSON
# )
# from sqlalchemy.sql import func
# from sqlalchemy.orm import relationship
# from database import Base
# import enum


# class PolicySetStatus(str, enum.Enum):
#     draft = "draft"
#     active = "active"
#     archived = "archived"


# class RuleType(str, enum.Enum):
#     do = "do"
#     dont = "dont"


# class Severity(str, enum.Enum):
#     info = "info"
#     low = "low"
#     medium = "medium"
#     high = "high"
#     critical = "critical"


# # ------------------------- POLICY SET -------------------------

# class CompliancePolicySet(Base):
#     __tablename__ = "compliance_policy_sets"

#     id = Column(Integer, primary_key=True)
#     version = Column(Integer, nullable=False)
#     status = Column(Enum(PolicySetStatus), default=PolicySetStatus.draft)
#     name = Column(String(255), nullable=True)

#     created_by = Column(Integer, ForeignKey("users.id"))
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# # ------------------------- DOCUMENTS -------------------------

# class CompliancePolicyDocument(Base):
#     __tablename__ = "compliance_policy_documents"

#     id = Column(Integer, primary_key=True)
#     policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id"))
#     file_name = Column(String, nullable=False)
#     file_path = Column(String, nullable=False)
#     file_type = Column(String, nullable=False)

#     uploaded_by = Column(Integer, ForeignKey("users.id"))
#     created_at = Column(DateTime(timezone=True), server_default=func.now())


# # ------------------------- RULES -------------------------

# class ComplianceRule(Base):
#     __tablename__ = "compliance_rules"

#     id = Column(Integer, primary_key=True)
#     policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id", ondelete="CASCADE"))

#     category = Column(String)
#     rule_type = Column(Enum(RuleType))
#     title = Column(String, nullable=False)
#     description = Column(Text)
#     severity = Column(Enum(Severity), default=Severity.info)
#     enabled = Column(Boolean, default=True)

#     ai_generated = Column(Boolean, default=True)
#     example_snippets = Column(JSON, nullable=True)

#     created_by = Column(Integer, ForeignKey("users.id"))
#     created_at = Column(DateTime(timezone=True), server_default=func.now())


from sqlalchemy import (
    Column, Integer, String, Text, Boolean, ForeignKey,
    DateTime, Enum, JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base
import enum


# ============================================================
# ENUM DEFINITIONS (Now created inside "compliance" schema)
# ============================================================

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
    schema="testdb"
)

RULE_TYPE_ENUM = Enum(
    RuleType,
    name="rule_type_enum",
    schema="testdb"
)

SEVERITY_ENUM = Enum(
    Severity,
    name="severity_enum",
    schema="testdb"
)


# ============================================================
# POLICY SET
# ============================================================

class CompliancePolicySet(Base):
    __tablename__ = "compliance_policy_sets"
   

    id = Column(Integer, primary_key=True)
    version = Column(Integer, nullable=False)
    status = Column(STATUS_ENUM, default=PolicySetStatus.draft)
    name = Column(String(255), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    documents = relationship("CompliancePolicyDocument", cascade="all, delete-orphan")
    rules = relationship("ComplianceRule", cascade="all, delete-orphan")


# ============================================================
# DOCUMENTS
# ============================================================

class CompliancePolicyDocument(Base):
    __tablename__ = "compliance_policy_documents"
 

    id = Column(Integer, primary_key=True)
    policy_set_id = Column(Integer, ForeignKey("compliance_policy_sets.id"))
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)

    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# RULES
# ============================================================

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
