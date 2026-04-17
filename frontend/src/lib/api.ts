import {
  BorrowerPortalLoginResponse,
  ResolutionMode,
  BorrowerWorkflowMessageResponse,
  BorrowerProfileCreateInput,
  BorrowerProfileRecord,
  EvaluateSimulationResponse,
  PromptChangeBatchResponse,
  PromptVersionActivateResponse,
  PromptVersionRevertResponse,
  ScenarioCreateInput,
  ScenarioRecord,
  SimulationStartInput,
  SimulationStartResponse,
  SimulationStatusResponse,
  TranscriptEvent,
} from "@/types/borrower";
import { EvalPerformanceDataset } from "@/types/performance";
import { PromptEvolutionActivateResponse, PromptEvolutionResponse } from "@/types/prompt-evolution";
import { ComplianceConfig } from "@/types/compliance";
import { LenderPolicyRecord, UpsertLenderPolicyResult } from "@/types/lender-policy";
import { MetaEvalLatestPair, MetaEvalRunRecord, MetaEvalRunRequest } from "@/types/meta-eval";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export function getBorrowerRealtimeWebSocketUrl(borrowerId: string): string {
  const base = API_BASE_URL.replace(/^http/, "ws");
  return `${base}/borrower-realtime/ws/${borrowerId}`;
}

export async function createBorrowerProfile(
  payload: BorrowerProfileCreateInput
): Promise<BorrowerProfileRecord> {
  const caseOverrides = payload.caseOverrides ?? {};
  const response = await fetch(`${API_BASE_URL}/borrower-profiles`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      full_name: payload.fullName,
      phone_number: payload.phoneNumber,
      create_case: true,
      case_overrides: {
        workflow_id: caseOverrides.workflowId,
        lender_id: caseOverrides.lenderId,
        loan_id_masked: caseOverrides.loanIdMasked,
        amount_due: caseOverrides.amountDue,
        stage: caseOverrides.stage,
        case_status: caseOverrides.caseStatus,
        resolution_mode: caseOverrides.resolutionMode,
      },
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to create borrower profile");
  }

  return response.json();
}

export async function borrowerPortalLogin(
  phoneNumber: string,
  password: string
): Promise<BorrowerPortalLoginResponse> {
  const response = await fetch(`${API_BASE_URL}/borrower-auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      phone_number: phoneNumber,
      password,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed borrower login");
  }
  return response.json();
}

export async function sendBorrowerChatMessage(payload: {
  borrowerId: string;
  workflowId: string;
  message: string;
  resolutionMode?: ResolutionMode;
}): Promise<BorrowerWorkflowMessageResponse> {
  const response = await fetch(`${API_BASE_URL}/workflows/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      borrower_id: payload.borrowerId,
      workflow_id: payload.workflowId,
      message: payload.message,
      resolution_mode: payload.resolutionMode,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to send borrower message");
  }
  return response.json();
}

export async function listScenarios(): Promise<ScenarioRecord[]> {
  const response = await fetch(`${API_BASE_URL}/evals/scenarios`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to load scenarios");
  }
  return response.json();
}

export async function createScenario(payload: ScenarioCreateInput): Promise<ScenarioRecord> {
  const response = await fetch(`${API_BASE_URL}/evals/scenarios`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      scenario_id: payload.scenarioId,
      borrower_id: payload.borrowerId || null,
      opening_message: payload.openingMessage,
      scenario_description: payload.scenarioDescription || null,
      borrower_profile: payload.borrowerProfile,
      borrower_intent: payload.borrowerIntent,
      stop_condition: payload.stopCondition,
      expected_path_notes: payload.expectedPathNotes || null,
      reply_style_rules: payload.replyStyleRules
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      follow_up_messages: payload.followUpMessages
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to create scenario");
  }
  return response.json();
}

export async function startSimulation(payload: SimulationStartInput): Promise<SimulationStartResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      borrower_id: payload.borrowerId,
      scenario_id: payload.scenarioId,
      project_context_id: payload.projectContextId ?? "collections_v1",
      max_turns: payload.maxTurns ?? 50,
      reset_case: true,
      clear_experiment_log: true,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to start simulation");
  }
  return response.json();
}

export async function getSimulationStatus(runId: string): Promise<SimulationStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch simulation status");
  }
  return response.json();
}

export async function getSimulationEvents(runId: string): Promise<TranscriptEvent[]> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}/events`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch simulation transcript");
  }
  return response.json();
}

export async function evaluateSimulation(runId: string): Promise<EvaluateSimulationResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}/evaluate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      metrics_key: "collections_agent_eval",
      lender_id: "nira",
      persist: true,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to evaluate simulation");
  }
  return response.json();
}

export async function applyPromptChanges(
  runId: string,
  forceActivate: boolean
): Promise<PromptChangeBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}/prompt-changes/apply`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      target_agent_ids: ["agent_1", "agent_2", "agent_3"],
      force_activate: forceActivate,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to apply prompt changes");
  }
  return response.json();
}

export async function activatePromptVersion(
  runId: string,
  agentId: string,
  versionId: string
): Promise<PromptVersionActivateResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}/prompt-changes/activate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_id: agentId,
      version_id: versionId,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to activate prompt version");
  }
  return response.json();
}

export async function revertPromptVersion(
  runId: string,
  agentId: string,
  revertToVersionId: string
): Promise<PromptVersionRevertResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/simulations/${runId}/prompt-changes/revert`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_id: agentId,
      revert_to_version_id: revertToVersionId,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to revert prompt version");
  }
  return response.json();
}

export async function getEvalPerformance(scenarioId?: string): Promise<EvalPerformanceDataset> {
  const query = scenarioId ? `?scenario_id=${encodeURIComponent(scenarioId)}` : "";
  const response = await fetch(`${API_BASE_URL}/evals/performance${query}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch evaluation performance data");
  }
  return response.json();
}

export async function getPromptEvolution(agentId: string): Promise<PromptEvolutionResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/prompt-evolution/${encodeURIComponent(agentId)}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch prompt evolution data");
  }
  return response.json();
}

export async function activatePromptEvolutionVersion(
  agentId: string,
  versionId: string
): Promise<PromptEvolutionActivateResponse> {
  const response = await fetch(`${API_BASE_URL}/evals/prompt-evolution/activate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      agent_id: agentId,
      version_id: versionId,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to activate prompt version");
  }
  return response.json();
}

export async function getComplianceConfig(): Promise<ComplianceConfig> {
  const response = await fetch(`${API_BASE_URL}/evals/compliance`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch compliance rules");
  }
  return response.json();
}

export async function updateComplianceConfig(rulesText: string): Promise<ComplianceConfig> {
  const response = await fetch(`${API_BASE_URL}/evals/compliance`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      rules_text: rulesText,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to update compliance rules");
  }
  return response.json();
}

export async function resetComplianceConfig(): Promise<ComplianceConfig> {
  const response = await fetch(`${API_BASE_URL}/evals/compliance/reset`, {
    method: "POST",
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to reset compliance rules");
  }
  return response.json();
}

export async function listLenderPolicies(): Promise<LenderPolicyRecord[]> {
  const response = await fetch(`${API_BASE_URL}/lender-policies`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch lender policies");
  }
  return response.json();
}

export async function getLenderPolicy(lenderId: string): Promise<LenderPolicyRecord | null> {
  const response = await fetch(`${API_BASE_URL}/lender-policies/${encodeURIComponent(lenderId)}`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch lender policy");
  }
  return response.json();
}

export async function upsertLenderPolicy(
  lenderId: string,
  policyText: string
): Promise<UpsertLenderPolicyResult> {
  const existing = await getLenderPolicy(lenderId);
  const method = existing ? "PUT" : "POST";
  const endpoint = existing
    ? `${API_BASE_URL}/lender-policies/${encodeURIComponent(lenderId)}`
    : `${API_BASE_URL}/lender-policies`;

  const response = await fetch(endpoint, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      lender_id: lenderId,
      policy: policyText,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to save lender policy");
  }

  const record = (await response.json()) as LenderPolicyRecord;
  return {
    record,
    mode: existing ? "updated" : "created",
  };
}

export async function getMetaEvalLatestPair(): Promise<MetaEvalLatestPair> {
  const response = await fetch(`${API_BASE_URL}/evals/meta-eval/latest-pair`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch latest meta eval experiment pair");
  }
  return response.json();
}

export async function runMetaEval(payload: MetaEvalRunRequest): Promise<MetaEvalRunRecord> {
  const response = await fetch(`${API_BASE_URL}/evals/meta-eval/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      metrics_key: payload.metrics_key,
      lender_id: payload.lender_id,
      force_activate: payload.force_activate,
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to run meta evaluation");
  }
  return response.json();
}

export async function listMetaEvalRuns(): Promise<MetaEvalRunRecord[]> {
  const response = await fetch(`${API_BASE_URL}/evals/meta-eval/runs`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Failed to fetch meta eval runs");
  }
  return response.json();
}
