# src/aggregates/loan_application.py
# This is a loan application aggregate

from typing import Optional

from src.models.aggregates import ApplicationState
from src.models.events import (
    ApplicationArchivedPayload,
    ApplicationSubmittedPayload,
    BaseEvent,
    CreditAnalysisCompletedPayload,
    DecisionGeneratedPayload,
    DomainError,
    FraudScreeningCompletedPayload,
    HumanReviewRequiredPayload,
    OptimisticConcurrencyError,
    StoredEvent,
)


class LoanApplicationAggregate:
    def __init__(self, application_id: str):
        """
        Initialise a new LoanApplicationAggregate.
        """
        self.application_id = application_id
        self.state: ApplicationState = ApplicationState.NEW
        self.stream_position: int = 0
        self.events: list[BaseEvent] = []
        # domain attributes
        self.applicant_id: Optional[str] = None
        self.requested_amount: Optional[float] = None
        self.approved_amount: Optional[float] = None
        self.decision: Optional[str] = None
        self.archived_at: Optional[str] = None

    @classmethod
    async def load(cls, store, application_id: str) -> "LoanApplicationAggregate":
        """
        Loads a LoanApplicationAggregate from the event store.
        """
        events = await store.load_stream(f"loan-{application_id}")
        agg = cls(application_id)
        for event in events:
            agg._apply(event)
        return agg

    def _apply(self, event: StoredEvent) -> None:
        """
        Applies a stored event to the aggregate.
        """
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.stream_position = event.stream_position

    # --- Event Handlers ---
    def _on_ApplicationSubmitted(self, event: StoredEvent) -> None:
        """
        Handles an ApplicationSubmitted event.

        Updates the aggregate's state to SUBMITTED and sets the applicant_id and requested_amount attributes from the event payload.
        """
        self.state = ApplicationState.SUBMITTED
        self.applicant_id = event.payload["applicant_id"]
        self.requested_amount = event.payload["requested_amount_usd"]

    def _on_CreditAnalysisCompleted(self, event: StoredEvent) -> None:
        """
        Handles a CreditAnalysisCompleted event.

        Args:
            event (StoredEvent): The CreditAnalysisCompleted event to handle.

        Notes:
            - Sets the state to CREDIT_ANALYSED.
        """
        self.state = ApplicationState.CREDIT_ANALYSED

    def _on_FraudScreeningCompleted(self, event: StoredEvent) -> None:
        """
        Handles a FraudScreeningCompleted event.

        Args:
            event (StoredEvent): The FraudScreeningCompleted event to handle.

        Notes:
            - Sets the state to FRAUD_SCREENED.
        """
        self.state = ApplicationState.FRAUD_SCREENED

    def _on_ComplianceCheckCompleted(self, event: StoredEvent) -> None:
        """
        Handles a ComplianceCheckCompleted event.

        Args:
            event (StoredEvent): The ComplianceCheckCompleted event to handle.

        Notes:
            - Sets the state to COMPLIANCE_CHECKED.
        """
        self.state = ApplicationState.COMPLIANCE_CHECKED

    def _on_DecisionGenerated(self, event: StoredEvent) -> None:
        """
        Handles a DecisionGenerated event.

        Args:
            event (StoredEvent): The DecisionGenerated event to handle.

        Notes:
            - Sets the state to DECIDED.
            - Sets the decision and approved_amount attributes from the event payload.
        """
        self.state = ApplicationState.DECIDED
        self.decision = event.payload["decision"]
        self.approved_amount = event.payload.get("approved_amount_usd")

    def _on_HumanReviewRequired(self, event: StoredEvent) -> None:
        """
        Handles a HumanReviewRequired event.

        Args:
            event (StoredEvent): The HumanReviewRequired event to handle.

        Notes:
            - Sets the state to HUMAN_REVIEW.
        """
        self.state = ApplicationState.HUMAN_REVIEW

    def _on_ApplicationArchived(self, event: StoredEvent) -> None:
        """
        Handles an ApplicationArchived event.

        Args:
            event (StoredEvent): The ApplicationArchived event to handle.

        Notes:
            - Sets the state to ARCHIVED.
            - Records the archived_at timestamp from the event payload.
        """
        self.state = ApplicationState.ARCHIVED
        self.archived_at = event.payload["archived_at"]

    # --- Commands ---
    def submit_application(self, applicant_id: str, requested_amount_usd: float):
        """
        Submits a loan application for review.

        :param applicant_id: Unique identifier of the applicant.
        :param requested_amount_usd: Amount requested by the applicant in USD.
        :raises OptimisticConcurrencyError: If the application has already been submitted.

        :return: None
        """
        if self.state != ApplicationState.NEW:
            raise OptimisticConcurrencyError(
                "Application already submitted.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        payload = ApplicationSubmittedPayload(
            applicant_id=applicant_id,
            requested_amount_usd=requested_amount_usd,
        )
        self._raise_event("ApplicationSubmitted", payload.model_dump())

    def credit_analysis_completed(
        self,
        agent_id: str,
        session_id: str,
        model_version: str,
        confidence_score: float,
        risk_tier: str,
        recommended_limit_usd: float,
        duration_ms: int,
        input_data_hash: Optional[str],
    ):
        """
        Records a credit analysis result for an application.

        Raises an OptimisticConcurrencyError if the application is not awaiting credit analysis.

        :param agent_id: The ID of the agent that ran the credit analysis.
        :param session_id: The ID of the credit analysis session.
        :param model_version: The version of the credit analysis model.
        :param confidence_score: The confidence score of the credit analysis.
        :param risk_tier: The risk tier of the credit analysis.
        :param recommended_limit_usd: The recommended limit of the credit analysis.
        :param duration_ms: The duration of the credit analysis in milliseconds.
        :param input_data_hash: The hash of the input data used for the credit analysis.
        """
        if self.state != ApplicationState.SUBMITTED:
            raise OptimisticConcurrencyError(
                "Application not awaiting credit analysis.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        payload = CreditAnalysisCompletedPayload(
            application_id=self.application_id,
            agent_id=agent_id,
            session_id=session_id,
            model_version=model_version,
            confidence_score=confidence_score,
            risk_tier=risk_tier,
            recommended_limit_usd=recommended_limit_usd,
            analysis_duration_ms=duration_ms,
            input_data_hash=input_data_hash,
        )
        self._raise_event("CreditAnalysisCompleted", payload.model_dump())

    def fraud_screening_completed(self, result: str):
        """
        Marks the application as having completed fraud screening.

        Args:
            result (str): The result of the fraud screening.

        Raises:
            OptimisticConcurrencyError: If the application is not in the CREDIT_ANALYSED state.
        """
        if self.state != ApplicationState.CREDIT_ANALYSED:
            raise OptimisticConcurrencyError(
                "Application not awaiting fraud screening.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        payload = FraudScreeningCompletedPayload(
            application_id=self.application_id,
            result=result,
        )
        self._raise_event("FraudScreeningCompleted", payload.model_dump())

    def generate_decision(
        self, decision: str, approved_amount_usd: Optional[float] = None
    ):
        """
        Generate a decision for an application.

        The application must have completed compliance checks (ApplicationState.COMPLIANCE_CHECKED).
        The decision must be either "APPROVED" or "REJECTED".
        If the decision is "APPROVED", it must include an approved_amount_usd.
        If the decision is "REJECTED", it must not include an approved_amount_usd.

        Raises:
            OptimisticConcurrencyError: If the application has not completed compliance checks.
            DomainError: If the decision is not "APPROVED" or "REJECTED", or if the approved_amount_usd is not provided when the decision is "APPROVED", or if it is provided when the decision is "REJECTED".
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError(
                "Decision requires compliance check first.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        if decision not in {"APPROVED", "REJECTED"}:
            raise DomainError("Decision must be APPROVED or REJECTED.")
        if decision == "APPROVED" and approved_amount_usd is None:
            raise DomainError(
                "Approved applications must include an approved_amount_usd."
            )
        if decision == "REJECTED" and approved_amount_usd is not None:
            raise DomainError(
                "Rejected applications must not include an approved_amount_usd."
            )

        payload = DecisionGeneratedPayload(
            decision=decision,
            approved_amount_usd=approved_amount_usd,
        )
        self._raise_event("DecisionGenerated", payload.model_dump())

    def require_human_review(self, reason: str):
        """
        Requires a human review for an application.

        Args:
            reason (str): The reason for requiring a human review.

        Raises:
            OptimisticConcurrencyError: If the application is not in the COMPLIANCE_CHECKED state.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError(
                "Application not ready for human review.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        payload = HumanReviewRequiredPayload(reason=reason)
        self._raise_event("HumanReviewRequired", payload.model_dump())

    def archive(self, archived_at: str):
        """
        Archives an application.

        Args:
            archived_at (str): The timestamp when the application was archived.

        Raises:
            OptimisticConcurrencyError: If the application is not in a DECIDED or HUMAN_REVIEW state.

        Returns:
            None
        """
        if self.state not in {ApplicationState.DECIDED, ApplicationState.HUMAN_REVIEW}:
            raise OptimisticConcurrencyError(
                "Application not ready for archive.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )
        payload = ApplicationArchivedPayload(archived_at=archived_at)
        self._raise_event("ApplicationArchived", payload.model_dump())

    def _raise_event(self, event_type: str, payload: dict):
        """
        Raises a domain event of the specified type with the given payload.

        Args:
            event_type (str): The type of event to be raised.
            payload (dict): The event payload.

        Returns:
            None
        """

        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions for command handlers ---
    def assert_not_submitted(self):
        """
        Asserts that the application is not yet submitted.

        Raises an OptimisticConcurrencyError if the application is not in the
        ApplicationState.NEW state.

        :raises: OptimisticConcurrencyError
        """
        if self.state != ApplicationState.NEW:
            raise OptimisticConcurrencyError(
                "Application already submitted.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_awaiting_credit_analysis(self):
        """
        Asserts that the application is awaiting credit analysis.

        Raises an OptimisticConcurrencyError if the application is not in the
        ApplicationState.SUBMITTED state.

        :raises: OptimisticConcurrencyError
        """
        if self.state != ApplicationState.SUBMITTED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting credit analysis.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_awaiting_fraud_screening(self):
        """
        Asserts that the application is awaiting fraud screening.

        Raises an OptimisticConcurrencyError if the application is not in the
        ApplicationState.CREDIT_ANALYSED state.

        :raises: OptimisticConcurrencyError
        """
        if self.state != ApplicationState.CREDIT_ANALYSED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting fraud screening.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_awaiting_compliance_check(self):
        """
        Asserts that the application is awaiting compliance check.

        Raises an OptimisticConcurrencyError if the application is not in the
        ApplicationState.FRAUD_SCREENED state.

        :raises: OptimisticConcurrencyError
        """
        if self.state != ApplicationState.FRAUD_SCREENED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting compliance check.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_ready_for_decision(self):
        """
        Asserts that the application is ready for decision.

        Raises:
            OptimisticConcurrencyError: If the application is not ready for decision.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError(
                "Application is not ready for decision.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_ready_for_archive(self):
        """
        Asserts that the application is ready for archive.

        Raises:
            OptimisticConcurrencyError: If the application is not ready for archive.
        """
        if self.state not in {ApplicationState.DECIDED, ApplicationState.HUMAN_REVIEW}:
            raise OptimisticConcurrencyError(
                "Application not ready for archive.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_ready_for_human_review(self):
        """
        Asserts that the application is ready for human review.

        Raises:
            OptimisticConcurrencyError: If the application is not ready for human review.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError(
                "Application not ready for human review.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )
