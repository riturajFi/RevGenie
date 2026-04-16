export type BorrowerProfileCreateInput = {
  fullName: string;
  phoneNumber: string;
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
  principalOutstanding: number;
  dpd: number;
  caseType: string;
  stage: string;
  caseStatus: string;
  nextAllowedActions: string;
};

export type ScenarioRecord = {
  scenario_id: string;
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
