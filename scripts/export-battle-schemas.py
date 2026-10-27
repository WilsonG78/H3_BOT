"""Regenerate public JSON schemas from the Python contract."""

import json
from pathlib import Path

from h3_bot.domain.battle.models import ActionReply, BattleObservation

root = Path(__file__).resolve().parents[1]
for name, model in [("observation", BattleObservation), ("action", ActionReply)]:
    path = root / "protocol" / f"battle-{name}-v2.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
