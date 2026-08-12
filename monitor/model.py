from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Observation:
    status: str
    raw_status: str
    places: Optional[int]

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "status": self.status,
            "raw_status": self.raw_status,
            "places": self.places,
        }

    @classmethod
    def from_dict(cls, value):
        # type: (Dict[str, Any]) -> Observation
        return cls(
            status=str(value["status"]),
            raw_status=str(value["raw_status"]),
            places=value.get("places"),
        )


@dataclass(frozen=True)
class MonitorState:
    observation: Optional[Observation]
    observed_at: Optional[str]
    last_heartbeat_slot: Optional[str]

    def to_dict(self):
        # type: () -> Dict[str, Any]
        return {
            "observation": (
                self.observation.to_dict() if self.observation is not None else None
            ),
            "observed_at": self.observed_at,
            "last_heartbeat_slot": self.last_heartbeat_slot,
        }

    @classmethod
    def from_dict(cls, value):
        # type: (Dict[str, Any]) -> MonitorState
        observation_data = value.get("observation")
        observation = (
            Observation.from_dict(observation_data)
            if observation_data is not None
            else None
        )
        return cls(
            observation=observation,
            observed_at=value.get("observed_at"),
            last_heartbeat_slot=value.get("last_heartbeat_slot"),
        )
