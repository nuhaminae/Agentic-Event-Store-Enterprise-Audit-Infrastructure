# src/aggregates/audit_ledger.py
# This is an audit ledger aggregate

from typing import Dict, List, Optional

from src.models.aggregates import AuditLedgerEventPayload
from src.models.events import BaseEvent, OptimisticConcurrencyError, StoredEvent


class AuditLedgerAggregate:
    """
    Aggregate root for the Audit Ledger.
    Enforces causal ordering of events across the system.
    """

    def __init__(self, ledger_id: str):
        """
        Initialises a new AuditLedgerAggregate.

        Args:
            ledger_id (str): The unique identifier for this audit ledger.

        Attributes:
            ledger_id (str): The unique identifier for this audit ledger.
            stream_position (int): The current position of the event stream.
            events (List[BaseEvent]): The list of events that have occurred in the audit ledger.
            applied_events (Dict[str, str]): A dictionary of event IDs to their corresponding causation IDs.
        """
        self.ledger_id = ledger_id
        self.stream_position: int = 0
        self.events: List[BaseEvent] = []
        self.applied_events: Dict[str, str] = {}

    @classmethod
    async def load(cls, store, ledger_id: str) -> "AuditLedgerAggregate":
        """
        Loads an AuditLedgerAggregate from the event store.

        Args:
            store (EventStore): The event store to load from.
            ledger_id (str): The unique identifier for this audit ledger.

        Returns:
            AuditLedgerAggregate: The loaded AuditLedgerAggregate.
        """
        events = await store.load_stream(f"audit-ledger-{ledger_id}")
        agg = cls(ledger_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        """
        Applies a stored event to the aggregate.

        Enforces causal ordering by checking that the event's causation
        ID is present in the applied events. If not found, raises an
        OptimisticConcurrencyError.

        :param event: The event to be applied.
        :type event: StoredEvent
        :raises OptimisticConcurrencyError: If the causation ID is not found.
        """
        if event.causation_id and event.causation_id not in self.applied_events:
            raise OptimisticConcurrencyError(
                f"Causal ordering violation: causation {event.causation_id} not found.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        self.applied_events[str(event.event_id)] = event.event_type
        self.stream_position = event.stream_position

    # --- Commands ---
    def record_event(
        self,
        event_type: str,
        payload: Dict,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ):
        """
        Records an event in the audit ledger.

        Args:
            event_type (str): The type of event to record.
            payload (Dict): The event payload.
            correlation_id (Optional[str], optional): Correlation ID for tracing workflows. Defaults to None.
            causation_id (Optional[str], optional): Causation ID for tracing causal chains. Defaults to None.

        Raises:
            OptimisticConcurrencyError: If the causation ID has not been applied yet.
        """
        if causation_id and causation_id not in self.applied_events:
            raise OptimisticConcurrencyError(
                f"Causal ordering violation: causation {causation_id} not yet applied.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        validated_payload = AuditLedgerEventPayload(data=payload)
        self._raise_event(
            event_type,
            validated_payload.model_dump(),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

    def _raise_event(
        self,
        event_type: str,
        payload: dict,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
    ):
        """
        Raises an event of the specified type with the given payload.

        Args:
            event_type (str): The type of the event to be raised.
            payload (dict): The payload of the event to be raised.
            correlation_id (Optional[str]): The correlation ID linking related events across streams.
            causation_id (Optional[str]): The causation ID linking back to the event that triggered this one.

        Returns:
            None
        """
        event = BaseEvent(
            event_type=event_type,
            payload=payload,
            version=1,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.events.append(event)
