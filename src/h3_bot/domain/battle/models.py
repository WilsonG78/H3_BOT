"""Version 2 battle events and explicit external-control decisions."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonNegative = Annotated[int, Field(strict=True, ge=0)]
Hex = Annotated[int, Field(strict=True, ge=0, lt=187)]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class StackStats(ContractModel):
    attack_melee: int
    attack_ranged: int
    defense_melee: int
    defense_ranged: int
    damage_min_melee: int
    damage_max_melee: int
    damage_min_ranged: int
    damage_max_ranged: int
    movement_range: NonNegative


class TurnStatus(ContractModel):
    waited: bool
    moved: bool
    defended: bool


class BattleStack(ContractModel):
    id: NonNegative
    creature_id: str
    side_id: Literal[0, 1]
    owner: int
    alive: bool
    ghost: bool
    count: NonNegative
    top_unit_hp: NonNegative
    max_unit_hp: NonNegative
    total_hp: NonNegative
    # Negative positions are reserved engine locations (e.g. siege towers).
    position: int
    occupied_hexes: list[int]
    stats: StackStats
    turn_status: TurnStatus
    shots: int | None


class Obstacle(ContractModel):
    id: int
    blocked_hexes: list[Hex]


class Battlefield(ContractModel):
    width: Literal[17]
    height: Literal[11]
    hex_encoding: Literal["vcmi_row_major"]
    obstacles: list[Obstacle]


class DefendAction(ContractModel):
    id: str
    actor_stack_id: NonNegative
    type: Literal["defend"]


class WaitAction(ContractModel):
    id: str
    actor_stack_id: NonNegative
    type: Literal["wait"]


class MoveAction(ContractModel):
    id: str
    actor_stack_id: NonNegative
    type: Literal["move"]
    destination_hex: Hex


class ShootAction(ContractModel):
    id: str
    actor_stack_id: NonNegative
    type: Literal["shoot"]
    target_stack_id: NonNegative


class MeleeAction(ContractModel):
    id: str
    actor_stack_id: NonNegative
    type: Literal["melee_attack"]
    target_stack_id: NonNegative
    target_hex: Hex
    destination_hex: Hex


LegalAction = Annotated[
    DefendAction | WaitAction | MoveAction | ShootAction | MeleeAction,
    Field(discriminator="type"),
]


class BattleObservation(ContractModel):
    type: Literal["observation"]
    schema_version: Literal[2]
    battle_id: str
    revision: NonNegative
    decision_id: str
    round: int | None
    viewer_side: Literal[0, 1]
    active_stack_id: NonNegative | None
    engine: str
    capabilities: list[str]
    battlefield: Battlefield
    stacks: list[BattleStack]
    mode: Literal["observe", "control"]
    event: Literal["battle_started", "round_started", "action_finished", "decision", "battle_ended", "environment_error"]
    status: Literal["running", "terminated", "error"]
    winner_side: Literal[0, 1, 2] | None = None
    error: str | None = None
    legal_actions: list[LegalAction]

    @property
    def requires_action(self) -> bool:
        return self.mode == "control" and self.event == "decision" and self.status == "running"


    @model_validator(mode="after")
    def validate_references(self) -> "BattleObservation":
        stacks = {stack.id for stack in self.stacks}
        if len(stacks) != len(self.stacks):
            raise ValueError("Duplicate stack IDs")
        if self.active_stack_id is not None and self.active_stack_id not in stacks:
            raise ValueError("Active stack is missing")
        if self.requires_action and (self.active_stack_id is None or not self.legal_actions):
            raise ValueError("Control decisions require an actor and offered actions")
        if not self.requires_action and self.legal_actions:
            raise ValueError("Non-decision events must not offer actions")
        if (self.event == "battle_ended") != (self.status == "terminated"):
            raise ValueError("Battle-end events must be terminal")
        if (self.event == "environment_error") != (self.status == "error"):
            raise ValueError("Environment errors must have error status")
        if self.status == "error" and not self.error:
            raise ValueError("Environment errors require a reason")
        ids = [action.id for action in self.legal_actions]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate action IDs")
        for action in self.legal_actions:
            if action.actor_stack_id != self.active_stack_id:
                raise ValueError("Action actor differs from active stack")
            if isinstance(action, (ShootAction, MeleeAction)) and action.target_stack_id not in stacks:
                raise ValueError("Action target is missing")
        return self


class ActionReply(ContractModel):
    type: Literal["action"] = "action"
    schema_version: Literal[2] = 2
    battle_id: str
    revision: NonNegative
    decision_id: str
    action_id: str

    @classmethod
    def select(cls, observation: BattleObservation, action_id: str) -> "ActionReply":
        if not observation.requires_action:
            raise ValueError("This event does not request an action")
        if action_id not in {action.id for action in observation.legal_actions}:
            raise ValueError("Selected action was not offered")
        return cls(
            battle_id=observation.battle_id,
            revision=observation.revision,
            decision_id=observation.decision_id,
            action_id=action_id,
        )
