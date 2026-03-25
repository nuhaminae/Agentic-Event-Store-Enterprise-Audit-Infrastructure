# Upcaster Registry
# Looks up table for schema evolution

import json

from src.models.events import BaseEvent, StoredEvent


class UpcasterRegistry:
    def __init__(self):
        """Initialise UpcasterRegistry.

        The registry is an empty dictionary at initialisation.
        It will be populated with upcasters during registration.
        """

        self._registry: dict[tuple[str, int], callable] = {}

    def register(self, event_type: str, from_version: int, upcaster):
        
        """
        Register an upcaster for a given event type and version.

        Args:
            event_type (str): The event type to register the upcaster for.
            from_version (int): The version of the event type to register the upcaster for.
            upcaster (callable): A callable that takes a BaseEvent and returns an upcasted BaseEvent.
        """
        self._registry[(event_type, from_version)] = upcaster

    def from_row(self, row) -> BaseEvent:
        """Convert DB row (StoredEvent) to BaseEvent and upcast if needed."""
        stored = StoredEvent(
            event_id=row["event_id"],
            stream_id=row["stream_id"],
            stream_position=row["stream_position"],
            global_position=row["global_position"],
            event_type=row["event_type"],
            event_version=row["event_version"],
            payload=(
                row["payload"]
                if isinstance(row["payload"], dict)
                else json.loads(row["payload"])
            ),
            metadata=(
                row["metadata"]
                if isinstance(row["metadata"], dict)
                else json.loads(row["metadata"])
            ),
            recorded_at=row["recorded_at"],
            correlation_id=row["correlation_id"],
            causation_id=row["causation_id"],
        )
        event = BaseEvent(
            event_type=stored.event_type,
            version=stored.event_version,
            payload=stored.payload,
            metadata=stored.metadata,
            correlation_id=stored.correlation_id,
            causation_id=stored.causation_id,
            recorded_at=stored.recorded_at,
        )
        return self.upcast(event)

    def upcast(self, event: BaseEvent) -> BaseEvent:
        """Upcast an event to its latest version using registered upcasters.

        The function iterates through the upcasters registered for the given event type
        and version, applies each upcaster in order, and returns the upcasted event.
        If no upcasters are registered for the given event type and version, the
        event is returned as is.
        """
        while (event.event_type, event.version) in self._registry:
            event = self._registry[(event.event_type, event.version)](event)
        return event
