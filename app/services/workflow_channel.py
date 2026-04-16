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

    def build_voice_transition_reply(self, base_reply: str | None = None) -> str:
        notice = "The next step will continue by phone on your registered number. Chat is paused while that call is attempted."
        if not base_reply:
            return notice
        return f"{base_reply}\n\n{notice}"

    def build_voice_pending_reply(self) -> str:
        return "Resolution is configured for voice mode. The next step is being handled by phone, so chat is paused for this stage."


workflow_channel_service = WorkflowChannelService()
