"use client";

import { useMemo, useState } from "react";

import { EvalPerformancePoint } from "@/types/performance";

const PALETTE = ["#c6622a", "#2b7a78", "#d64f7d", "#6d8b3d", "#6a4cff", "#2e5aac", "#bf5b17", "#7a4a9f"];

function buildScenarioColors(scenarios: string[]): Record<string, string> {
  const sorted = [...scenarios].sort();
  return sorted.reduce<Record<string, string>>((acc, scenario, index) => {
    acc[scenario] = PALETTE[index % PALETTE.length];
    return acc;
  }, {});
}

type PerformanceBarChartProps = {
  points: EvalPerformancePoint[];
};

export function PerformanceBarChart({ points }: PerformanceBarChartProps) {
  const [hoveredExperimentId, setHoveredExperimentId] = useState<string | null>(null);
  const scenarioColors = useMemo(
    () => buildScenarioColors(Array.from(new Set(points.map((point) => point.scenario_id)))),
    [points]
  );
  const hoveredPoint =
    points.find((point) => point.experiment_id === hoveredExperimentId) ?? (points.length > 0 ? points[points.length - 1] : null);

  if (points.length === 0) {
    return <p className="performance-empty">No evaluation points available for this filter.</p>;
  }

  const barWidth = 36;
  const gap = 18;
  const chartHeight = 280;
  const topPadding = 16;
  const bottomPadding = 38;
  const maxScore = 10;
  const svgWidth = points.length * (barWidth + gap) + gap;
  const svgHeight = chartHeight + bottomPadding;

  return (
    <div className="performance-layout">
      <div className="performance-legend">
        {Object.entries(scenarioColors).map(([scenario, color]) => (
          <div className="legend-item" key={scenario}>
            <span className="legend-swatch" style={{ backgroundColor: color }} />
            <span>{scenario}</span>
          </div>
        ))}
      </div>

      <div className="performance-chart-wrap">
        <svg className="performance-chart" width={svgWidth} height={svgHeight} role="img" aria-label="Evaluation performance bar chart">
          {[0, 2, 4, 6, 8, 10].map((tick) => {
            const y = topPadding + chartHeight - (tick / maxScore) * chartHeight;
            return (
              <g key={tick}>
                <line x1={0} x2={svgWidth} y1={y} y2={y} className="chart-grid-line" />
                <text x={4} y={y - 4} className="chart-grid-label">
                  {tick}
                </text>
              </g>
            );
          })}

          {points.map((point, index) => {
            const x = gap + index * (barWidth + gap);
            const scoreHeight = (Math.max(0, Math.min(point.overall_score, maxScore)) / maxScore) * chartHeight;
            const y = topPadding + chartHeight - scoreHeight;
            const color = scenarioColors[point.scenario_id] ?? "#6a6a6a";
            const isActive = hoveredPoint?.experiment_id === point.experiment_id;

            return (
              <g
                key={point.experiment_id}
                onMouseEnter={() => setHoveredExperimentId(point.experiment_id)}
                onFocus={() => setHoveredExperimentId(point.experiment_id)}
              >
                <rect
                  x={x}
                  y={y}
                  width={barWidth}
                  height={scoreHeight}
                  rx={8}
                  fill={color}
                  opacity={isActive ? 1 : 0.86}
                  className="chart-bar"
                />
                <circle
                  cx={x + barWidth / 2}
                  cy={y}
                  r={isActive ? 6 : 4}
                  fill={isActive ? "#111" : "#fff"}
                  stroke={color}
                  strokeWidth={2}
                />
                <text x={x + barWidth / 2} y={svgHeight - 12} textAnchor="middle" className="chart-x-label">
                  {point.iteration}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {hoveredPoint ? (
        <article className="performance-hover-card">
          <header>
            <h4>Iteration {hoveredPoint.iteration}</h4>
            <strong>{hoveredPoint.overall_score.toFixed(2)} / 10</strong>
          </header>
          <p>Scenario: {hoveredPoint.scenario_id}</p>
          <p>Experiment: {hoveredPoint.experiment_id}</p>
          <p>Workflow: {hoveredPoint.workflow_id ?? "unknown"}</p>
          <p>Verdict: {hoveredPoint.verdict.toUpperCase()}</p>
          <p>Evaluated: {new Date(hoveredPoint.evaluated_at).toLocaleString()}</p>
          <div className="hover-prompt-versions">
            <h5>Prompt Versions</h5>
            {Object.keys(hoveredPoint.prompt_versions).length === 0 ? (
              <p>No prompt version snapshot available.</p>
            ) : (
              Object.entries(hoveredPoint.prompt_versions).map(([agent, version]) => (
                <p key={agent}>
                  {agent}: {version}
                </p>
              ))
            )}
          </div>
          {hoveredPoint.prompt_change ? (
            <div className="hover-prompt-change">
              <h5>Prompt Change</h5>
              <p>
                {hoveredPoint.prompt_change.agent_id}: {hoveredPoint.prompt_change.old_version_id} ->{" "}
                {hoveredPoint.prompt_change.new_version_id} ({hoveredPoint.prompt_change.activation_status})
              </p>
            </div>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
