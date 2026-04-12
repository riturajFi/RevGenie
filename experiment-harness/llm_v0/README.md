# LLM Loops v0

This folder is standalone on purpose. It is not wired into `app/`.

It implements the bare minimum version of the two loops you described:

- Loop 1: transcript -> evaluator LLM -> prompt diff -> rerun -> compare -> adopt or reject
- Loop 2: transcript + old evaluator outputs -> meta LLM -> evaluator diff -> rerun evaluator -> compare -> adopt or reject

## What it stores

- `data/prompts/prompt_v*.json`
- `data/evaluators/evaluator_v*.json`
- `data/state.json`
- `data/runs/*.json`
- `data/audit_runs/*.json`
- `data/logs/events.jsonl`
- `data/history/prompt_history.jsonl`
- `data/history/evaluator_history.jsonl`
- `data/token_counts/token_counts.jsonl`
- `prompt_store/prompt_v*.txt`

`state.json` tracks:

```json
{
  "active_prompt_version": "prompt_v1",
  "active_evaluator_version": "evaluator_v1",
  "next_prompt_number": 2,
  "next_evaluator_number": 2,
  "next_log_sequence": 1
}
```

Rollback trims the linked-list tail. Example:

```text
prompt_v1 -> prompt_v2 -> prompt_v3
revert from prompt_v3
stored chain becomes:
prompt_v1 -> prompt_v2
```

## How it works

Right now the whole thing is purely LLM-driven:

1. `Loop1Runner` and `Loop2Runner` are separate classes now.
2. A collector LLM generates:
   - `agent_1_chat`
   - `agent_2_voice`
   - `agent_3_chat`
3. The code merges those into one big transcript and stores it.
4. The evaluator LLM scores the run and suggests prompt changes.
5. A second LLM proposes a prompt diff.
6. The same scenarios are rerun with the candidate prompt.
7. A comparison LLM adopts or rejects the candidate.
8. Loop 2 does the same thing for the evaluator prompt.

The diff application is intentionally naive: the new version is just `old text + diff`.

Prompt and evaluator version chains are managed separately:

- Loop 1 changes the prompt chain
- Loop 2 changes the evaluator chain

Both are managed like linked lists with audit history files.

## API

Main entrypoint:

```python
from experiments.llm_v0 import ExperimentApi

api = ExperimentApi()
api.init_experiment()
active_prompt = api.get_active_prompt()
api.run_loop1("experiments/llm_v0/sample/scenarios.json")
api.run_loop2("experiments/llm_v0/sample/audits.json")
api.collect_log("manual", "hello from anywhere")
api.calculate_prompt_tokens("Tell me a joke.")
api.revert_loop1()
api.revert_loop2()
```

Shortcut log collector:

```python
from experiments.llm_v0 import collect_log

collect_log("manual", "hello from anywhere")
```

The log collector always writes into this module's storage, not the caller's current directory.

Prompt object:

```python
from experiments.llm_v0 import ExperimentHarness

experiment_harness = ExperimentHarness()
prompt = experiment_harness.get_active_prompt()
print(prompt.version_id)
print(prompt.text)
```

Prompt files live in `prompt_store/`. Prompt metadata still lives in `data/prompts/`.

Prompt token calculator:

```python
from experiments.llm_v0 import ExperimentHarness

experiment_harness = ExperimentHarness()
token_record = experiment_harness.calculate_prompt_tokens("Tell me a joke.")
print(token_record.input_tokens)
```

This uses the OpenAI `responses/input_tokens` endpoint and stores the result in `data/token_counts/token_counts.jsonl`.

## Commands

Initialize or inspect state:

```bash
.venv/bin/python -m experiments.llm_v0.engine init
.venv/bin/python -m experiments.llm_v0.engine state
```

Run Loop 1:

```bash
.venv/bin/python -m experiments.llm_v0.engine loop1
```

Run Loop 2:

```bash
.venv/bin/python -m experiments.llm_v0.engine loop2
```

Collect a log from any repo folder:

```bash
.venv/bin/python -m experiments.llm_v0.engine log --source manual --message "test log"
```

If your current folder is not the repo root, call the CLI by absolute file path instead:

```bash
.venv/bin/python /home/riturajtripathy/Documents/_Code/personal_projects/Take\ Home\ Tasks/Riverline/RevGenie/experiments/llm_v0/engine.py log --source manual --message "test log"
```

Calculate prompt tokens:

```bash
.venv/bin/python -m experiments.llm_v0.engine tokens --input "Tell me a joke." --model gpt-5
```

Revert prompt or evaluator chain:

```bash
.venv/bin/python -m experiments.llm_v0.engine revert prompt
.venv/bin/python -m experiments.llm_v0.engine revert evaluator
```

## Environment

It uses the repo's existing LangChain/OpenAI setup.

- `OPENAI_API_KEY` must be set
- `OPENAI_MODEL` defaults to `gpt-4o-mini`
- `OPENAI_JUDGE_MODEL` defaults to `OPENAI_MODEL`
