# src/aggregates/compliance_record.py
# This is a compliance record aggregate

from typing import Optional, Set

from src.models.aggregates import ComplianceState
from src.models.events import BaseEvent, OptimisticConcurrencyError, StoredEvent

MANDATORY_CHECKS = {"fraud", "credit", "kyc", "aml"}


class ComplianceRecordAggregate:

    def __init__(self, record_id: str):
        """
        Initialises a new Compliance record aggregate.

        Args:
            record_id (str): The identifier for the compliance record.

        Attributes:
            record_id (str): The identifier for the compliance record.
            state (ComplianceState): The state of the compliance record.
            stream_position (int): The current position in the event stream.
            events (list[BaseEvent]): The list of events in the compliance record.
            completed_checks (Set[str]): The set of completed compliance checks.
            archived_at (Optional[str]): The timestamp when the compliance record was archived.
        """
        self.record_id = record_id
        self.state: ComplianceState = ComplianceState.NEW
        self.stream_position: int = 0
        self.events: list[BaseEvent] = []
        self.completed_checks: Set[str] = set()
        self.archived_at: Optional[str] = None

    @classmethod
    async def load(cls, store, record_id: str) -> "ComplianceRecordAggregate":
        """
        Loads a Compliance record aggregate from the event store.

        Args:
            store (EventStore): The event store.
            record_id (str): The identifier for the compliance record.

        Returns:
            ComplianceRecordAggregate: The loaded aggregate.
        """
        events = await store.load_stream(f"compliance-{record_id}")
        agg = cls(record_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        """
        Applies a stored event to the aggregate.

        Calls the relevant event handler method if it exists, and updates the
        aggregate's stream position to the position of the applied event.

        Raises:
            OptimisticConcurrencyError: If the causal ordering of events is violated.
        """
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.stream_position = event.stream_position

    # --- Event Handlers ---
    def _on_ComplianceCheckRecorded(self, event: StoredEvent) -> None:
        """
        Applies a ComplianceCheckRecorded event to the aggregate.

        Updates the state to CHECKS_IN_PROGRESS and adds the check type to the set of completed checks.

        Args:
            event (StoredEvent): The event to apply.
        """
        self.state = ComplianceState.CHECKS_IN_PROGRESS
        self.completed_checks.add(event.payload["check_type"])

    def _on_AllComplianceChecksCompleted(self, event: StoredEvent) -> None:
        """
        Applies an AllComplianceChecksCompleted event to the aggregate.

        Updates the state to ALL_CHECKS_COMPLETED.

        Args:
            event (StoredEvent): The event to apply.
        """
        self.state = ComplianceState.ALL_CHECKS_COMPLETED

    def _on_ComplianceRecordArchived(self, event: StoredEvent) -> None:
        """
        Applies a ComplianceRecordArchived event to the aggregate.

        Updates the state to ARCHIVED and records the archived_at timestamp.

        Args:
            event (StoredEvent): The event to apply.
        """
        self.state = ComplianceState.ARCHIVED
        self.archived_at = event.payload["archived_at"]

    # --- Commands ---
    def record_check(self, check_type: str):
        """
        Records a compliance check for a compliance record.

        Raises:
            OptimisticConcurrencyError: If the compliance record is archived or the check has already been recorded.

        Args:
            check_type (str): The type of compliance check to record.
        """
        if self.state == ComplianceState.ARCHIVED:
            raise OptimisticConcurrencyError(
                "Cannot record checks on archived compliance record."
            )
        if check_type in self.completed_checks:
            raise OptimisticConcurrencyError(f"Check {check_type} already recorded.")

        self.completed_checks.add(check_type)
        self._raise_event("ComplianceCheckRecorded", {"check_type": check_type})

        if MANDATORY_CHECKS.issubset(self.completed_checks):
            self._raise_event(
                "AllComplianceChecksCompleted",
                {"completed": list(self.completed_checks)},
            )

    def archive(self, archived_at: str):
        """
        Archives a compliance record.

        Raises an OptimisticConcurrencyError if the record is not in the ALL_CHECKS_COMPLETED state.

        Args:
            archived_at (str): The timestamp when the compliance record was archived.
        """
        if self.state != ComplianceState.ALL_CHECKS_COMPLETED:
            raise OptimisticConcurrencyError(
                "Cannot archive until all mandatory checks are completed."
            )
        self._raise_event("ComplianceRecordArchived", {"archived_at": archived_at})

    def _raise_event(self, event_type: str, payload: dict):
        # schema version fixed at 1
        """
        Raises an event of the specified type with the given payload.

        The event is appended to the aggregate's events list.

        Args:
            event_type (str): The type of event to raise.
            payload (dict): The event payload.
        """
        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions ---
    def assert_all_checks_completed(self):
        """
        Asserts that all mandatory compliance checks have been completed.

        Raises an OptimisticConcurrencyError if not all mandatory compliance checks have been completed.
        """
        if not MANDATORY_CHECKS.issubset(self.completed_checks):
            raise OptimisticConcurrencyError(
                "Not all mandatory compliance checks have been completed."
            )
