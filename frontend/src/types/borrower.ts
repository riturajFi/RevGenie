export type ResolutionMode = "CHAT" | "VOICE";

export type BorrowerProfileCreateInput = {
  fullName: string;
  phoneNumber: string;
  caseOverrides?: {
    workflowId?: string;
    lenderId?: string;
    loanIdMasked?: string;
    amountDue?: number;
    stage?: "ASSESSMENT" | "RESOLUTION" | "FINAL_NOTICE";
    caseStatus?: "OPEN" | "RESOLVED" | "CLOSED" | "STOP_CONTACT";
    resolutionMode?: ResolutionMode;
  };
};

export type BorrowerProfileRecord = {
  borrower_id: string;
  full_name: string;
  phone_number: string;
};

export type BorrowerTestDefaults = {
  lenderId: string;
  workflowId: string;
  loanIdMasked: string;
  amountDue: number;
  stage: string;
  caseStatus: string;
};

export type ScenarioRecord = {
  scenario_id: string;
  borrower_id: string | null;
  opening_message: string;
  scenario_description: string | null;
  borrower_profile: string;
  borrower_intent: string;
  reply_style_rules: string[];
  stop_condition: string;
  expected_path_notes: string | null;
  follow_up_messages: string[];
};

export type ScenarioCreateInput = {
  scenarioId: string;
  borrowerId: string;
  openingMessage: string;
  scenarioDescription: string;
  borrowerProfile: string;
  borrowerIntent: string;
  stopCondition: string;
  expectedPathNotes: string;
  replyStyleRules: string;
  followUpMessages: string;
};

export type SimulationStartInput = {
  borrowerId: string;
  scenarioId: string;
  projectContextId?: string;
  maxTurns?: number;
};

export type SimulationStartResponse = {
  run_id: string;
  workflow_id: string;
  experiment_id: string;
  status: string;
};

export type SimulationStatusResponse = {
  run_id: string;
  workflow_id: string;
  experiment_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result: {
    experiment_id: string;
    workflow_id: string;
    borrower_id: string;
    scenario_id: string;
    turn_count: number;
    stop_reason: string;
  } | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type TranscriptEvent = {
  id: number;
  actor: string | null;
  message_text: string;
  created_at: string;
};

export type JudgeScore = {
  metric_id: string;
  name: string;
  score: number;
  reason: string;
};

export type JudgeResult = {
  experiment_id: string;
  scores: JudgeScore[];
  overall_score: number;
  verdict: string;
};

export type EvaluateSimulationResponse = {
  run_id: string;
  workflow_id: string;
  experiment_id: string;
  result: JudgeResult;
};

export type PromptChangeApplyResult = {
  agent_id: string;
  old_version_id: string;
  new_version_id: string;
  diff_summary: string;
  why_this_change: string;
  activation_status: "active" | "inactive";
};

export type PromptChangeBatchResponse = {
  run_id: string;
  workflow_id: string;
  experiment_id: string;
  results: PromptChangeApplyResult[];
};

export type PromptVersionActivateResponse = {
  run_id: string;
  agent_id: string;
  active_version_id: string;
};

export type PromptVersionRevertResponse = {
  run_id: string;
  agent_id: string;
  active_version_id: string;
};

export type BorrowerCaseSnapshot = {
  core: {
    borrower_id: string;
    workflow_id: string;
    loan_id_masked: string;
    lender_id: string;
    stage: string;
    case_status: string;
    amount_due: number;
    final_disposition: string | null;
  };
  attributes: Record<string, unknown>;
  latest_handoff_summary: string | null;
};

export type BorrowerPortalLoginResponse = {
  borrower_profile: BorrowerProfileRecord;
  borrower_case: BorrowerCaseSnapshot;
};

export type BorrowerChatMessage = {
  id: string;
  actor: "borrower" | "agent" | "system";
  text: string;
  created_at: string;
};

export type BorrowerWorkflowMessageResponse = {
  workflow_id: string;
  reply: string | null;
  stage: string;
  final_result: string | null;
  resolution_mode: ResolutionMode;
  voice_call_id: string | null;
  voice_call_status: string | null;
};

export type BorrowerConversationState = {
  borrower_case: BorrowerCaseSnapshot;
  workflow_id: string;
  final_result: string | null;
  input_enabled: boolean;
  messages: BorrowerChatMessage[];
};

export type BorrowerSocketClientMessage = {
  type: "borrower_message";
  message: string;
};

export type BorrowerSocketServerEvent =
  | {
      type: "conversation_state";
      state: BorrowerConversationState;
      message?: null;
    }
  | {
      type: "error";
      state?: null;
      message: string;
    };
