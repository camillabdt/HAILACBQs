from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


class JudgeType(str, Enum):
    LLM = "llm"
    HUMAN = "human"


class Severity(str, Enum):
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class FinalAction(str, Enum):
    APROVADA = "APROVADA"
    REGENERAR = "REGENERAR"
    BLOQUEADA = "BLOQUEADA"
    AGUARDANDO_JUIZ_HUMANO = "AGUARDANDO_JUIZ_HUMANO"
    FALHA_DE_PROCESSO = "FALHA_DE_PROCESSO"


class EvaluationStatus(str, Enum):
    COMPLETED = "completed"
    WAITING_HUMAN = "waiting_human"
    PROCESS_ERROR = "process_error"


class RedFlagDefinition(BaseModel):
    id: str
    base_id: str
    version: int = Field(ge=1)
    name: str
    description: str
    category: str
    prompt_instruction: str
    blocking: bool = False
    default_action: Literal["REGENERAR", "BLOQUEADA"] = "REGENERAR"
    source: Literal["builtin", "custom"] = "builtin"
    created_by: str = "system"
    active: bool = True


class CustomRedFlagCreate(BaseModel):
    base_id: str | None = None
    name: str
    description: str
    category: str
    prompt_instruction: str
    blocking: bool = False
    default_action: Literal["REGENERAR", "BLOQUEADA"] = "REGENERAR"
    created_by: str = "professor"


class RedFlagSelection(BaseModel):
    red_flag_id: str
    threshold: float | None = Field(default=None, ge=0, le=1)
    blocking_override: bool | None = None
    action_override: Literal["REGENERAR", "BLOQUEADA"] | None = None


class JudgeConfig(BaseModel):
    id: str
    type: JudgeType
    display_name: str
    specialty_area: str
    model: str | None = None
    enabled: bool = True

    @model_validator(mode="after")
    def validate_model(self) -> "JudgeConfig":
        if self.type == JudgeType.LLM and not self.model:
            raise ValueError("Juiz LLM precisa informar model.")
        if self.type == JudgeType.HUMAN and self.model:
            raise ValueError("Juiz humano não deve informar model.")
        return self


class GroupWeights(BaseModel):
    llm: int = Field(ge=0, le=100)
    human: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_weights(self) -> "GroupWeights":
        allowed = {
            (100, 0),
            (80, 20),
            (50, 50),
            (20, 80),
            (0, 100),
        }
        current = (self.llm, self.human)
        if current not in allowed:
            raise ValueError(
                "Pesos permitidos: 100/0, 80/20, 50/50, 20/80 ou 0/100."
            )
        return self


class JuryProfile(BaseModel):
    id: str
    name: str
    question_area: str
    red_flags: list[RedFlagSelection]
    judges: list[JudgeConfig]
    group_weights: GroupWeights
    default_detection_threshold: float = Field(default=0.5, ge=0, le=1)
    require_complete_jury: bool = True
    created_by: str = "professor"
    active: bool = True

    @model_validator(mode="after")
    def validate_profile(self) -> "JuryProfile":
        active_judges = [judge for judge in self.judges if judge.enabled]
        llm_count = sum(j.type == JudgeType.LLM for j in active_judges)
        human_count = sum(j.type == JudgeType.HUMAN for j in active_judges)

        if llm_count > 3:
            raise ValueError("O perfil aceita no máximo 3 juízes LLM.")
        if human_count > 3:
            raise ValueError("O perfil aceita no máximo 3 juízes humanos.")
        if llm_count == 0 and human_count == 0:
            raise ValueError("O perfil precisa de pelo menos um juiz.")

        if self.group_weights.llm > 0 and llm_count == 0:
            raise ValueError("Peso LLM maior que zero exige juiz LLM.")
        if self.group_weights.human > 0 and human_count == 0:
            raise ValueError("Peso humano maior que zero exige juiz humano.")
        if self.group_weights.llm == 0 and llm_count > 0:
            raise ValueError("Juízes LLM não podem ter peso de grupo zero.")
        if self.group_weights.human == 0 and human_count > 0:
            raise ValueError("Juízes humanos não podem ter peso de grupo zero.")

        ids = [item.red_flag_id for item in self.red_flags]
        if not ids:
            raise ValueError("Selecione pelo menos uma Red Flag.")
        if len(ids) != len(set(ids)):
            raise ValueError("Red Flags duplicadas no perfil.")

        judge_ids = [judge.id for judge in active_judges]
        if len(judge_ids) != len(set(judge_ids)):
            raise ValueError("IDs de juízes duplicados.")

        return self


class QuestionPayload(BaseModel):
    uid: str
    area: str
    year: int | None = None
    context: str = ""
    statement: str
    answer_key: str
    distractors: list[str] = Field(min_length=1)


class JudgeFinding(BaseModel):
    red_flag_id: str
    detected: bool
    severity: Severity = Severity.NONE
    confidence: float = Field(default=1.0, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    recommendation: str = ""

    @model_validator(mode="after")
    def validate_finding(self) -> "JudgeFinding":
        if not self.detected:
            self.severity = Severity.NONE
        return self


class JudgeReport(BaseModel):
    judge_id: str
    judge_type: JudgeType
    specialty_area: str
    model: str | None = None
    status: Literal["completed", "error"] = "completed"
    findings: list[JudgeFinding] = Field(default_factory=list)
    error: str | None = None
    raw_output: str | None = None
    retry_after_seconds: float | None = Field(default=None, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0)
    api_attempts: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_report(self) -> "JudgeReport":
        if self.status == "error" and not self.error:
            raise ValueError("Relatório com erro precisa informar error.")
        return self


class AggregatedRedFlag(BaseModel):
    red_flag_id: str
    detected: bool
    disputed: bool = False
    weighted_score: float = Field(ge=0, le=1)
    threshold: float = Field(ge=0, le=1)
    supporting_judges: list[str] = Field(default_factory=list)
    opposing_judges: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    blocking: bool
    action: Literal["REGENERAR", "BLOQUEADA"]


class EvaluationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    profile_id: str
    profile_snapshot: JuryProfile
    question: QuestionPayload
    reports: list[JudgeReport] = Field(default_factory=list)
    aggregated_flags: list[AggregatedRedFlag] = Field(default_factory=list)
    status: EvaluationStatus = EvaluationStatus.PROCESS_ERROR
    final_action: FinalAction = FinalAction.FALHA_DE_PROCESSO
    process_errors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationRequest(BaseModel):
    profile_id: str
    question: QuestionPayload


class HumanReportRequest(BaseModel):
    report: JudgeReport

    @model_validator(mode="after")
    def validate_human(self) -> "HumanReportRequest":
        if self.report.judge_type != JudgeType.HUMAN:
            raise ValueError("Este endpoint aceita apenas relatório humano.")
        return self
