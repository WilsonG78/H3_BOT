# H3 Bot implementation plan

## Current direction

Start with battle modeling and a VCMI state/action adapter for an external
Python application. Earlier proposals to start with adventure-map behavior or
implement decision logic inside a VCMI AI module have been superseded.
See [README](../README.md) for the current directory layout and
[battle prototype](BATTLE_PROTOTYPE.md) for the first scenario.

## Goal and architecture

Build a Heroes III agent whose actions are visible in the VCMI client and whose
observations, decisions, failures, and results can be analyzed.

- VCMI owns game rules and state; its server validates and applies actions.
- A thin C++ adapter extracts state and executes requests without strategy.
- A versioned protocol connects the adapter to an external Python application.
- Domain models are independent of engine classes and ML libraries.
- An LLM strategist sets adventure-map goals at turn boundaries or major events.
- A System 1 executor selects concrete actions to carry out those goals.
- An RL policy controls battles.

Use uv for Python, CMake with Ninja for C++, and support Windows, Linux, and
macOS. Decision modules must be usable with offline example observations.

## Milestones

### 1. Reproducible VCMI environment

Select and record a shared VCMI release or commit. Each contributor installs
VCMI and supplies their own original Heroes III assets. Document dependencies,
configuration, and platform differences. The game currently runs locally on
Debian 13 with VCMI `1.6.5+dfsg-2`; this is not yet a verified team-wide build.

Completion: contributors can launch the same selected release and baseline.

### 2. Battle contract

Define observations, stacks, battlefield geometry, decision contexts, legal
actions, and action results. Separate player-visible observations from internal
engine state. Obtain base definitions from VCMI and associate catalogs with the
active configuration; report current stack attributes in each observation.

Completion: synthetic observations can be consumed without a running engine.

### 3. Adapter prototype

Inspect matching sources and confirm an integration point for reading state,
waiting for external decisions, and submitting actions. Determine whether a
separate module is practical or an engine build is necessary. Pin sources if
needed; do not add an engine submodule before confirming the requirement.

Start with TCP/JSON between processes. Consider bindings for high-throughput RL
only after measurement. If VCMI AI interfaces provide the integration hook,
keep all actual decision logic in the external application.

Completion: export a real battle observation and execute one legal action.

### 4. Tooling and observability

Provide repeatable build/run instructions, record observations and action
results, and maintain a baseline scenario that can be legally shared.
Keep original game assets, private saves, binaries, and generated results out
of Git. Record rejected actions and enough context to diagnose failures.

Completion: a contributor can follow the README and reproduce the prototype.

### 5. Decision modules

Begin with simple baseline policies to validate integration. Add an RL battle
environment with reset/step semantics and separate reward calculation. Then
extend the contract to the adventure map and add the executor and LLM planner.
Coordinate handoffs through the orchestration layer.

Completion: the application completes a baseline scenario with observable
choices and no integration failures.

### 6. Evaluation

Compare policies on multiple fixed scenarios. Record wins/losses, losses,
decision times, failures, and model versions. Verify reset and random-seed
behavior before claiming deterministic replay. Investigate non-rendered,
parallel battle execution for training.

## Risks and open questions

- VCMI API/ABI changes and compatible builds across platforms.
- Engine integration, dependency setup, and adapter loading mechanisms.
- Hidden information leaking into player observations.
- Correct legality checks and stale-action rejection.
- Rule complexity, modifiers, spells, and siege mechanics.
- Repeatable resets and sufficient simulation throughput for RL.
- A shared VCMI release and a legally shareable baseline scenario.

## Official references

- [VCMI website](https://vcmi.eu/)
- [Releases](https://github.com/vcmi/vcmi/releases)
- [Engine repository](https://github.com/vcmi/vcmi)
- [AI architecture](https://github.com/vcmi/vcmi/blob/develop/docs/developers/AI.md)
- [Code structure](https://github.com/vcmi/vcmi/blob/develop/docs/developers/Code_Structure.md)
- [Building on Linux](https://github.com/vcmi/vcmi/blob/develop/docs/developers/Building_Linux.md)
- [Building on Windows](https://github.com/vcmi/vcmi/blob/develop/docs/developers/Building_Windows.md)
- [Linux installation](https://github.com/vcmi/vcmi/blob/develop/docs/players/Installation_Linux.md)
- [Windows installation](https://github.com/vcmi/vcmi/blob/develop/docs/players/Installation_Windows.md)
