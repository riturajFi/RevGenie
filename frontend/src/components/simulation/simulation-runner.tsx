"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  activatePromptVersion,
  applyPromptChanges,
  createScenario,
  evaluateSimulation,
  getPromptChangeJobStatus,
  getSimulationEvents,
  getSimulationStatus,
  listScenarios,
  revertPromptVersion,
  startSimulation,
} from "@/lib/api";
import {
  EvaluateSimulationResponse,
  PromptChangeApplyResult,
  PromptChangeBatchResponse,
  PromptChangeJobStatusResponse,
  ScenarioCreateInput,
  ScenarioRecord,
  SimulationStatusResponse,
  TranscriptEvent,
} from "@/types/borrower";

const emptyScenarioForm: ScenarioCreateInput = {
  scenarioId: "",
  borrowerId: "",
  openingMessage: "",
  scenarioDescription: "",
  borrowerProfile: "",
  borrowerIntent: "",
  stopCondition: "",
  expectedPathNotes: "",
  replyStyleRules: "",
  followUpMessages: "",
};

function actorClass(actor: string | null): string {
  if (!actor) return "msg-system";
  if (actor === "borrower") return "msg-borrower";
  if (actor.startsWith("agent_")) return "msg-agent";
  return "msg-system";
}

function actorLabel(actor: string | null): string {
  if (!actor) return "system";
  if (actor === "borrower") return "Borrower";
  if (actor === "agent_1") return "Agent 1";
  if (actor === "agent_2") return "Agent 2";
  if (actor === "agent_3") return "Agent 3";
  return actor.replaceAll("_", " ");
}

type ParsedEventPayload =
  | { kind: "plain"; text: string }
  | { kind: "handoff"; fromStage: string; toStage: string; summary: string }
  | {
      kind: "case_state";
      fromStage: string;
      toStage: string;
      core: Record<string, unknown>;
      salient: Record<string, unknown>;
    };

function toTitleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function parseEventPayload(event: TranscriptEvent): ParsedEventPayload {
  const text = event.message_text;
  if (!text.trim().startsWith("{")) {
    return { kind: "plain", text };
  }
  try {
    const payload = JSON.parse(text) as Record<string, unknown>;
    if (
      typeof payload.from_stage === "string" &&
      typeof payload.to_stage === "string" &&
      typeof payload.summary === "string"
    ) {
      return {
        kind: "handoff",
        fromStage: payload.from_stage,
        toStage: payload.to_stage,
        summary: payload.summary,
      };
    }
    if (
      typeof payload.from_stage === "string" &&
      typeof payload.to_stage === "string" &&
      payload.borrower_case_state &&
      typeof payload.borrower_case_state === "object"
    ) {
      const state = payload.borrower_case_state as Record<string, unknown>;
      const core = (state.core as Record<string, unknown>) ?? state;
      const attributes = (state.attributes as Record<string, unknown>) ?? state;
      const salientKeys = [
        "resolution_mode",
        "resolution_call_id",
        "resolution_call_status",
      ];
      const salient = salientKeys.reduce<Record<string, unknown>>((acc, key) => {
        const value = attributes[key];
        if (value !== undefined && value !== null && value !== "") {
          acc[key] = value;
        }
        return acc;
      }, {});
      return {
        kind: "case_state",
        fromStage: payload.from_stage,
        toStage: payload.to_stage,
        core,
        salient,
      };
    }
    return { kind: "plain", text };
  } catch {
    return { kind: "plain", text };
  }
}

export function SimulationRunner() {
  const [scenarios, setScenarios] = useState<ScenarioRecord[]>([]);
  const [selectedScenarioId, setSelectedScenarioId] = useState("");
  const [borrowerId, setBorrowerId] = useState("b_001");
  const [maxTurns, setMaxTurns] = useState(50);
  const [createMode, setCreateMode] = useState(false);
  const [scenarioForm, setScenarioForm] = useState<ScenarioCreateInput>(emptyScenarioForm);
  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<SimulationStatusResponse | null>(null);
  const [events, setEvents] = useState<TranscriptEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingScenarios, setIsLoadingScenarios] = useState(true);
  const [isCreatingScenario, setIsCreatingScenario] = useState(false);
  const [isStartingSimulation, setIsStartingSimulation] = useState(false);
  const [expandedStateLogIds, setExpandedStateLogIds] = useState<number[]>([]);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluation, setEvaluation] = useState<EvaluateSimulationResponse | null>(null);
  const [autoActivatePromptChanges, setAutoActivatePromptChanges] = useState(true);
  const [isApplyingPromptChanges, setIsApplyingPromptChanges] = useState(false);
  const [promptChanges, setPromptChanges] = useState<PromptChangeBatchResponse | null>(null);
  const [promptChangeJob, setPromptChangeJob] = useState<PromptChangeJobStatusResponse | null>(null);
  const [isActivatingByAgent, setIsActivatingByAgent] = useState<Record<string, boolean>>({});
  const [isRevertingByAgent, setIsRevertingByAgent] = useState<Record<string, boolean>>({});

  async function loadScenarios() {
    setIsLoadingScenarios(true);
    setError(null);
    try {
      const loaded = await listScenarios();
      setScenarios(loaded);
      if (!selectedScenarioId && loaded.length > 0) {
        const firstScenario = loaded[0];
        setSelectedScenarioId(firstScenario.scenario_id);
        if (firstScenario.borrower_id) {
          setBorrowerId(firstScenario.borrower_id);
        }
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load scenarios.");
    } finally {
      setIsLoadingScenarios(false);
    }
  }

  useEffect(() => {
    void loadScenarios();
  }, []);

  useEffect(() => {
    if (!runId) return;
    const activeRunId = runId;
    let cancelled = false;

    async function poll() {
      try {
        const [nextStatus, nextEvents] = await Promise.all([
          getSimulationStatus(activeRunId),
          getSimulationEvents(activeRunId),
        ]);
        if (cancelled) return;
        setStatus(nextStatus);
        setEvents(nextEvents);
        if (nextStatus.status === "queued" || nextStatus.status === "running") {
          window.setTimeout(poll, 1200);
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Failed to poll simulation run.");
        }
      }
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  useEffect(() => {
    if (!runId || !promptChangeJob || (promptChangeJob.status !== "queued" && promptChangeJob.status !== "running")) {
      return;
    }
    const activeRunId = runId;
    const activeJobId = promptChangeJob.job_id;
    let cancelled = false;

    async function pollPromptChangeJob() {
      try {
        const nextJob = await getPromptChangeJobStatus(activeRunId, activeJobId);
        if (cancelled) return;
        setPromptChangeJob(nextJob);
        if (nextJob.status === "completed") {
          setPromptChanges({
            run_id: nextJob.run_id,
            workflow_id: nextJob.workflow_id,
            experiment_id: nextJob.experiment_id,
            results: nextJob.results,
          });
          return;
        }
        if (nextJob.status === "failed") {
          setError(nextJob.error || "Prompt change job failed.");
          return;
        }
        if (nextJob.status === "queued" || nextJob.status === "running") {
          window.setTimeout(pollPromptChangeJob, 900);
        }
      } catch (pollError) {
        if (!cancelled) {
          setError(pollError instanceof Error ? pollError.message : "Failed to poll prompt change job.");
        }
      }
    }

    void pollPromptChangeJob();
    return () => {
      cancelled = true;
    };
  }, [runId, promptChangeJob]);

  async function handleCreateScenario(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsCreatingScenario(true);
    setError(null);
    try {
      const created = await createScenario(scenarioForm);
      setScenarios((current) => [...current, created]);
      setSelectedScenarioId(created.scenario_id);
      if (created.borrower_id) {
        setBorrowerId(created.borrower_id);
      }
      setScenarioForm(emptyScenarioForm);
      setCreateMode(false);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create scenario.");
    } finally {
      setIsCreatingScenario(false);
    }
  }

  async function handleStartSimulation() {
    if (!selectedScenarioId) {
      setError("Select a scenario before running the simulation.");
      return;
    }
    setIsStartingSimulation(true);
    setError(null);
    setStatus(null);
    setEvents([]);
    setExpandedStateLogIds([]);
    setEvaluation(null);
    setPromptChanges(null);
    setPromptChangeJob(null);
    setIsActivatingByAgent({});
    setIsRevertingByAgent({});
    try {
      const normalizedMaxTurns = Number.isFinite(maxTurns) && maxTurns > 0 ? maxTurns : 50;
      const started = await startSimulation({
        borrowerId,
        scenarioId: selectedScenarioId,
        maxTurns: normalizedMaxTurns,
      });
      setRunId(started.run_id);
    } catch (startError) {
      setError(startError instanceof Error ? startError.message : "Failed to start simulation.");
    } finally {
      setIsStartingSimulation(false);
    }
  }

  function handleSelectScenario(nextScenarioId: string) {
    setSelectedScenarioId(nextScenarioId);
    const selected = scenarios.find((scenario) => scenario.scenario_id === nextScenarioId);
    if (selected?.borrower_id) {
      setBorrowerId(selected.borrower_id);
    }
  }

  async function handleEvaluateSimulation() {
    if (!runId) return;
    setIsEvaluating(true);
    setError(null);
    try {
      const result = await evaluateSimulation(runId);
      setEvaluation(result);
    } catch (evaluateError) {
      setError(evaluateError instanceof Error ? evaluateError.message : "Failed to evaluate simulation.");
    } finally {
      setIsEvaluating(false);
    }
  }

  async function handleApplyPromptChanges() {
    if (!runId || !evaluation) return;
    setIsApplyingPromptChanges(true);
    setError(null);
    try {
      const result = await applyPromptChanges(runId, autoActivatePromptChanges);
      setPromptChanges(null);
      setPromptChangeJob({
        ...result,
        started_at: new Date().toISOString(),
        finished_at: null,
        message: "Queued prompt improvement run.",
        error: null,
        agent_progress: [],
        results: [],
      });
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Failed to apply prompt changes.");
    } finally {
      setIsApplyingPromptChanges(false);
    }
  }

  async function handleActivatePromptChange(item: PromptChangeApplyResult) {
    if (!runId) return;
    setIsActivatingByAgent((current) => ({ ...current, [item.agent_id]: true }));
    setError(null);
    try {
      await activatePromptVersion(runId, item.agent_id, item.new_version_id);
      setPromptChanges((current) => {
        if (!current) return current;
        return {
          ...current,
          results: current.results.map((result) =>
            result.agent_id === item.agent_id
              ? {
                  ...result,
                  activation_status: "candidate",
                }
              : result
          ),
        };
      });
    } catch (activationError) {
      setError(activationError instanceof Error ? activationError.message : "Failed to activate prompt change.");
    } finally {
      setIsActivatingByAgent((current) => ({ ...current, [item.agent_id]: false }));
    }
  }

  async function handleRevertPromptChange(item: PromptChangeApplyResult) {
    if (!runId) return;
    setIsRevertingByAgent((current) => ({ ...current, [item.agent_id]: true }));
    setError(null);
    try {
      await revertPromptVersion(runId, item.agent_id, item.old_version_id);
      setPromptChanges((current) => {
        if (!current) return current;
        return {
          ...current,
          results: current.results.map((result) =>
            result.agent_id === item.agent_id
              ? {
                  ...result,
                  activation_status: "active",
                }
              : result
          ),
        };
      });
    } catch (revertError) {
      setError(revertError instanceof Error ? revertError.message : "Failed to revert prompt change.");
    } finally {
      setIsRevertingByAgent((current) => ({ ...current, [item.agent_id]: false }));
    }
  }

  return (
    <section className="simulation-layout">
      <div className="panel simulation-control">
        <div className="panel-header">
          <div>
            <p className="eyebrow">Admin</p>
            <h2>Run Simulation</h2>
          </div>
          <p className="panel-copy">
            Choose an existing scenario or create one, then run a read-only tester vs collector simulation with live
            transcript updates.
          </p>
        </div>

        <div className="simulation-controls-grid">
          <label className="field">
            <span>Borrower ID</span>
            <input value={borrowerId} onChange={(event) => setBorrowerId(event.target.value)} />
          </label>
          <label className="field">
            <span>Max Turns</span>
            <input
              type="number"
              min={1}
              max={200}
              value={maxTurns}
              onChange={(event) => setMaxTurns(Number(event.target.value))}
            />
          </label>
            <label className="field">
              <span>Scenario</span>
              <select
                className="select-input"
                value={selectedScenarioId}
                onChange={(event) => handleSelectScenario(event.target.value)}
                disabled={isLoadingScenarios}
              >
              {scenarios.map((scenario) => (
                <option value={scenario.scenario_id} key={scenario.scenario_id}>
                  {scenario.scenario_id}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-actions">
          <button type="button" className="button button-primary" onClick={handleStartSimulation} disabled={isStartingSimulation}>
            {isStartingSimulation ? "Starting..." : "Simulate"}
          </button>
          {status?.status === "completed" ? (
            <button
              type="button"
              className="button button-primary"
              onClick={handleEvaluateSimulation}
              disabled={isEvaluating}
            >
              {isEvaluating ? "Evaluating..." : "Evaluate"}
            </button>
          ) : null}
          <button type="button" className="button button-secondary" onClick={() => setCreateMode((current) => !current)}>
            {createMode ? "Cancel Scenario Create" : "Create Scenario"}
          </button>
          <button type="button" className="button button-secondary" onClick={() => void loadScenarios()}>
            Refresh Scenarios
          </button>
        </div>

        {status ? (
          <div className="run-meta">
            <div>
              <span>Run</span>
              <strong>{status.run_id}</strong>
            </div>
            <div>
              <span>Workflow</span>
              <strong>{status.workflow_id}</strong>
            </div>
            <div>
              <span>Experiment</span>
              <strong>{status.experiment_id}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{status.status}</strong>
            </div>
          </div>
        ) : null}

        {error ? <p className="form-error">{error}</p> : null}
      </div>

      {evaluation ? (
        <div className="panel evaluation-panel">
          <div className="evaluation-header">
            <h3>Evaluation Report</h3>
            <div className="evaluation-summary">
              <span>Verdict: {evaluation.result.verdict.toUpperCase()}</span>
              <strong>Overall Score: {evaluation.result.overall_score.toFixed(2)} / 10</strong>
            </div>
          </div>
          <div className="prompt-change-toolbar">
            <label className="checkbox-inline">
              <input
                type="checkbox"
                checked={autoActivatePromptChanges}
                onChange={(event) => setAutoActivatePromptChanges(event.target.checked)}
              />
              <span>Auto-activate only if benchmark passes</span>
            </label>
            <button
              type="button"
              className="button button-primary"
              onClick={handleApplyPromptChanges}
              disabled={
                isApplyingPromptChanges ||
                promptChangeJob?.status === "queued" ||
                promptChangeJob?.status === "running"
              }
            >
              {isApplyingPromptChanges || promptChangeJob?.status === "queued" || promptChangeJob?.status === "running"
                ? "Running Prompt Improvement..."
                : "Propose Prompt Changes (Agent 1, 2, 3)"}
            </button>
          </div>
          {promptChanges ? (
            <p className="prompt-change-note">
              Candidate prompt versions are benchmarked on the fixed evaluation set before they can be adopted.
            </p>
          ) : null}
          {promptChangeJob && (promptChangeJob.status === "queued" || promptChangeJob.status === "running") ? (
            <div className="prompt-change-results">
              <h4>Prompt Change Progress</h4>
              <p>{promptChangeJob.message}</p>
              <div className="evaluation-metrics">
                {promptChangeJob.agent_progress.map((progress) => (
                  <article className="metric-card" key={progress.agent_id}>
                    <header>
                      <strong>{progress.agent_id}</strong>
                      <span>{progress.status.toUpperCase()}</span>
                    </header>
                    <p>{progress.message}</p>
                    {progress.variant ? (
                      <p>
                        Current run: {progress.variant === "current_prompt" ? "current prompt" : "new prompt"}
                      </p>
                    ) : null}
                    {progress.total_runs > 0 ? (
                      <p>
                        Scenario tests: {progress.completed_runs}/{progress.total_runs}
                      </p>
                    ) : null}
                    {progress.scenario_id ? <p>Current scenario: {progress.scenario_id}</p> : null}
                    {progress.transcript_events.length > 0 ? (
                      <div className="live-transcript">
                        {progress.transcript_events.map((event, index) => (
                          <div className="live-transcript-row" key={`${progress.agent_id}-${index}`}>
                            <strong>{actorLabel(event.actor)}</strong>
                            <span>{event.message}</span>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}
          <div className="evaluation-metrics">
            {evaluation.result.scores.map((item) => (
              <article className="metric-card" key={item.metric_id}>
                <header>
                  <strong>{item.name}</strong>
                  <span>{item.score.toFixed(2)} / 10</span>
                </header>
                <p>{item.reason}</p>
              </article>
            ))}
          </div>
          {promptChanges ? (
            <div className="prompt-change-results">
              <h4>Prompt Change Results</h4>
              <div className="evaluation-metrics">
                {promptChanges.results.map((result) => (
                  <article className="metric-card" key={result.agent_id}>
                    <header>
                      <strong>{result.agent_id}</strong>
                      <span>{result.activation_status.toUpperCase()}</span>
                    </header>
                    <p>{result.diff_summary}</p>
                    <p>{result.why_this_change}</p>
                    <p>
                      Version: {result.old_version_id} {"->"} {result.new_version_id}
                    </p>
                    {result.benchmark_result ? (
                      <>
                        <p>
                          Benchmark: {result.benchmark_result.baseline_mean_score.toFixed(2)} {"->"}{" "}
                          {result.benchmark_result.candidate_mean_score.toFixed(2)} (
                          {result.benchmark_result.mean_score_delta >= 0 ? "+" : ""}
                          {result.benchmark_result.mean_score_delta.toFixed(2)})
                        </p>
                        <p>
                          Scenario wins: {(result.benchmark_result.candidate_win_rate * 100).toFixed(0)}% {" | "}
                          Compliance stable: {result.benchmark_result.compliance_non_regression ? "yes" : "no"}
                        </p>
                        <p>{result.benchmark_result.reason}</p>
                        {result.benchmark_result.scenario_results.length > 0 ? (
                          <div className="meta-pill-row">
                            {result.benchmark_result.scenario_results.map((scenarioResult) => (
                              <span key={scenarioResult.scenario_id} className="meta-chip">
                                {scenarioResult.scenario_id}: {scenarioResult.baseline_score.toFixed(1)} {"->"}{" "}
                                {scenarioResult.candidate_score.toFixed(1)}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </>
                    ) : null}
                    {result.activation_status === "candidate" ? (
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => void handleActivatePromptChange(result)}
                        disabled={Boolean(isActivatingByAgent[result.agent_id])}
                      >
                        {isActivatingByAgent[result.agent_id] ? "Activating..." : "Activate"}
                      </button>
                    ) : null}
                    {result.activation_status === "active" ? (
                      <button
                        type="button"
                        className="button button-secondary"
                        onClick={() => void handleRevertPromptChange(result)}
                        disabled={Boolean(isRevertingByAgent[result.agent_id])}
                      >
                        {isRevertingByAgent[result.agent_id] ? "Reverting..." : "Revert"}
                      </button>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {createMode ? (
        <form className="panel scenario-form" onSubmit={handleCreateScenario}>
          <h3>Create Scenario</h3>
          <div className="scenario-grid">
            <label className="field">
              <span>Scenario ID</span>
              <input
                required
                value={scenarioForm.scenarioId}
                onChange={(event) => setScenarioForm((current) => ({ ...current, scenarioId: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Borrower ID</span>
              <input
                required
                value={scenarioForm.borrowerId}
                onChange={(event) => setScenarioForm((current) => ({ ...current, borrowerId: event.target.value }))}
              />
            </label>
            <label className="field">
              <span>Opening Message</span>
              <textarea
                required
                rows={3}
                value={scenarioForm.openingMessage}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, openingMessage: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Borrower Profile</span>
              <textarea
                required
                rows={3}
                value={scenarioForm.borrowerProfile}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, borrowerProfile: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Borrower Intent</span>
              <textarea
                required
                rows={3}
                value={scenarioForm.borrowerIntent}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, borrowerIntent: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Stop Condition</span>
              <textarea
                required
                rows={2}
                value={scenarioForm.stopCondition}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, stopCondition: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Scenario Description (optional)</span>
              <textarea
                rows={2}
                value={scenarioForm.scenarioDescription}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, scenarioDescription: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Expected Path Notes (optional)</span>
              <textarea
                rows={2}
                value={scenarioForm.expectedPathNotes}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, expectedPathNotes: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Reply Style Rules (one per line)</span>
              <textarea
                rows={4}
                value={scenarioForm.replyStyleRules}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, replyStyleRules: event.target.value }))
                }
              />
            </label>
            <label className="field">
              <span>Follow Up Messages (one per line)</span>
              <textarea
                rows={4}
                value={scenarioForm.followUpMessages}
                onChange={(event) =>
                  setScenarioForm((current) => ({ ...current, followUpMessages: event.target.value }))
                }
              />
            </label>
          </div>
          <div className="form-actions">
            <button type="submit" className="button button-primary" disabled={isCreatingScenario}>
              {isCreatingScenario ? "Creating..." : "Create Scenario"}
            </button>
          </div>
        </form>
      ) : null}

      <div className="panel transcript-panel">
        <div className="transcript-header">
          <h3>Simulation Transcript</h3>
          <p>Read-only live conversation between borrower simulator and collections agents.</p>
        </div>
        <div className="transcript-stream">
          {events.length === 0 ? (
            <p className="empty-transcript">No transcript events yet. Run a simulation to populate this view.</p>
          ) : (
            events.map((event) => {
              const parsed = parseEventPayload(event);
              const isExpanded = expandedStateLogIds.includes(event.id);
              const isCaseState = parsed.kind === "case_state";

              return (
                <article
                  key={event.id}
                  className={`message-row ${isCaseState ? "msg-state" : actorClass(event.actor)}`}
                >
                  <header>
                    <strong>{actorLabel(event.actor)}</strong>
                    <time>{new Date(event.created_at).toLocaleTimeString()}</time>
                  </header>

                  {parsed.kind === "plain" ? <p>{parsed.text}</p> : null}

                  {parsed.kind === "handoff" ? (
                    <div className="structured-block">
                      <p className="structured-title">
                        Handoff {parsed.fromStage} {"->"} {parsed.toStage}
                      </p>
                      <p>{parsed.summary}</p>
                    </div>
                  ) : null}

                  {parsed.kind === "case_state" ? (
                    <div className="structured-block">
                      <div className="state-summary-row">
                        <p className="structured-title">
                          State Update {parsed.fromStage} {"->"} {parsed.toStage}
                        </p>
                        <button
                          type="button"
                          className="state-toggle"
                          onClick={() =>
                            setExpandedStateLogIds((current) =>
                              current.includes(event.id)
                                ? current.filter((id) => id !== event.id)
                                : [...current, event.id]
                            )
                          }
                        >
                          {isExpanded ? "Hide details" : "Show details"}
                        </button>
                      </div>

                      {isExpanded ? (
                        <>
                          <div className="state-grid">
                            {Object.entries(parsed.core).map(([key, value]) => (
                              <div className="state-item" key={key}>
                                <span>{toTitleCase(key)}</span>
                                <strong>{typeof value === "string" ? value : JSON.stringify(value)}</strong>
                              </div>
                            ))}
                          </div>
                          {Object.keys(parsed.salient).length > 0 ? (
                            <>
                              <p className="salient-title">Salient Notes</p>
                              <div className="state-grid">
                                {Object.entries(parsed.salient).map(([key, value]) => (
                                  <div className="state-item" key={key}>
                                    <span>{toTitleCase(key)}</span>
                                    <strong>{typeof value === "string" ? value : JSON.stringify(value)}</strong>
                                  </div>
                                ))}
                              </div>
                            </>
                          ) : null}
                        </>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              );
            })
          )}
        </div>
      </div>
    </section>
  );
}
