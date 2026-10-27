"""Atomic publication of the latest received decision observation."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from h3_bot.domain.battle.models import BattleObservation


def publish(path: Path, observation: BattleObservation) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "observation": observation.model_dump(mode="json"),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
