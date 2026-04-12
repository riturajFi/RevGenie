# Standalone LLM Loop v0 Design

This file explains the standalone `experiments/llm_v0` module so another agent can continue work with minimal codebase exploration.

## Scope

This folder is intentionally not integrated with the main app.

Goal:

- keep a separate bare-minimum implementation of the purely LLM-based self-improvement loops
- store prompt versions and evaluator versions as simple files
- run Loop 1 and Loop 2 with minimal moving parts

This is a prototype workspace, not production architecture.

## What exists here

Files:

- `api.py`: init API and top-level module API
- `engine.py`: thin CLI wrapper
- `models.py`: Pydantic models
- `store.py`: file storage helpers
- `logs.py`: log collector
- `tokens.py`: prompt token calculator
- `versioning.py`: linked-list version managers
- `runtime.py`: shared LLM calls and experiment execution helpers
- `loop1.py`: Loop 1 runner
- `loop2.py`: Loop 2 runner
- `README.md`: quick usage notes
- `sample/scenarios.json`: sample Loop 1 input
- `sample/audits.json`: sample Loop 2 input
- `data/`: version files, active pointers, logs, history, and stored run outputs
- `prompt_store/`: actual prompt text files

## Core idea

Everything is text-first and LLM-driven.

There is no extra scoring service, no optimizer, no workflow engine, and no app integration here.

The design is:

1. generate full 3-agent transcripts
2. merge them into one big transcript
3. evaluate with evaluator LLM
4. generate diff
5. append diff to old prompt/evaluator text
6. rerun
7. compare old vs new
8. adopt or reject

## Folder contract

Another agent should treat this folder as a self-contained experiment package.

Important boundary:

- do not assume anything in `app/` is required for this module to work
- do not integrate with the main application unless explicitly asked
- if extending this folder, keep changes local to `experiments/llm_v0`

## Stored data layout

Under `data/`:

- `prompts/prompt_v1.json`, `prompt_v2.json`, ...
- `evaluators/evaluator_v1.json`, `evaluator_v2.json`, ...
- `state.json`
- `runs/*.json`
- `audit_runs/*.json`
- `logs/events.jsonl`
- `history/prompt_history.jsonl`
- `history/evaluator_history.jsonl`
- `token_counts/token_counts.jsonl`
- `../prompt_store/prompt_v1.txt`, `prompt_v2.txt`, ...

`state.json` tracks active versions and counters:

```json
{
  "active_prompt_version": "prompt_v1",
  "active_evaluator_version": "evaluator_v1",
  "next_prompt_number": 2,
  "next_evaluator_number": 2,
  "next_log_sequence": 1
}
```

Rollback trims the tail of the adopted chain.

Example:

```text
prompt_v1 -> prompt_v2 -> prompt_v3
revert prompt_v3
remaining stored chain:
prompt_v1 -> prompt_v2
```

## Version model

Prompt and evaluator changes are now managed separately by linked-list managers:

- `PromptVersionManager`
- `EvaluatorVersionManager`

Each stored adopted version has:

- `version_id`
- `kind`
- `text`
- `diff`
- `previous_version_id`
- `next_version_id`
- `created_at`

Candidate versions are created as temporary files first.

If adopted:

- parent `next_version_id` points to the candidate
- active state moves to the candidate

If rejected:

- candidate file is deleted
- rejection survives only in the history jsonl file

There is no patch engine. Apply strategy is still intentionally naive:

```text
new_version_text = old_version_text + "\n\n" + diff
```

In code this happens in `ExperimentRuntime.apply_diff()`.

For prompts specifically, the actual text also lives in `prompt_store/` and is wrapped by a `Prompt` class.

## Transcript model

The run produces a `TranscriptBundle` with:

- `agent_1_chat`
- `agent_2_voice`
- `agent_3_chat`
- `merged_transcript`

`merged_transcript` is built in `build_merged_transcript()` and is the main thing passed into the evaluator.

The collector system is simulated by one LLM call that returns all three transcripts.

This is intentionally simple and fake:

- Agent 1, Agent 2, and Agent 3 are not independent runtimes here
- Agent 2 voice is just text representing a voice transcript

## Scenario model

Input scenarios and audits use the same `Scenario` model.

Fields:

- `scenario_id`
- `title`
- `original_scenario`
- `task_requirements`
- `compliance_rules`
- `output_format`
- `expected_truths`
- `audit_expectations`

Loop 1 mostly uses:

- original scenario
- task requirements
- compliance rules
- output format

Loop 2 additionally uses:

- expected truths
- audit expectations

## Loop 1 design

Purpose:

- improve the collector prompt

Flow:

1. load active prompt version from `state.json`
2. load active evaluator version from `state.json`
3. run all scenarios with current prompt
4. store transcripts and evaluator outputs
5. choose one failing or weakest run
6. ask LLM for prompt diff using:
   - current prompt
   - full bad transcript
   - judge feedback
7. create `prompt_v{n+1}`
8. rerun same scenarios with candidate prompt
9. ask comparison LLM whether to adopt or reject
10. if adopt, set new prompt active
11. if reject, mark candidate rejected

Code path:

- `Loop1Runner.run()`

Important helpers:

- `ExperimentRuntime.run_single_experiment()`
- `ExperimentRuntime.generate_transcript()`
- `ExperimentRuntime.evaluate_transcript()`
- `ExperimentRuntime.propose_prompt_diff()`
- `ExperimentRuntime.compare_prompt_versions()`

Adoption rule right now:

- LLM-based comparison
- prefers compliance first, continuity second, resolution third
- rejects if evidence is unclear

There is no statistical testing yet.

## Loop 2 design

Purpose:

- improve the evaluator prompt

Flow:

1. load active prompt version
2. load active evaluator version
3. run audit scenarios with old evaluator
4. store old evaluator outputs
5. ask meta-LLM to inspect:
   - transcripts
   - evaluator outputs
   - expected truths
   - audit expectations
6. generate evaluator diff
7. create `evaluator_v{n+1}`
8. rerun evaluator on the same audits
9. ask comparison LLM whether candidate evaluator is better
10. adopt or reject

Code path:

- `Loop2Runner.run()`

Important helpers:

- `ExperimentRuntime.propose_evaluator_diff()`
- `ExperimentRuntime.compare_evaluator_versions()`

Adoption rule right now:

- LLM decides whether the candidate catches real flaws more reliably

Again, no extra scoring layer exists yet.

## CLI contract

Current commands:

```bash
.venv/bin/python -m experiments.llm_v0.engine init
.venv/bin/python -m experiments.llm_v0.engine state
.venv/bin/python -m experiments.llm_v0.engine loop1
.venv/bin/python -m experiments.llm_v0.engine loop2
.venv/bin/python -m experiments.llm_v0.engine log --source manual --message "hello"
.venv/bin/python -m experiments.llm_v0.engine revert prompt
.venv/bin/python -m experiments.llm_v0.engine revert evaluator
```

Notes:

- use `.venv/bin/python` in this repo, not plain `python`
- `init` ensures storage, version roots, and counters exist
- `log` can be called from any folder and still writes into this module's storage
- `revert` trims the linked-list tail or reverts to a supplied version id
- if the caller is outside the repo root, use the absolute path to `engine.py`

## LLM call design

All structured LLM calls go through:

- `ExperimentRuntime._structured_call()`

It uses:

- `ChatPromptTemplate`
- `ChatOpenAI`
- `with_structured_output(schema)`

Environment:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` default: `gpt-4o-mini`
- `OPENAI_JUDGE_MODEL` default: same as `OPENAI_MODEL`

There is no cost tracking yet.

## Run record design

Each run stores:

- run id
- loop name
- full scenario payload
- prompt version id
- evaluator version id
- full transcript bundle
- evaluator result
- timestamp

Loop 1 run files go into:

- `data/runs/`

Loop 2 run files go into:

- `data/audit_runs/`

## Log collector

There is now a dedicated `LogCollector`.

Purpose:

- append ordered logs from anywhere
- always write into `experiments/llm_v0/data/logs/events.jsonl`

Ordering rule:

- `state.json` holds `next_log_sequence`
- every new log increments that counter
- logs are append-only and sequence-based

This means callers do not depend on their current working directory.

## Prompt token calculator

There is now a dedicated `PromptTokenCalculator`.

Purpose:

- call OpenAI's `responses/input_tokens` endpoint
- return prompt token counts for any input string
- store those counts as a metrics table under this module

Main API:

- `ExperimentApi.calculate_prompt_tokens(input_text: str, model: str = "gpt-5")`

Storage:

- `data/token_counts/token_counts.jsonl`

The calculator also writes a normal log event through the shared logger.

## Prompt class

There is now a dedicated `Prompt` class in `prompt.py`.

It contains:

- `version_id`
- `text`
- `file_path`

It also has:

- `update(diff, parent_version_id=None)`
- `save()`

The main API exposes:

- `ExperimentApi.get_active_prompt()`

That is the intended way for another agent or a future main agent to fetch the current prompt object.

## Init API

There is now a dedicated `ExperimentApi`.

Main methods:

- `init_experiment()`
- `get_state()`
- `collect_log()`
- `calculate_prompt_tokens()`
- `run_loop1()`
- `run_loop2()`
- `revert_loop1()`
- `revert_loop2()`

This is the main entrypoint another agent should use.

## Current simplifications

These are deliberate, not oversights:

1. No app integration.
2. No Temporal.
3. No real separate agents.
4. No real voice system.
5. No token budget enforcement.
6. No cost accounting.
7. No batching.
8. No statistical significance logic.
9. No diff parser beyond append-only text.
10. No database, just JSON files.
11. No concurrency protection for log writes or version writes.

This is intentionally the shortest workable version of the idea.

## Safe ways to extend this

If another agent continues work here, the lowest-risk next steps are:

1. Add richer sample scenarios and audit cases.
2. Add cost tracking per LLM call.
3. Add deterministic run metadata like seed/config fields.
4. Add CSV or aggregated reporting on top of stored JSON runs.
5. Replace append-only diff application with a slightly better prompt rewrite step.
6. Add stronger adoption rules without integrating the app.

## Things not to do unless explicitly asked

1. Do not wire this into `app/`.
2. Do not refactor the whole repo around this module.
3. Do not introduce a database layer just for this folder.
4. Do not split this into many services.
5. Do not over-abstract the current simple file model.

## Quick orientation for a new agent

If you need to continue from here, read in this order:

1. `experiments/llm_v0/design.md`
2. `experiments/llm_v0/README.md`
3. `experiments/llm_v0/api.py`
4. `experiments/llm_v0/versioning.py`
5. `experiments/llm_v0/loop1.py`
6. `experiments/llm_v0/loop2.py`
7. `experiments/llm_v0/runtime.py`
8. `experiments/llm_v0/sample/*.json`

That is enough to understand the current standalone design without exploring the main repo.
