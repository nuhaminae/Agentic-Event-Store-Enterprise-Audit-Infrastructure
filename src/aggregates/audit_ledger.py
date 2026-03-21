# src/aggregates/audit_ledger.py
# This is an audit ledger aggregate

from typing import Dict, List, Optional

from src.models.events import BaseEvent, OptimisticConcurrencyError, StoredEvent


class AuditLedgerAggregate:
    """
    Aggregate root for the Audit Ledger.
    Enforces causal ordering of events across the system.
    """

    def __init__(self, ledger_id: str):
        """
        Initialise the Audit Ledger Aggregate.

        Args:
            ledger_id (str): The identifier for the audit ledger.

        Attributes:
            ledger_id (str): The identifier for the audit ledger.
            stream_position (int): The current position in the event stream.
            events (List[BaseEvent]): The list of events in the audit ledger.
            applied_events (Dict[str, str]): The dictionary of applied events, keyed by correlation ID and valued by causation ID.
        """
        self.ledger_id = ledger_id
        self.stream_position: int = 0
        self.events: List[BaseEvent] = []
        self.applied_events: Dict[str, str] = {}

    @classmethod
    async def load(cls, store, ledger_id: str) -> "AuditLedgerAggregate":
        """
        Load the Audit Ledger Aggregate from the event store.

        Args:
            store (EventStore): The event store.
            ledger_id (str): The ledger ID.

        Returns:
            AuditLedgerAggregate: The loaded aggregate.
        """
        events = await store.load_stream(f"audit-ledger-{ledger_id}")
        agg = cls(ledger_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        """
        Apply a stored event to the aggregate.

        Checks for causal ordering violations before applying the event.

        Raises:
            OptimisticConcurrencyError: If the causal ordering of events is violated.
        """
        if event.causation_id and event.causation_id not in self.applied_events:
            raise OptimisticConcurrencyError(
                f"Causal ordering violation: causation {event.causation_id} not found."
            )
        self.applied_events[str(event.event_id)] = event.event_type
        self.stream_position = event.stream_position

    # --- Commands ---
    def record_event(
        self,
        event_type: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ):
        """
        Record an event in the audit ledger.

        Raises:
            OptimisticConcurrencyError: If the causal ordering of events is violated.

        Args:
            event_type (str): The type of event to record.
            payload (dict): The event payload.
            correlation_id (Optional[str]): The correlation ID for the event.
            causation_id (Optional[str]): The causation ID for the event.
        """
        if causation_id and causation_id not in self.applied_events:
            raise OptimisticConcurrencyError(
                f"Causal ordering violation: causation {causation_id} not yet applied."
            )

        event = BaseEvent(
            event_type=event_type,
            payload=payload,
            version=1,  # schema version fixed
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.events.append(event)
