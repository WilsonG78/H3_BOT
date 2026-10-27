# Battle protocol v2

- `battle-observation-v2.schema.json`: partial lifecycle/control observation.
- `battle-action-v2.schema.json`: explicit control action ID reply.

Version 2 replaces the BattleAI-based decision-only prototype. It adds separate
observe/control modes, nullable actors, empty action lists outside decisions,
and battle-end/error statuses. Observe mode never expects an action reply.

Schemas come from `src/h3_bot/domain/battle/models.py`:
`uv run python scripts/export-battle-schemas.py`.
Synthetic observer/control fixtures are in `data/fixtures/`.
See the [adapter guide](../docs/VCMI_ADAPTER.md) for transport and limitations.
