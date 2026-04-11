Yes. Build it in this order.

---

## 0. Freeze the shape first

Before coding, fix these things on paper:

```text
3 agents
1 workflow
1 handoff format
1 case state schema
1 compliance rule set
1 evaluation rule set
1 storage model
```

Decide:

```text
Agent 1 = chat assessment
Agent 2 = voice resolution
Agent 3 = chat final notice
```

And decide exact outputs of each agent.

Example:

```text
Agent 1 output:
- updated case state
- handoff_to_agent_2

Agent 2 output:
- updated case state
- handoff_to_agent_3
- call outcome

Agent 3 output:
- final case disposition
```

Do this first. Otherwise you will keep rewriting everything.

---

## 1. Define the data model

Make the schemas before building agents.

Create these models:

```text
BorrowerCase
ConversationEvent
ExtractedFacts
CaseClassification
HandoffSummary
OfferPolicy
ComplianceFlags
PromptVersion
EvaluationRun
```

Minimum important fields:

```text
borrower_id
workflow_id
stage
case_type
amount_due
dpd
borrower_capacity
borrower_intent
hardship_flags
dispute_flags
approval_state
offers_made
next_allowed_actions
stop_contact_flag
```

Goal of this step:

```text
every component knows what it reads and what it writes
```

---

## 2. Build one agent locally first

Start with **Agent 1 only**.

Input:

```text
borrower message + borrower case state
```

Output:

```text
agent reply + extracted facts + updated case state
```

Do not think about Temporal yet.
Do not think about voice yet.

Just make this work locally in a loop:

```text
user message
   ->
Agent 1 prompt
   ->
reply
   ->
fact extraction
   ->
case state update
```

Run 3–4 fake borrower examples.

Goal:

```text
Agent 1 can verify, gather facts, and classify case
```

---

## 3. Add structured extraction after Agent 1

Now make the post-processing layer.

After every Agent 1 turn:

```text
transcript
   ->
extract structured facts
   ->
update case state
```

Store:

```text
identity_verified
employment_status
can_pay_now
borrower_reason
hardship_signal
dispute_signal
trust_signal
borrower_intent
```

This is important because:

```text
handoff should come from state
not from raw chat
```

Goal:

```text
Agent 1 is not just chatting
it is filling the case record
```

---

## 4. Build handoff from Agent 1 to Agent 2

Now build the summarizer.

Input:

```text
case state + recent events
```

Output:

```text
500-token max handoff summary
```

Format should be fixed.

Example:

```text
IDENTITY
ACCOUNT
CASE TYPE
BORROWER POSITION
PAY CAPACITY
FLAGS
OPEN ITEMS
NEXT ACTION
DO NOT REPEAT
```

Now test this:

```text
Agent 1 conversation
   ->
state updated
   ->
handoff generated
```

Goal:

```text
handoff exists and is small
```

Do token counting here.

---

## 5. Build Agent 2 locally as text first

Do **not** integrate phone yet.

Make Agent 2 first as a normal local text agent.

Input:

```text
handoff_from_agent_1 + case state
```

Output:

```text
resolution reply + updated offers + outcome
```

Test that Agent 2 does **not** ask repeated questions.

It should start like this:

```text
I see from the earlier conversation...
```

not like this:

```text
can you tell me about your case?
```

Goal:

```text
cross-agent continuity works before voice is added
```

---

## 6. Add resolution state tracking

Now capture what Agent 2 does.

Store:

```text
offers_presented
offers_rejected
offers_accepted
borrower_objections
commitment_made
promise_to_pay_amount
promise_to_pay_date
approval_needed
approval_status
call_outcome
```

This step matters because Agent 3 will depend on this.

Goal:

```text
Agent 2 updates case state in a way Agent 3 can use
```

---

## 7. Build Agent 2 to Agent 3 handoff

Now make second handoff.

Input:

```text
case state + Agent 2 interaction result
```

Output:

```text
500-token max summary for Agent 3
```

This summary must include:

```text
what was offered
what was rejected
what borrower said
what deadline exists
what next action is allowed
```

Goal:

```text
Agent 3 can continue from voice outcome
```

---

## 8. Build Agent 3 locally

Now make Agent 3 as a chat/text agent.

Input:

```text
handoff_from_agent_2 + case state
```

Output:

```text
final written notice or final documented next step
```

Test cases:

```text
1. no deal
2. hardship
3. dispute
4. promise to pay
5. special approval completed
```

Goal:

```text
Agent 3 feels like continuation, not restart
```

---

## 9. Run full pipeline locally without Temporal

Now connect all 3 agents in one Python script.

Flow:

```text
start case
   ->
Agent 1
   ->
handoff
   ->
Agent 2
   ->
handoff
   ->
Agent 3
```

Still no Temporal.
Still no real voice.

Use fake borrower inputs.

Goal:

```text
full business flow works end-to-end on local machine
```

This is the first real milestone.

---

## 10. Add persistent storage

Now replace in-memory state with DB.

Use simple DB first:

```text
SQLite or Postgres
```

Store:

```text
cases
events
facts
handoffs
prompt_versions
evaluations
```

Goal:

```text
workflow can stop and resume
audit trail exists
```

---

## 11. Add compliance guards

Before adding Temporal, put rule checks in place.

Make deterministic checks first:

```text
AI disclosure present
recording disclosure present
no full account number
offer within policy
stop contact honored
hardship not pressured
```

Then optional LLM judge for softer checks.

Run every agent output through compliance.

Goal:

```text
bad output is blocked early
```

---

## 12. Integrate real voice for Agent 2

Now add phone/call layer.

Do not redesign Agent 2.
Wrap the existing Agent 2 logic.

Flow:

```text
voice provider
   ->
speech/text transcript
   ->
Agent 2 logic
   ->
spoken response
```

Keep it thin.

Goal:

```text
same Agent 2 brain
new input/output channel
```

Very important:

```text
do not build voice-specific business logic
keep business logic separate
```

---

## 13. Run chat -> voice -> chat locally

Now test real modality shift.

Flow:

```text
Agent 1 chat
   ->
generate handoff
   ->
Agent 2 voice call
   ->
generate handoff
   ->
Agent 3 chat
```

Goal:

```text
seamless cross-modal continuity is real
```

This is your second major milestone.

---

## 14. Put the pipeline into Temporal

Now move the already-working flow into Temporal.

Do not start Temporal at the beginning.
Wrap working pieces into activities.

Suggested split:

```text
Workflow:
- start_assessment
- maybe_retry_assessment
- generate_handoff_1
- start_resolution_call
- generate_handoff_2
- start_final_notice
- close_case
```

Activities:

```text
run_agent_1
extract_facts
generate_handoff
run_agent_2
run_agent_3
save_case_state
check_compliance
send_message
place_call
```

Goal:

```text
Temporal orchestrates
agents do the work
```

---

## 15. Add retries, timers, and branching in Temporal

Now implement the real workflow rules.

Example:

```text
if no response in Agent 1
   ->
retry up to 3 times

if Agent 2 gets deal
   ->
exit

if Agent 2 no deal
   ->
wait
   ->
Agent 3

if stop_contact_flag
   ->
exit and mark
```

Goal:

```text
workflow logic is real, not just straight-line script
```

---

## 16. Build the simulation harness

Now make fake borrowers.

Create persona set:

```text
cooperative
angry
hardship
student
dispute
approval exception
confused
silent / no response
```

Run:

```text
borrower simulator
   ->
full 3-agent workflow
   ->
scores + logs + cost
```

Goal:

```text
system can be tested repeatedly without humans
```

---

## 17. Add prompt versioning

Now make agent prompts versioned.

Store:

```text
agent_name
prompt_version
prompt_text
created_at
status
parent_version
```

Goal:

```text
every run is linked to exact prompt version
```

---

## 18. Build the self-learning loop

Now add improvement loop.

Flow:

```text
current prompt
   ->
propose mutation
   ->
run benchmark conversations
   ->
score
   ->
check compliance
   ->
accept or reject
```

Keep mutation simple.

Examples:

```text
change wording
reorder instructions
add explicit hardship rule
add stronger dispute handling
tighten identity check
```

Goal:

```text
prompt changes are measured, not guessed
```

---

## 19. Add meta-evaluation

Now build evaluator-improves-evaluator.

Flow:

```text
evaluation results
   ->
inspect for blind spots
   ->
find bad metric / weak checker
   ->
patch evaluator
   ->
rerun benchmark
```

Example:

```text
old evaluator rewarded "deal closed"
but missed hardship mishandling

meta-layer catches this
adds hardship penalty
reruns results
some prompt versions now fail
```

Goal:

```text
one real example of evaluation system correcting itself
```

---

## 20. Add rollback

Now make it possible to revert.

Simple model:

```text
active_prompt_version pointer per agent
```

If new version underperforms:

```text
switch pointer back
```

Goal:

```text
rollback is real and demoable
```

---

## 21. Add cost tracking

Now track LLM spend.

Store per run:

```text
model
tokens_in
tokens_out
estimated_cost
purpose:
- simulation
- evaluation
- prompt_generation
```

Goal:

```text
prove total loop cost < $20
```

---

## 22. Docker Compose everything

Now package:

```text
app
temporal
temporal worker
db
voice/mock service if needed
```

Goal:

```text
fresh machine
docker compose up
system runs
```

---

## 23. Generate evidence artifacts

Now produce submission outputs.

Need:

```text
raw transcripts
raw scores
CSV/JSON
prompt history
evaluation report
cost breakdown
demo audio
technical writeup
decision journal
```

Goal:

```text
project is not just working
it is inspectable and reproducible
```

---

## 24. Final rehearsal

Now test like an interviewer.

Be able to explain:

```text
why this handoff design
why this storage model
why these metrics
why this adoption rule
where compliance is enforced
how rollback works
how token cap is enforced
where meta-eval happened
```

If you cannot explain one box clearly:

```text
you are not done
```

---

# Best practical phase grouping

If you want the shortest version:

## Phase 1 — local business logic

```text
build Agent 1
build extraction
build handoff 1
build Agent 2 as text
build handoff 2
build Agent 3
run full pipeline locally
```

## Phase 2 — production shape

```text
add DB
add compliance
add real voice
add Temporal
add retries and branching
```

## Phase 3 — intelligence layer

```text
build simulator
build evaluation
build prompt versioning
build self-learning
build meta-eval
build rollback
build cost tracking
```

## Phase 4 — submission layer

```text
docker compose
report
raw data
README
demo
decision journal
```

---

# Super short implementation order

```text
1. schemas
2. Agent 1
3. extraction
4. handoff 1
5. Agent 2 as text
6. resolution state
7. handoff 2
8. Agent 3
9. local end-to-end run
10. DB
11. compliance
12. voice integration
13. local cross-modal run
14. Temporal orchestration
15. retries / branching
16. simulation harness
17. prompt versioning
18. self-learning
19. meta-eval
20. rollback
21. cost tracking
22. Docker Compose
23. report + artifacts
```

Next, I can convert this into a **day-by-day 4-day build schedule**.
