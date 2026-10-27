# VCMI adapter

- `src/bridge.cpp`: portable loopback TCP transport, send-only observations,
  and validated control replies.
- `engine/ExternalBattle.*`: our observer/controller, without built-in strategy.
- `CMakeLists.txt`: transport library and optional test probe.

The source integration targets the VCMI 1.6.5 player interface and
`vcmiclientcommon`, not BattleAI. Manual observation never waits for Python.
Control errors never choose a fallback action or delegate to a built-in AI.

See [setup and limitations](../../docs/VCMI_ADAPTER.md). A full rebuilt-engine
playthrough has not yet been verified. Installed game packages are unchanged.
