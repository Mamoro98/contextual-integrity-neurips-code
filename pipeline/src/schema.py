"""Unified contextual factors schema for scenario experiments.

7 target-agnostic factors grounded in:
- Contextual Integrity (Nissenbaum)
- Accountability Theory
- Dual-Process Theory (Kahneman)
- Social Exchange Theory
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any


# ── Context type (always present, not counted in factor_count) ───────────────

class ContextType(Enum):
    """Information norm context -- CI (Nissenbaum)."""
    FINANCIAL = "financial"
    MEDICAL = "medical"
    SOCIAL = "social"
    LEGAL = "legal"
    COMMERCIAL = "commercial"
    EDUCATIONAL = "educational"


# ── Transmission principle strength ──────────────────────────────────────────

class TransmissionPrinciple(Enum):
    """Strength of normative justification for sharing -- CI (Nissenbaum).

    none:   No specific reason to share the target info.
    weak:   Vague or future-oriented justification.
    strong: Concrete, immediate procedural/contractual requirement.
    """
    NONE = "none"
    WEAK = "weak"
    STRONG = "strong"


# ── Unified CI factor schema ────────────────────────────────────────────────

BOOLEAN_FACTOR_NAMES = [
    "information_flow_expected",
    "receiver_role_legitimacy",
]


@dataclasses.dataclass(frozen=True)
class ContextualFactors:
    """Target-agnostic CI contextual factors.

    Four factors reach the model: context_type (always present, not counted),
    information_flow_expected, receiver_role_legitimacy, and
    transmission_principle. factor_count = number of active *counted* factors
    (0-3): the two booleans plus transmission_principle (1 if not NONE).
    context_type is always present and not counted.
    """

    context_type: ContextType = ContextType.SOCIAL
    information_flow_expected: bool = False
    receiver_role_legitimacy: bool = False
    transmission_principle: TransmissionPrinciple = TransmissionPrinciple.NONE

    def __post_init__(self) -> None:
        for name in BOOLEAN_FACTOR_NAMES:
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a Boolean (true or false).")

    @property
    def factor_count(self) -> int:
        """Count of active factors (0-3). context_type not counted."""
        count = sum(getattr(self, name) for name in BOOLEAN_FACTOR_NAMES)
        if self.transmission_principle != TransmissionPrinciple.NONE:
            count += 1
        return count

    @property
    def active_factors(self) -> list[str]:
        """Names of active factors."""
        active = [
            name for name in BOOLEAN_FACTOR_NAMES
            if getattr(self, name)
        ]
        if self.transmission_principle != TransmissionPrinciple.NONE:
            active.append(f"tp_{self.transmission_principle.value}")
        return active

    @property
    def inactive_factors(self) -> list[str]:
        """Names of factors that should be absent."""
        inactive = [
            name for name in BOOLEAN_FACTOR_NAMES
            if not getattr(self, name)
        ]
        if self.transmission_principle == TransmissionPrinciple.NONE:
            inactive.extend(["tp_weak", "tp_strong"])
        elif self.transmission_principle == TransmissionPrinciple.WEAK:
            inactive.append("tp_strong")
        return inactive

    @property
    def folder_name(self) -> str:
        """Short folder name encoding factor_count + active factors.

        Examples: 'fc0', 'fc3_infoflow_receiverrole_tp-strong'
        """
        short = {
            "information_flow_expected": "infoflow",
            "receiver_role_legitimacy": "receiverrole",
        }
        parts = [f"fc{self.factor_count}"]
        for name in BOOLEAN_FACTOR_NAMES:
            if getattr(self, name):
                parts.append(short.get(name, name))
        if self.transmission_principle != TransmissionPrinciple.NONE:
            parts.append(f"tp-{self.transmission_principle.value}")
        return "_".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_type": self.context_type.value,
            "information_flow_expected": self.information_flow_expected,
            "receiver_role_legitimacy": self.receiver_role_legitimacy,
            "transmission_principle": self.transmission_principle.value,
            "factor_count": self.factor_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextualFactors:
        """Deserialize from dict."""
        tp_raw = data.get("transmission_principle", "none")
        return cls(
            context_type=ContextType(data["context_type"]),
            information_flow_expected=data.get(
                "information_flow_expected", False
            ),
            receiver_role_legitimacy=data.get(
                "receiver_role_legitimacy", False
            ),
            transmission_principle=TransmissionPrinciple(tp_raw),
        )

    def prompt_lines(self) -> list[str]:
        """Factor descriptions for the LLM generation prompt."""
        return [
            f"- Context type: {self.context_type.value}",
            f"- Information flow expected: {self.information_flow_expected}",
            f"- Receiver role legitimacy: {self.receiver_role_legitimacy}",
            f"- Transmission principle: {self.transmission_principle.value}",
        ]


def factors_from_dict(data: dict[str, Any]) -> ContextualFactors:
    """Deserialize factors from dict."""
    return ContextualFactors.from_dict(data)


# ── Scenario-level dataclasses ────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class ScenarioMetadata:
    """Fixed social context metadata."""

    platform_type: str = "forum"
    relationship_type: str = "strangers"
    pseudonymity: str = "screen_names"

    def to_dict(self) -> dict[str, str]:
        return {
            "platform_type": self.platform_type,
            "relationship_type": self.relationship_type,
            "pseudonymity": self.pseudonymity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ScenarioMetadata:
        return cls(
            platform_type=data.get("platform_type", "forum"),
            relationship_type=data.get("relationship_type", "strangers"),
            pseudonymity=data.get("pseudonymity", "screen_names"),
        )


@dataclasses.dataclass
class ScenarioConfig:
    """Full scenario configuration combining all parts.

    Agents are stored as lists:
        innocents:  [{"screen_name": ..., "country": ...}, ...]
        adversaries: [{"screen_name": ..., "country": ...}, ...]

    Backward-compat properties (innocent_screen_name, etc.) return the
    first element of each list.
    """

    schema_version: str
    scenario_id: str
    extraction_target: str

    # Agent identities
    innocents: list[dict[str, str]]
    adversaries: list[dict[str, str]]

    # Scenario content
    premise: str
    shared_memories: list[str]
    player_specific_memories: dict[str, list[str]]
    goals: dict[str, str]
    task_checklist: dict[str, str]

    # Scoring
    contextual_factors: ContextualFactors
    metadata: ScenarioMetadata

    # Private data values for leakage detection
    private_data: dict[str, dict[str, str]] = dataclasses.field(
        default_factory=dict
    )

    # Item IDs that are task-relevant (should be shared for task completion)
    # The extraction_target must NEVER be in this list.
    task_relevant_items: list[str] = dataclasses.field(
        default_factory=list
    )

    # "adversarial" = sharing is inappropriate (default)
    # "appropriate" = sharing is CI-compliant and correct
    scenario_class: str = "adversarial"

    # Provenance only; never read as a simulation instruction.
    generation: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.innocents:
            raise ValueError("innocents must contain at least one actor.")
        if not self.adversaries:
            raise ValueError("adversaries/requestors must contain at least one actor.")

    # ── Backward-compat properties ──────────────────────────────────────

    @property
    def innocent_screen_name(self) -> str:
        return self.innocents[0]["screen_name"]

    @property
    def innocent_country(self) -> str:
        return self.innocents[0]["country"]

    @property
    def adversary_screen_name(self) -> str:
        return self.adversaries[0]["screen_name"]

    @property
    def adversary_country(self) -> str:
        return self.adversaries[0]["country"]

    @property
    def all_screen_names(self) -> list[str]:
        return (
            [a["screen_name"] for a in self.innocents]
            + [a["screen_name"] for a in self.adversaries]
        )

    # ── Serialization ───────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML output."""
        # Use "requestors" key for appropriate scenarios, "adversaries" otherwise
        other_role_key = (
            "requestors" if self.scenario_class == "appropriate"
            else "adversaries"
        )
        result = {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "scenario_class": self.scenario_class,
            "extraction_target": self.extraction_target,
            "agents": {
                "innocents": list(self.innocents),
                other_role_key: list(self.adversaries),
            },
            "premise": self.premise,
            "shared_memories": self.shared_memories,
            "player_specific_memories": self.player_specific_memories,
            "goals": self.goals,
            "task_checklist": self.task_checklist,
            "contextual_factors": self.contextual_factors.to_dict(),
            "metadata": self.metadata.to_dict(),
            "private_data": self.private_data,
            "task_relevant_items": self.task_relevant_items,
        }
        if self.generation:
            result["generation"] = self.generation
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScenarioConfig:
        """Deserialize from dict (e.g. loaded YAML).

        Supports three agent formats:
        - Old singular: agents.innocent / agents.adversary
        - List adversarial: agents.innocents / agents.adversaries
        - List appropriate: agents.innocents / agents.requestors
        """
        agents = data["agents"]
        if "innocents" in agents:
            innocents = agents["innocents"]
            # Accept either "adversaries" or "requestors"
            adversaries = agents.get(
                "adversaries", agents.get("requestors", [])
            )
        else:
            innocents = [agents["innocent"]]
            adversaries = [agents["adversary"]]

        return cls(
            schema_version=data["schema_version"],
            scenario_id=data["scenario_id"],
            extraction_target=data["extraction_target"],
            innocents=innocents,
            adversaries=adversaries,
            premise=data["premise"],
            shared_memories=data["shared_memories"],
            player_specific_memories=data["player_specific_memories"],
            goals=data["goals"],
            task_checklist=data["task_checklist"],
            contextual_factors=factors_from_dict(data["contextual_factors"]),
            metadata=ScenarioMetadata.from_dict(data["metadata"]),
            private_data=data.get("private_data", {}),
            task_relevant_items=data.get("task_relevant_items", []),
            scenario_class=data.get("scenario_class", "adversarial"),
            generation=data.get("generation", {}) or {},
        )
