from __future__ import annotations

from app.domain.borrower_case import BorrowerCase, ResolutionMode


DEFAULT_BORROWER_RESOLUTION_MODE = ResolutionMode.VOICE
DEFAULT_TESTER_RESOLUTION_MODE = ResolutionMode.CHAT


class WorkflowChannelService:
    def resolve_resolution_mode(
        self,
        requested_mode: ResolutionMode | None,
        borrower_case: BorrowerCase | None = None,
        default_mode: ResolutionMode = DEFAULT_BORROWER_RESOLUTION_MODE,
    ) -> ResolutionMode:
        if requested_mode is not None:
            return requested_mode
        if borrower_case is not None:
            return borrower_case.resolution_mode
        return default_mode

    def update_resolution_mode(self, borrower_case: BorrowerCase, resolution_mode: ResolutionMode) -> bool:
        if borrower_case.resolution_mode == resolution_mode:
            return False
        borrower_case.resolution_mode = resolution_mode
        return True


workflow_channel_service = WorkflowChannelService()
