export type PromptDiffLine = {
  line_type: "add" | "remove" | "context";
  text: string;
};

export type PromptVersionEvolution = {
  version_id: string;
  parent_version_id: string | null;
  created_at: string;
  diff_summary: string | null;
  prompt_line_count: number;
  previous_version_id: string | null;
  diff_lines: PromptDiffLine[];
};

export type PromptEvolutionResponse = {
  agent_id: string;
  active_version_id: string;
  versions: PromptVersionEvolution[];
};

export type PromptEvolutionActivateResponse = {
  agent_id: string;
  active_version_id: string;
};
