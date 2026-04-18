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

function getMedianScore(scores: number[]): number {
  if (scores.length === 0) {
    return 0;
  }
  const sorted = [...scores].sort((a, b) => a - b);
  const midpoint = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return (sorted[midpoint - 1] + sorted[midpoint]) / 2;
  }
  return sorted[midpoint];
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
  const scores = points.map((point) => point.overall_score);
  const meanScore = scores.reduce((sum, score) => sum + score, 0) / scores.length;
  const medianScore = getMedianScore(scores);
  const meanY = topPadding + chartHeight - (Math.max(0, Math.min(meanScore, maxScore)) / maxScore) * chartHeight;
  const medianY = topPadding + chartHeight - (Math.max(0, Math.min(medianScore, maxScore)) / maxScore) * chartHeight;

  return (
    <div className="performance-layout">
      <div className="performance-legend">
        {Object.entries(scenarioColors).map(([scenario, color]) => (
          <div className="legend-item" key={scenario}>
            <span className="legend-swatch" style={{ backgroundColor: color }} />
            <span>{scenario}</span>
          </div>
        ))}
        <div className="legend-item">
          <span className="legend-line-swatch mean-line" />
          <span>Mean</span>
        </div>
        <div className="legend-item">
          <span className="legend-line-swatch median-line" />
          <span>Median</span>
        </div>
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

          <g>
            <line x1={0} x2={svgWidth} y1={meanY} y2={meanY} className="chart-reference-line mean-line" />
            <text x={svgWidth - 8} y={meanY - 6} textAnchor="end" className="chart-reference-label mean-line-label">
              Mean {meanScore.toFixed(2)}
            </text>
          </g>
          <g>
            <line x1={0} x2={svgWidth} y1={medianY} y2={medianY} className="chart-reference-line median-line" />
            <text x={svgWidth - 8} y={medianY - 6} textAnchor="end" className="chart-reference-label median-line-label">
              Median {medianScore.toFixed(2)}
            </text>
          </g>

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
          <div className="hover-metrics-used">
            <h5>Metrics Used</h5>
            {hoveredPoint.metrics_used.length === 0 ? (
              <p>No metric snapshot available.</p>
            ) : (
              hoveredPoint.metrics_used.map((metric) => (
                <p key={metric.metric_id}>
                  {metric.metric_name} ({metric.metric_id}): {metric.score.toFixed(2)}
                </p>
              ))
            )}
          </div>
          {hoveredPoint.prompt_change ? (
            <div className="hover-prompt-change">
              <h5>Prompt Change</h5>
              <p>
                {hoveredPoint.prompt_change.agent_id}: {hoveredPoint.prompt_change.old_version_id} {"->"}{" "}
                {hoveredPoint.prompt_change.new_version_id} ({hoveredPoint.prompt_change.activation_status})
              </p>
            </div>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}
