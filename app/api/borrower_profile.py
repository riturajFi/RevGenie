from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.domain.borrower_case import BorrowerCase, CaseStatus, ContactChannel, ResolutionMode, Stage
from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService

router = APIRouter(prefix="/borrower-profiles", tags=["borrower-profiles"])
service = FileBorrowerProfileService()
borrower_case_service = FileBorrowerCaseService()
DEFAULT_CASE_TEMPLATE_ID = "b_001"


class DeleteResponse(BaseModel):
    deleted: bool


class BorrowerCaseOverrides(BaseModel):
    workflow_id: str | None = None
    lender_id: str | None = None
    loan_id_masked: str | None = None
    amount_due: int | None = Field(default=None, ge=0)
    principal_outstanding: int | None = Field(default=None, ge=0)
    dpd: int | None = Field(default=None, ge=0)
    case_type: list[str] | None = None
    stage: Stage | None = None
    case_status: CaseStatus | None = None
    next_allowed_actions: list[str] | None = None
    identity_verified: bool | None = None
    resolution_mode: ResolutionMode | None = None


class CreateBorrowerProfileRequest(BaseModel):
    full_name: str
    phone_number: str
    create_case: bool = True
    case_overrides: BorrowerCaseOverrides | None = None


def _generate_borrower_id() -> str:
    while True:
        candidate = f"b_{uuid4().hex[:8]}"
        if service.get_borrower_profile(candidate) is None:
            return candidate


def _generate_workflow_id() -> str:
    return f"wf_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"


def _build_case_from_defaults(
    borrower_id: str,
    overrides: BorrowerCaseOverrides | None = None,
) -> BorrowerCase:
    template = borrower_case_service.get_borrower_case(DEFAULT_CASE_TEMPLATE_ID)
    if template is None:
        raise KeyError(f"Default borrower case template not found: {DEFAULT_CASE_TEMPLATE_ID}")

    case = BorrowerCase.model_validate(template.model_dump(mode="python"))
    case.borrower_id = borrower_id
    case.workflow_id = _generate_workflow_id()
    case.stage = Stage.ASSESSMENT
    case.case_status = CaseStatus.OPEN
    case.final_disposition = None
    case.latest_handoff_summary = None
    case.latest_handoff_stage = None
    case.offers_made = []
    case.borrower_objections = []
    case.borrower_stated_position = None
    case.last_deadline_offered = None
    case.assessment_notes = None
    case.resolution_notes = None
    case.final_notice_notes = None
    case.last_contact_channel = ContactChannel.CHAT
    case.resolution_mode = ResolutionMode.VOICE
    case.resolution_call_id = None
    case.resolution_call_status = None
    case.stop_contact_flag = False
    if "stop_contact_requested" in case.attributes:
        case.attributes["stop_contact_requested"] = False

    if overrides is not None:
        if overrides.workflow_id:
            case.workflow_id = overrides.workflow_id
        if overrides.lender_id:
            case.lender_id = overrides.lender_id
        if overrides.loan_id_masked:
            case.loan_id_masked = overrides.loan_id_masked
        if overrides.amount_due is not None:
            case.amount_due = overrides.amount_due
        if overrides.principal_outstanding is not None:
            case.principal_outstanding = overrides.principal_outstanding
        if overrides.dpd is not None:
            case.dpd = overrides.dpd
        if overrides.case_type is not None:
            case.case_type = overrides.case_type
        if overrides.stage is not None:
            case.stage = overrides.stage
        if overrides.case_status is not None:
            case.case_status = overrides.case_status
        if overrides.next_allowed_actions is not None:
            case.next_allowed_actions = overrides.next_allowed_actions
        if overrides.identity_verified is not None:
            case.identity_verified = overrides.identity_verified
        if overrides.resolution_mode is not None:
            case.resolution_mode = overrides.resolution_mode

    case.agent_context_summary = case.build_agent_context_summary()
    return case


@router.post("", response_model=BorrowerProfile, status_code=status.HTTP_201_CREATED)
def create_borrower_profile(request: CreateBorrowerProfileRequest) -> BorrowerProfile:
    borrower_profile = BorrowerProfile(
        borrower_id=_generate_borrower_id(),
        full_name=request.full_name,
        phone_number=request.phone_number,
    )

    try:
        created_profile = service.create_borrower_profile(borrower_profile)
        if request.create_case:
            case = _build_case_from_defaults(
                borrower_id=created_profile.borrower_id,
                overrides=request.case_overrides,
            )
            borrower_case_service.create_borrower_case(case)
        return created_profile
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except KeyError as error:
        service.delete_borrower_profile(borrower_profile.borrower_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except Exception as error:
        service.delete_borrower_profile(borrower_profile.borrower_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.get("", response_model=list[BorrowerProfile])
def list_borrower_profiles() -> list[BorrowerProfile]:
    return service.list_borrower_profiles()


@router.get("/{borrower_id}", response_model=BorrowerProfile)
def get_borrower_profile(borrower_id: str) -> BorrowerProfile:
    borrower_profile = service.get_borrower_profile(borrower_id)
    if borrower_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower profile not found")
    return borrower_profile


@router.put("/{borrower_id}", response_model=BorrowerProfile)
def update_borrower_profile(borrower_id: str, borrower_profile: BorrowerProfile) -> BorrowerProfile:
    try:
        return service.update_borrower_profile(borrower_id, borrower_profile)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{borrower_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_borrower_profile(borrower_id: str) -> DeleteResponse:
    deleted = service.delete_borrower_profile(borrower_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower profile not found")
    return DeleteResponse(deleted=True)
