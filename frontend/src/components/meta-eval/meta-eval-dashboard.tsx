"use client";

import { useEffect, useMemo, useState } from "react";

import { getMetaEvalLatestPair, listMetaEvalRuns, runMetaEval } from "@/lib/api";
import { MetaEvalRunRecord } from "@/types/meta-eval";

export function MetaEvalDashboard() {
  const [metricsKey, setMetricsKey] = useState("collections_agent_eval");
  const [lenderId, setLenderId] = useState("nira");
  const [forceActivate, setForceActivate] = useState(true);
  const [beforeExperimentId, setBeforeExperimentId] = useState<string | null>(null);
  const [afterExperimentId, setAfterExperimentId] = useState<string | null>(null);
  const [totalEvaluatedExperiments, setTotalEvaluatedExperiments] = useState(0);
  const [runs, setRuns] = useState<MetaEvalRunRecord[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadData() {
    const [latestPair, allRuns] = await Promise.all([getMetaEvalLatestPair(), listMetaEvalRuns()]);
    setBeforeExperimentId(latestPair.before_experiment_id);
    setAfterExperimentId(latestPair.after_experiment_id);
    setTotalEvaluatedExperiments(latestPair.total_evaluated_experiments);
    setRuns(allRuns);
    setSelectedRunId((current) => {
      if (current && allRuns.some((item) => item.run_id === current)) {
        return current;
      }
      return allRuns.length > 0 ? allRuns[0].run_id : null;
    });
  }

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      setIsLoading(true);
      setError(null);
      try {
        await loadData();
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load meta evaluation data");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRun = useMemo(
    () => runs.find((item) => item.run_id === selectedRunId) ?? (runs.length > 0 ? runs[0] : null),
    [runs, selectedRunId]
  );
  const canRunMetaEval = Boolean(beforeExperimentId && afterExperimentId);

  async function handleRunMetaEval() {
    setIsSubmitting(true);
    setError(null);
    setStatus("Running meta evaluation...");
    try {
      const result = await runMetaEval({
        metrics_key: metricsKey.trim() || "collections_agent_eval",
        lender_id: lenderId.trim(),
        force_activate: forceActivate,
      });
      await loadData();
      setSelectedRunId(result.run_id);
      setStatus(`Meta evaluation completed: ${result.run_id}`);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : "Failed to run meta evaluation");
      setStatus(null);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <section className="panel placeholder-panel">
        <h2>Meta Eval</h2>
        <p>Loading meta evaluation workspace...</p>
      </section>
    );
  }

  return (
    <section className="panel meta-eval-panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Meta Eval</p>
          <h2>Metrics Evolution Validator</h2>
        </div>
        <p className="panel-copy">
          Uses the latest two evaluated experiments automatically. Older manual experiment selection is disabled.
        </p>
      </div>

      <div className="meta-eval-experiment-pair">
        <div className="meta-eval-pill">
          <span>Before Experiment</span>
          <strong>{beforeExperimentId ?? "Not available"}</strong>
        </div>
        <div className="meta-eval-pill">
          <span>After Experiment</span>
          <strong>{afterExperimentId ?? "Not available"}</strong>
        </div>
        <div className="meta-eval-pill">
          <span>Evaluated Experiments</span>
          <strong>{totalEvaluatedExperiments}</strong>
        </div>
      </div>

      <div className="meta-eval-controls">
        <label className="field">
          <span>Metrics Key</span>
          <input value={metricsKey} onChange={(event) => setMetricsKey(event.target.value)} />
        </label>
        <label className="field">
          <span>Lender ID</span>
          <input value={lenderId} onChange={(event) => setLenderId(event.target.value)} />
        </label>
        <label className="checkbox-inline">
          <input
            type="checkbox"
            checked={forceActivate}
            onChange={(event) => setForceActivate(event.target.checked)}
          />
          <span>Auto activate candidate metrics</span>
        </label>
      </div>

      <div className="form-actions">
        <button
          type="button"
          className="button button-primary"
          onClick={() => void handleRunMetaEval()}
          disabled={!canRunMetaEval || isSubmitting}
        >
          {isSubmitting ? "Running..." : "Run Meta Eval"}
        </button>
      </div>

      {!canRunMetaEval ? (
        <p className="form-error">Need at least two evaluated experiments before running meta eval.</p>
      ) : null}
      {status ? <p className="form-success">{status}</p> : null}
      {error ? <p className="form-error">{error}</p> : null}

      <div className="meta-eval-layout">
        <aside className="meta-eval-run-list">
          <h3>Past Runs</h3>
          {runs.length === 0 ? (
            <p className="meta-eval-empty">No meta eval runs yet.</p>
          ) : (
            runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                className={selectedRun?.run_id === run.run_id ? "meta-run-button meta-run-button-active" : "meta-run-button"}
                onClick={() => setSelectedRunId(run.run_id)}
              >
                <strong>{run.run_id}</strong>
                <small>{new Date(run.created_at).toLocaleString()}</small>
              </button>
            ))
          )}
        </aside>

        <div className="meta-eval-run-detail">
          {selectedRun ? (
            <>
              <div className="meta-summary-grid">
                <div className="meta-summary-card">
                  <span>Metrics Version</span>
                  <strong>
                    {selectedRun.old_metrics_version} {"->"} {selectedRun.candidate_metrics_version}
                  </strong>
                </div>
                <div className="meta-summary-card">
                  <span>Activation Status</span>
                  <strong>{selectedRun.activation_status}</strong>
                </div>
                <div className="meta-summary-card">
                  <span>Validation Decision</span>
                  <strong>{selectedRun.validation_decision.decision}</strong>
                </div>
                <div className="meta-summary-card">
                  <span>Held-out Validation Experiments</span>
                  <strong>{selectedRun.validation_experiment_ids.length}</strong>
                </div>
              </div>

              <div className="meta-section">
                <h3>Why This Change</h3>
                <p>{selectedRun.why_this_change}</p>
              </div>

              <div className="meta-section">
                <h3>Expected Improvement</h3>
                <p>{selectedRun.expected_improvement}</p>
              </div>

              <div className="meta-section">
                <h3>Metrics Diff Summary</h3>
                <p>{selectedRun.metrics_diff_summary}</p>
              </div>

              <div className="meta-section">
                <h3>Validation Summary</h3>
                <p>{selectedRun.validation_decision.reason}</p>
                {selectedRun.validation_experiment_ids.length > 0 ? (
                  <div className="meta-pill-row">
                    {selectedRun.validation_experiment_ids.map((experimentId) => (
                      <span key={experimentId} className="meta-chip">
                        {experimentId}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="meta-eval-empty">No held-out validation experiments were available.</p>
                )}
              </div>

              <div className="meta-section">
                <h3>Metric Actions</h3>
                {selectedRun.metric_actions.length === 0 ? (
                  <p className="meta-eval-empty">No metric actions found.</p>
                ) : (
                  <div className="meta-list">
                    {selectedRun.metric_actions.map((action, index) => (
                      <article key={`${action.metric_name}-${index}`} className="meta-list-item">
                        <header>
                          <strong>
                            {action.action.toUpperCase()} - {action.metric_name}
                          </strong>
                          {action.metric_id ? <small>{action.metric_id}</small> : null}
                        </header>
                        <p>{action.rationale}</p>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div className="meta-section">
                <h3>Validation Results</h3>
                {selectedRun.validation_decision.experiment_results.length === 0 ? (
                  <p className="meta-eval-empty">No held-out comparison results found.</p>
                ) : (
                  <div className="meta-list">
                    {selectedRun.validation_decision.experiment_results.map((result) => (
                      <article key={result.experiment_id} className="meta-list-item">
                        <header>
                          <strong>{result.experiment_id}</strong>
                          <small>Winner: {result.winner}</small>
                        </header>
                        <p>{result.reason}</p>
                        <p>
                          Old: {result.old_judgment.verdict} ({result.old_judgment.overall_score.toFixed(2)}) {" | "}
                          Candidate: {result.candidate_judgment.verdict} (
                          {result.candidate_judgment.overall_score.toFixed(2)})
                        </p>
                      </article>
                    ))}
                  </div>
                )}
              </div>

              <div className="meta-section">
                <h3>Correctness Analysis</h3>
                {selectedRun.correctness_analysis.length === 0 ? (
                  <p className="meta-eval-empty">No correctness analysis found.</p>
                ) : (
                  <div className="meta-list">
                    {selectedRun.correctness_analysis.map((analysis) => (
                      <article key={analysis.experiment_id} className="meta-list-item">
                        <header>
                          <strong>{analysis.experiment_id}</strong>
                        </header>
                        <p>Judge got right: {analysis.judge_got_right.length}</p>
                        <p>Judge got wrong: {analysis.judge_got_wrong.length}</p>
                        <p>Judge missed: {analysis.judge_missed.length}</p>
                      </article>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="meta-eval-empty">Run meta eval to view results.</p>
          )}
        </div>
      </div>
    </section>
  );
}
