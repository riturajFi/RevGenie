export type MetaEvalLatestPair = {
  before_experiment_id: string | null;
  after_experiment_id: string | null;
  total_evaluated_experiments: number;
};

export type MetaEvalEvidenceBundle = {
  transcript_evidence: string[];
  judgment_evidence: string[];
  policy_evidence: string[];
};

export type MetaEvalMetricDefinition = {
  metric_id: string;
  name: string;
  description: string;
  score_type: string;
  policy_references: string[];
};

export type MetaEvalMetricAction = {
  action: "keep" | "delete" | "add" | "rewrite";
  metric_id: string | null;
  metric_name: string;
  rationale: string;
  policy_references: string[];
  proposed_metric: MetaEvalMetricDefinition | null;
  evidence: MetaEvalEvidenceBundle;
};

export type MetaEvalCorrectnessAnalysis = {
  experiment_id: string;
  judge_got_right: string[];
  judge_got_wrong: string[];
  judge_missed: string[];
  evidence: MetaEvalEvidenceBundle;
};

export type MetaEvalRunRecord = {
  run_id: string;
  created_at: string;
  before_experiment_id: string;
  after_experiment_id: string;
  validation_experiment_ids: string[];
  metrics_key: string;
  lender_id: string | null;
  old_metrics_version: string;
  candidate_metrics_version: string;
  correctness_analysis: MetaEvalCorrectnessAnalysis[];
  metric_actions: MetaEvalMetricAction[];
  candidate_metrics: MetaEvalMetricDefinition[];
  metrics_diff_summary: string;
  why_this_change: string;
  expected_improvement: string;
  validation_decision: {
    decision: string;
    reason: string;
    old_expectation_matches: number;
    candidate_expectation_matches: number;
    total_expectation_checks: number;
    experiment_results: {
      experiment_id: string;
      scenario_id: string | null;
      purpose: string | null;
      expected_verdict: string | null;
      expected_fail_metrics: string[];
      expected_pass_metrics: string[];
      old_matched_checks: number;
      candidate_matched_checks: number;
      total_checks: number;
      winner: string;
      reason: string;
      old_judgment: {
        experiment_id: string;
        overall_score: number;
        verdict: string;
      };
      candidate_judgment: {
        experiment_id: string;
        overall_score: number;
        verdict: string;
      };
    }[];
  };
  activation_status: string;
};

export type MetaEvalRunRequest = {
  metrics_key: string;
  lender_id: string;
  force_activate: boolean;
};
