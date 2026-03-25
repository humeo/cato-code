# Claude Agent SDK Native Capabilities vs CatoCode-Owned Responsibilities

## Summary

This document defines a thinner boundary for CatoCode.

The core position is:

- Claude Code / Claude Agent SDK provides all agentic capabilities.
- CatoCode does not own the workflow logic, paper method, proof model, or execution strategy.
- CatoCode acts as the control plane around Claude Code for GitHub-driven, multi-repo, multi-session operation.

In short:

`Claude Code is the agent runtime. CatoCode is the dispatcher, router, and context broker.`

## Design Decision

The product should be designed around this split:

### Claude Code owns

- tool use
- agent loop
- context management inside a session
- workflow execution
- skills, commands, and project memory
- the `issue location -> issue solve` method
- proof generation
- approval requests through SDK-native primitives
- fallback reasoning
- final natural-language outputs

### CatoCode owns

- GitHub webhook ingestion
- repo selection
- session selection, resume, and fork routing
- event-to-skill or event-to-command routing
- minimal context packaging for the runtime
- activity metadata, logs, and cost tracking
- external writeback integration points
- multi-repo and multi-tenant coordination

This means CatoCode should not build a parallel workflow engine.

## Why This Boundary Matters

If Claude Code already provides the agent runtime, then CatoCode should stay small.

Otherwise the system drifts into an awkward middle ground:

- Claude Code is present but underused
- host-side code starts reconstructing workflow semantics that belong in the runtime
- prompt assembly becomes a substitute for native skills and commands
- approval and skill invocation get split across two systems
- session continuity exists, but the host still behaves as if it owns the task logic

The cleaner architecture is to let Claude Code remain the intelligence and execution layer, while CatoCode becomes the product shell around it.

## What "CatoCode Is Thin" Actually Means

CatoCode is not a second agent.

It is a control plane that answers these questions:

- which GitHub event arrived
- which repository does it belong to
- which Claude session should handle it
- should this be a new session, a resume, or a fork
- which top-level skill or command should Claude start from
- what minimal context should be attached
- where should outputs, logs, and costs be stored
- where should the final result be delivered

It should not answer these questions:

- how should the issue be analyzed
- whether `issue_location` should search files in a certain way
- what counts as a valid solve plan
- what proof structure should be generated inside the run
- how the internal workflow should branch step by step

Those belong inside Claude Code skills, commands, memory, and runtime behavior.

## Claude Code Native Capabilities Relevant to This Design

The official SDK already provides the primitives needed for this thinner architecture.

### Agent loop and built-in tools

Anthropic documents the SDK as providing the same tools, agent loop, and context management that power Claude Code.

Implication:

- CatoCode should not build its own generic task execution loop
- task intelligence should stay inside Claude Code

Source:

- https://platform.claude.com/docs/en/agent-sdk/overview

### Skills, commands, and memory

The SDK supports project-backed skills, slash commands, and `CLAUDE.md` memory.

Implication:

- event-specific workflows should start from native skills or commands
- long-lived project instructions should live in Claude-native config surfaces
- the host should avoid manually flattening these into prompts as the long-term model

Sources:

- https://platform.claude.com/docs/en/agent-sdk/overview
- https://platform.claude.com/docs/en/agent-sdk/skills

### Sessions

The SDK supports session persistence, continuation, resume, and fork behavior.

Implication:

- CatoCode should treat `session_id` as a first-class routing handle
- approval or follow-up events should usually resume or fork an existing Claude session rather than rebuild state host-side

Source:

- https://platform.claude.com/docs/en/agent-sdk/sessions

### Permissions, approvals, and hooks

The SDK exposes permission handling, user-input primitives, and hooks.

Implication:

- if approval exists, it should be mediated through Claude-native runtime behavior
- CatoCode may relay or surface approval state, but it should not replace the runtime's approval model with a parallel host-side one

Sources:

- https://platform.claude.com/docs/en/agent-sdk/permissions
- https://platform.claude.com/docs/en/agent-sdk/user-input
- https://platform.claude.com/docs/en/agent-sdk/hooks

### MCP and subagents

The SDK supports MCP and subagent delegation.

Implication:

- external capabilities and internal decomposition should be expressed through Claude-native extension points
- CatoCode should not invent separate mechanisms unless a hard product requirement forces it

Sources:

- https://platform.claude.com/docs/en/agent-sdk/mcp
- https://platform.claude.com/docs/en/agent-sdk/subagents

## Where the Paper Method Lives

Under this thinner boundary, the paper method does not live in CatoCode.

It lives in Claude Code's runtime layer, likely through:

- a top-level skill or command for the event type
- lower-level skills such as `issue_location` and `issue_solve`
- project memory and repo-specific instructions
- Claude's own tool use and chain of reasoning

That means the right statement is not:

- "CatoCode implements the paper"

It is:

- "CatoCode routes events into Claude Code, and Claude Code implements the paper method inside the selected repo and session context"

## Recommended Workflow Model

The workflow should be event-driven, but the workflow intelligence should stay in Claude Code.

### Event routing model

Example shape:

- `issue_opened` -> start session with `triage_issue`
- `issue_mention` -> resume or start session with `respond_mention`
- `pr_opened` -> start session with `review_pr`
- `approval_received` -> resume existing session with `fix_issue_approved`

### Skill layering model

Within Claude Code:

- top-level skill handles the event class
- top-level skill can invoke lower-level skills such as:
  - `issue_location`
  - `issue_solve`
  - `proof_check`
  - `codebase_graph`

This preserves the method structure without forcing CatoCode to own phase state.

### What CatoCode does during this workflow

CatoCode only needs to:

- map event to repo
- map event to session
- choose the entry skill or command
- package the event payload and repo context
- persist logs and result metadata
- deliver the Claude-produced result outward

## What CatoCode Should Not Own

Given this design, CatoCode should not own:

- a host-side `location -> solve -> proof` state machine
- a separate proof engine
- a second approval policy engine that competes with Claude runtime behavior
- detailed branch logic for how the agent should think through the task
- a prompt-rendering architecture as the long-term substitute for native skills

If machine-readable outputs are needed, CatoCode should ask Claude Code to emit structured artifacts, not recreate the reasoning flow outside the runtime.

## Current Codebase Evidence of Boundary Drift

The current codebase still shows signs of a thicker host architecture.

### 1. Skill files are being flattened into prompts

`skill_renderer.py` reads `SKILL.md` and renders prompts host-side.

See:

- `src/catocode/skill_renderer.py`

This is useful as a bootstrap path, but it is not the clean end state if Claude-native skills are the intended abstraction.

### 2. The dispatcher still behaves like a partial workflow owner

`dispatcher.py` currently does more than routing:

- repo reset
- indexing
- context preloading
- prompt assembly
- session resume routing
- runner retries

Some of this belongs to a thin control plane. Some of it suggests the host is still partly shaping task execution.

See:

- `src/catocode/dispatcher.py`

### 3. Runtime policy is currently configured in a way that assumes autonomy

The SDK runner sets `permission_mode="bypassPermissions"` and disables `AskUserQuestion`.

See:

- `src/catocode/container/scripts/run_activity.py`
- `src/catocode/templates/user_claude_md.py`
- `tests/test_integration.py`

This does not necessarily violate the thin-host model, but it does show that runtime policy is currently opinionated and not yet aligned with a future approval-relay model if one is needed.

## What This Means for the Next Refactor

If we follow this design, the refactor direction becomes clearer.

### Keep

- webhook ingestion
- repo registry and repo readiness
- activity persistence
- session tracking
- cost tracking
- log streaming
- GitHub transport and writeback integration

### Reduce

- host-side prompt construction as the primary execution model
- host-side workflow shaping beyond routing and context handoff
- bespoke abstractions that duplicate native Claude skill/session behavior

### Move into Claude Code

- event-specific workflow behavior
- paper-method execution
- skill composition
- internal task decomposition
- phase-level task logic
- proof generation and task-specific reasoning

## Data Model Implications

If CatoCode is thin, then the core product entities are:

- `repo`
- `event`
- `activity`
- `session`
- `routing_rule`
- `writeback_target`

Not:

- `location_state`
- `solve_state`
- `proof_state`

Those internal states should remain inside Claude Code's runtime context and outputs unless there is a strong product need to expose them.

## Non-Goals

- This document does not define the exact shape of every skill.
- This document does not remove the current prompt-rendering path yet.
- This document does not require that every approval be implemented immediately.
- This document does not argue against observability. It argues that observability should track Claude-run activities rather than replace them with host-owned workflow semantics.

## Final Position

The right framing is:

- Claude Code is the complete agent system.
- CatoCode is the system that decides where Claude should run, with which repo, in which session, from which entrypoint, and where its outputs should go.

Or more compactly:

`CatoCode should dispatch. Claude Code should think, act, and decide.`
