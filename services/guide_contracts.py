"""Pydantic contracts and validation models for guides, rules, and authoring pipelines."""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GuideKind(str, enum.Enum):
    CORE = "core"
    STAGE = "stage"
    STYLE = "style"
    PATTERN = "pattern"
    RULE = "rule"


class RuleSeverity(str, enum.Enum):
    BLOCKING = "blocking"
    REVIEW = "review"
    WARNING = "warning"


class RuleStatus(str, enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class MatchCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(..., description="Target field in context entities (e.g. claim_kinds, product_ids)")
    op: str = Field(..., description="Matching operator (currently 'intersects' supported)")
    values: List[str] = Field(default_factory=list, description="Values to match against")

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        if v not in ("intersects", "equals", "contains"):
            raise ValueError(f"Unsupported matching operator: {v}")
        return v


class RuleMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all: List[MatchCondition] = Field(default_factory=list)
    any: List[MatchCondition] = Field(default_factory=list)


class RuleContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Unique rule ID, e.g. RULE-NUMERIC-SCOPE")
    version: str = Field(default="1.0.0")
    status: RuleStatus = Field(default=RuleStatus.ACTIVE)
    path: str = Field(..., description="Relative markdown file path")
    required: bool = Field(default=True)
    severity: RuleSeverity = Field(default=RuleSeverity.BLOCKING)
    priority: int = Field(default=100)
    match: RuleMatch = Field(default_factory=RuleMatch)
    stages: List[str] = Field(default_factory=lambda: ["strategy", "write", "feedback", "official"])
    description: Optional[str] = None
    owner: Optional[str] = "content-team"
    change_note: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    references_rule_ids: List[str] = Field(default_factory=list)
    supersedes: Optional[List[str]] = None
    body: Optional[str] = None
    sha256: Optional[str] = None


class GuideContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(..., description="Unique guide ID, e.g. GUIDE-STAGE-WRITE")
    version: str = Field(default="1.0.0")
    status: RuleStatus = Field(default=RuleStatus.ACTIVE)
    path: str = Field(..., description="Relative markdown path or module path")
    kind: GuideKind = Field(default=GuideKind.STAGE)
    description: str = Field(..., description="Summary of this guide")
    owner: Optional[str] = "content-team"
    change_note: Optional[str] = None
    stages: List[str] = Field(default_factory=list)
    intents: List[str] = Field(default_factory=list)
    applies_to_elements: List[str] = Field(default_factory=list)
    required: bool = Field(default=False)
    severity: RuleSeverity = Field(default=RuleSeverity.REVIEW)
    priority: int = Field(default=100)
    match: Optional[RuleMatch] = None
    depends_on: List[str] = Field(default_factory=list)
    references_rule_ids: List[str] = Field(default_factory=list)
    supersedes: Optional[List[str]] = None
    body: Optional[str] = None
    sha256: Optional[str] = None


class RuleRegistryContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "1.0.0"
    guide_version: str = "3.0.0"
    implementation_status: Optional[str] = None
    rules: List[RuleContract] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duplicate_ids(self) -> RuleRegistryContract:
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            duplicates = [x for x in ids if ids.count(x) > 1]
            raise ValueError(f"Duplicate rule IDs found in registry: {set(duplicates)}")
        return self


class GuideRegistryContract(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "1.0.0"
    guide_version: str = "3.0.0"
    guides: List[GuideContract] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_duplicate_ids(self) -> GuideRegistryContract:
        ids = [g.id for g in self.guides]
        if len(ids) != len(set(ids)):
            duplicates = [x for x in ids if ids.count(x) > 1]
            raise ValueError(f"Duplicate guide IDs found in registry: {set(duplicates)}")
        return self


class GuideReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    release_id: str
    created_at: str
    schema_version: str = "1.0.0"
    bundle_sha256: str
    code_revision: str
    guides: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    rules: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    prompts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    eval_report_ref: Optional[str] = None


class SectionPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    section_id: str
    title: str
    stage: str = "write"
    purpose: Optional[str] = None
    questions: List[str] = Field(default_factory=list)
    required_facts: List[str] = Field(default_factory=list)
    assigned_rules: List[str] = Field(default_factory=list)
    elements: List[str] = Field(default_factory=list)
    asset_ids: List[str] = Field(default_factory=list)
    link_anchors: List[Dict[str, Any]] = Field(default_factory=list)
    connection_memo: Optional[str] = None


class SelectionReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    stage: str
    section_id: Optional[str] = None
    call_id: Optional[str] = None
    selected_rules: List[Dict[str, Any]] = Field(default_factory=list)
    omitted_rules: List[Dict[str, Any]] = Field(default_factory=list)
    selected_guides: List[Dict[str, Any]] = Field(default_factory=list)
    server_guides: List[Dict[str, Any]] = Field(default_factory=list)
    optimization: Dict[str, Any] = Field(default_factory=dict)
    fact_policy: Dict[str, Any] = Field(default_factory=dict)
    selected_facts: List[Dict[str, Any]] = Field(default_factory=list)
    omitted_facts: List[Dict[str, Any]] = Field(default_factory=list)
    missing_required: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    budget_status: Dict[str, Any] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    char_count: int = 0
    estimated_tokens: int = 0


class ReviewCheckCategory(str, enum.Enum):
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    HUMAN = "human"


class ReviewStatus(str, enum.Enum):
    SATISFIED = "satisfied"
    UNRESOLVED = "unresolved"
    NOT_APPLICABLE = "not_applicable"
    VIOLATION = "violation"


class ReviewItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    rule_id: Optional[str] = None
    fact_id: Optional[str] = None
    category: ReviewCheckCategory = ReviewCheckCategory.STRUCTURAL
    status: ReviewStatus = ReviewStatus.UNRESOLVED
    evidence: Optional[str] = None
    detail: Optional[str] = None


class CoverageReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    requirements: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    satisfied: List[str] = Field(default_factory=list)
    unresolved: List[str] = Field(default_factory=list)
    not_applicable: List[str] = Field(default_factory=list)
    passed: bool = False


class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    content_id: str
    passed: bool = False
    structural_checks: List[ReviewItem] = Field(default_factory=list)
    semantic_checks: List[ReviewItem] = Field(default_factory=list)
    human_checks: List[ReviewItem] = Field(default_factory=list)
    unresolved_items: List[ReviewItem] = Field(default_factory=list)
    satisfied_requirements: List[str] = Field(default_factory=list)
    summary: str = ""
