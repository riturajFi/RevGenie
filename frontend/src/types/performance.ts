export type PerformancePromptChange = {
  agent_id: string;
  old_version_id: string;
  new_version_id: string;
  activation_status: string;
  diff_summary: string;
};

export type PerformanceMetricUsed = {
  metric_id: string;
  metric_name: string;
  score: number;
};

export type EvalPerformancePoint = {
  iteration: number;
  experiment_id: string;
  workflow_id: string | null;
  scenario_id: string;
  overall_score: number;
  verdict: string;
  evaluated_at: string;
  prompt_versions: Record<string, string>;
  metrics_used: PerformanceMetricUsed[];
  prompt_change: PerformancePromptChange | null;
};

export type EvalPerformanceDataset = {
  points: EvalPerformancePoint[];
  available_scenarios: string[];
};
