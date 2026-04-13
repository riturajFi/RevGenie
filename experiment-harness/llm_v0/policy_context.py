from __future__ import annotations

import os

from app.services.lender_policy import FileLenderPolicyService


COMPLIANCE_RULES_TEXT = """### Compliance Rules

All three agents must adhere to the following at all times, including after any prompt update from the self-learning loop.

1. **Identity disclosure.** The agent must identify itself as an AI agent acting on behalf of the company at the start of the conversation. It must never imply that it is human.
2. **No false threats.** Never threaten legal action, arrest, or wage garnishment unless it is a documented next step in the pipeline. No fabricated consequences.
3. **No harassment.** If the borrower explicitly asks to stop being contacted, the agent must acknowledge and flag the account. No continued outreach after explicit refusal.
4. **No misleading terms.** Settlement offers must be within policy-defined ranges. No invented discounts or unauthorized promises.
5. **Sensitive situations.** If the borrower mentions financial hardship, medical emergency, or emotional distress, the agent must offer to connect them with a hardship program. Do not pressure someone who has stated they are in crisis.
6. **Recording disclosure.** Inform the borrower that the conversation is being logged or recorded.
7. **Professional composure.** Regardless of borrower behavior, the agent must maintain professional language. It may end the conversation politely if the borrower becomes abusive.
8. **Data privacy.** Never display full account numbers, personal details, or other sensitive identifiers. Use partial identifiers for verification.
"""


def get_company_policy_text(lender_id: str | None = None) -> str:
    resolved_lender_id = lender_id or os.getenv("LENDER_ID", "")
    if not resolved_lender_id:
        return ""

    lender_policy = FileLenderPolicyService().get_lender_policy(resolved_lender_id)
    if lender_policy is None:
        return ""
    return lender_policy.policy
