# src/aggregates/compliance_record.py
# This is a compliance record aggregate

from typing import Optional, Set

from src.models.aggregates import (
    AllComplianceChecksCompletedPayload,
    ComplianceCheckRecordedPayload,
    ComplianceRecordArchivedPayload,
    ComplianceState,
)
from src.models.events import (
    BaseEvent,
    DomainError,
    OptimisticConcurrencyError,
    StoredEvent,
)

MANDATORY_CHECKS = {"fraud", "credit", "kyc", "aml"}


class ComplianceRecordAggregate:

    def __init__(self, compliance_id: str):
        """
        Initialises a ComplianceRecordAggregate instance.

        Args:
            compliance_id (str): The ID of the compliance record.

        Sets the compliance record state to NEW, stream position to 0,
        and initialises the events, completed checks, and archived_at
        attributes.
        """
        self.compliance_id = compliance_id
        self.state: ComplianceState = ComplianceState.NEW
        self.stream_position: int = 0
        self.events: list[BaseEvent] = []
        self.completed_checks: Set[str] = set()
        self.archived_at: Optional[str] = None

    @classmethod
    async def load(cls, store, compliance_id: str) -> "ComplianceRecordAggregate":
        """
        Loads a compliance record aggregate from the event store.

        Args:
            store: The event store to load from.
            compliance_id (str): The ID of the compliance record to load.

        Returns:
            ComplianceRecordAggregate: The loaded compliance record aggregate.
        """
        events = await store.load_stream(f"compliance-{compliance_id}")
        agg = cls(compliance_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        """
        Applies a stored event to the aggregate.

        Args:
            event (StoredEvent): The stored event to apply.

        Notes:
            - If the event has a corresponding handler, it calls the handler.
            - Regardless of whether a handler exists, updates the stream position.
        """
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.stream_position = event.stream_position

    # --- Event Handlers ---
    def _on_ComplianceCheckRecorded(self, event: StoredEvent) -> None:
        """
        Handles a ComplianceCheckRecorded event

        Args:
            event (StoredEvent): The ComplianceCheckRecorded event to handle

        Notes:
            - Sets the state of the compliance record to CHECKS_IN_PROGRESS
            - Adds the check type to the completed_checks set
        """

        self.state = ComplianceState.CHECKS_IN_PROGRESS
        self.completed_checks.add(event.payload["check_type"])

    def _on_AllComplianceChecksCompleted(self, event: StoredEvent) -> None:
        """
        Handles an AllComplianceChecksCompleted event

        Args:
            event (StoredEvent): The AllComplianceChecksCompleted event to handle

        Notes:
            This event is triggered when all compliance checks have been completed.
            It sets the state of the compliance record to ALL_CHECKS_COMPLETED.
        """
        self.state = ComplianceState.ALL_CHECKS_COMPLETED

    def _on_ComplianceRecordArchived(self, event: StoredEvent) -> None:
        """
        Handles a ComplianceRecordArchived event

        Args:
            event (StoredEvent): The ComplianceRecordArchived event to handle

        Notes:
            - Sets the state of the compliance record to ARCHIVED
            - Records the archived_at timestamp from the event payload
        """
        self.state = ComplianceState.ARCHIVED
        self.archived_at = event.payload["archived_at"]

    # --- Commands ---
    def record_check(self, check_type: str):
        """
        Records a compliance check for a compliance record.

        Args:
            check_type (str): the type of compliance check to record

        Raises:
            OptimisticConcurrencyError: if the compliance record has been archived
            DomainError: if the compliance check has already been recorded
        """
        if self.state == ComplianceState.ARCHIVED:
            raise OptimisticConcurrencyError(
                "Cannot record checks on archived compliance record.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        if check_type in self.completed_checks:
            raise DomainError(f"Check {check_type} already recorded.")

        self.completed_checks.add(check_type)
        payload = ComplianceCheckRecordedPayload(check_type=check_type)
        self._raise_event("ComplianceCheckRecorded", payload.model_dump())

        if MANDATORY_CHECKS.issubset(self.completed_checks):
            payload = AllComplianceChecksCompletedPayload(
                completed=list(self.completed_checks)
            )
            self._raise_event("AllComplianceChecksCompleted", payload.model_dump())

    def archive(self, archived_at: str):
        """
        Archives the compliance record if all mandatory checks have been completed.

        Args:
            archived_at: str - timestamp of when the compliance record was archived

        Raises:
            DomainError - if the compliance record has not completed all mandatory checks
        """
        if self.state != ComplianceState.ALL_CHECKS_COMPLETED:
            raise DomainError(
                "Cannot archive until all mandatory checks are completed."
            )
        payload = ComplianceRecordArchivedPayload(archived_at=archived_at)
        self._raise_event("ComplianceRecordArchived", payload.model_dump())

    def _raise_event(self, event_type: str, payload: dict):
        """
        Raises a domain event of the specified type with the given payload.

        Args:
            event_type (str): The type of event to be raised.
            payload (dict): The event payload.

        Returns:
            None

        Notes:
            - This method ensures that all raised events are immutable and have a version.
            - It is also responsible for appending the raised event to the aggregate's event list.
        """
        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions ---
    def assert_all_checks_completed(self):
        """
        Asserts that all mandatory compliance checks have been completed.

        Raises:
            DomainError: If not all mandatory compliance checks have been completed.
        """
        if not MANDATORY_CHECKS.issubset(self.completed_checks):
            raise DomainError(
                "Not all mandatory compliance checks have been completed."
            )
