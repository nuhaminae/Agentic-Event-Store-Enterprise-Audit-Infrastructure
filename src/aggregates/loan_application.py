# src/aggregates/loan_application.py
# This is a loan application aggregate

from typing import Optional

from src.models.aggregates import ApplicationState
from src.models.events import BaseEvent, OptimisticConcurrencyError, StoredEvent


class LoanApplicationAggregate:
    def __init__(self, application_id: str):
        """
        Initialise a new LoanApplicationAggregate.

        Args:
            application_id (str): The identifier for the loan application.

        Attributes:
            application_id (str): The identifier for the loan application.
            state (ApplicationState): The current state of the loan application.
            stream_position (int): The current position in the event stream.
            events (List[BaseEvent]): The list of events in the loan application.
            applicant_id (Optional[str]): The identifier for the applicant.
            requested_amount (Optional[float]): The requested amount for the loan.
            approved_amount (Optional[float]): The approved amount for the loan.
            decision (Optional[str]): The decision for the loan application.
            archived_at (Optional[str]): The timestamp when the loan application was archived.
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

        Args:
            store (EventStore): The event store.
            application_id (str): The identifier for the loan application.

        Returns:
            LoanApplicationAggregate: The loaded aggregate.
        """
        events = await store.load_stream(f"loan-{application_id}")
        agg = cls(application_id)
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
    def _on_ApplicationSubmitted(self, event: StoredEvent) -> None:
        """
        Applies an ApplicationSubmitted event to the aggregate, updating its state and applicant information.

        The `_on_ApplicationSubmitted` method takes an ApplicationSubmitted event as input and applies it to the aggregate.
        It first updates the aggregate's state to `ApplicationState.SUBMITTED`.
        Then, it updates the aggregate's `applicant_id` and `requested_amount` fields from the event payload.
        """
        self.state = ApplicationState.SUBMITTED
        self.applicant_id = event.payload["applicant_id"]
        self.requested_amount = event.payload["requested_amount_usd"]

    def _on_CreditAnalysisCompleted(self, event: StoredEvent) -> None:
        """
        Applies a CreditAnalysisCompleted event to the aggregate, updating its state.

        The `_on_CreditAnalysisCompleted` method takes a CreditAnalysisCompleted event as input and applies it to the aggregate.
        It updates the aggregate's state to `ApplicationState.CREDIT_ANALYZED`.
        """

        self.state = ApplicationState.CREDIT_ANALYZED

    def _on_FraudScreeningCompleted(self, event: StoredEvent) -> None:
        """
        Applies a FraudScreeningCompleted event to the aggregate, updating its state.

        The `_on_FraudScreeningCompleted` method takes a FraudScreeningCompleted event as input and applies it to the aggregate.
        It updates the aggregate's state to `ApplicationState.FRAUD_SCREENED`.
        """
        self.state = ApplicationState.FRAUD_SCREENED

    def _on_ComplianceCheckCompleted(self, event: StoredEvent) -> None:
        """
        Applies a ComplianceCheckCompleted event to the aggregate, updating its state.

        The `_on_ComplianceCheckCompleted` method takes a ComplianceCheckCompleted event as input and applies it to the aggregate.
        It updates the aggregate's state to `ApplicationState.COMPLIANCE_CHECKED`.
        """
        self.state = ApplicationState.COMPLIANCE_CHECKED

    def _on_DecisionGenerated(self, event: StoredEvent) -> None:
        """
        Applies a DecisionGenerated event to the aggregate, updating its state and decision information.

        The `_on_DecisionGenerated` method takes a DecisionGenerated event as input and applies it to the aggregate.
        It first updates the aggregate's state to `ApplicationState.DECIDED`.
        Then, it updates the aggregate's `decision` and `approved_amount` fields from the event payload.
        """
        self.state = ApplicationState.DECIDED
        self.decision = event.payload["decision"]
        self.approved_amount = event.payload.get("approved_amount_usd")

    def _on_HumanReviewRequired(self, event: StoredEvent) -> None:
        """
        Applies a HumanReviewRequired event to the aggregate, updating its state.

        The `_on_HumanReviewRequired` method takes a HumanReviewRequired event as input and applies it to the aggregate.
        It updates the aggregate's state to `ApplicationState.HUMAN_REVIEW`.
        """
        self.state = ApplicationState.HUMAN_REVIEW

    def _on_ApplicationArchived(self, event: StoredEvent) -> None:
        """
        Applies an ApplicationArchived event to the aggregate, updating its state and archived_at field.

        The `_on_ApplicationArchived` method takes an ApplicationArchived event as input and applies it to the aggregate.
        It updates the aggregate's state to `ApplicationState.ARCHIVED` and sets the `archived_at` field to the value from the event payload.
        """
        self.state = ApplicationState.ARCHIVED
        self.archived_at = event.payload["archived_at"]

    # --- Commands ---
    def submit_application(self, applicant_id: str, requested_amount_usd: float):
        """
        Submits a loan application.

        The `submit_application` method submits a loan application with the given applicant_id and requested_amount_usd.
        It raises an OptimisticConcurrencyError if the application is already submitted.

        Args:
            applicant_id (str): The identifier for the applicant.
            requested_amount_usd (float): The requested amount for the loan in USD.

        Raises:
            OptimisticConcurrencyError: If the application is already submitted.
        """
        if self.state != ApplicationState.NEW:
            raise OptimisticConcurrencyError("Application already submitted.")
        self._raise_event(
            "ApplicationSubmitted",
            {
                "applicant_id": applicant_id,
                "requested_amount_usd": requested_amount_usd,
            },
        )

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

        The `credit_analysis_completed` method records a credit analysis result for an application with the given
        agent_id, session_id, model_version, confidence_score, risk_tier, recommended_limit_usd, duration_ms, and
        input_data_hash.

        It raises an OptimisticConcurrencyError if the application is not awaiting credit analysis.

        Args:
            agent_id (str): The identifier for the agent.
            session_id (str): The identifier for the session.
            model_version (str): The version of the credit analysis model.
            confidence_score (float): The confidence score of the credit analysis model.
            risk_tier (str): The risk tier of the credit analysis model.
            recommended_limit_usd (float): The recommended limit for the loan in USD.
            duration_ms (int): The duration of the credit analysis in milliseconds.
            input_data_hash (Optional[str]): The hash of the input data used for the credit analysis.

        Raises:
            OptimisticConcurrencyError: If the application is not awaiting credit analysis.
        """
        if self.state != ApplicationState.SUBMITTED:
            raise OptimisticConcurrencyError(
                "Application not awaiting credit analysis."
            )
        self._raise_event(
            "CreditAnalysisCompleted",
            {
                "application_id": self.application_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "model_version": model_version,
                "confidence_score": confidence_score,
                "risk_tier": risk_tier,
                "recommended_limit_usd": recommended_limit_usd,
                "analysis_duration_ms": duration_ms,
                "input_data_hash": input_data_hash,
            },
        )

    def fraud_screening_completed(self, result: str):
        """
        Records a fraud screening result for an application.

        The `fraud_screening_completed` method records a fraud screening result for an application with the given result.

        It raises an OptimisticConcurrencyError if the application is not awaiting fraud screening.

        Args:
            result (str): The result of the fraud screening.

        Raises:
            OptimisticConcurrencyError: If the application is not awaiting fraud screening.
        """
        if self.state != ApplicationState.CREDIT_ANALYZED:
            raise OptimisticConcurrencyError(
                "Application not awaiting fraud screening."
            )
        self._raise_event(
            "FraudScreeningCompleted",
            {"application_id": self.application_id, "result": result},
        )

    def generate_decision(
        self, decision: str, approved_amount_usd: Optional[float] = None
    ):
        """
        Generates a decision for the application.

        The `generate_decision` method records a decision for the application with the given decision and approved amount in USD.

        It raises an OptimisticConcurrencyError if the application is not awaiting compliance check.

        It raises a ValueError if the decision is not "APPROVED" or "REJECTED".

        If the decision is "APPROVED", it must include an approved_amount_usd.

        If the decision is "REJECTED", it must not include an approved_amount_usd.

        Args:
            decision (str): The decision for the application.
            approved_amount_usd (Optional[float]): The approved amount in USD for the application.

        Raises:
            OptimisticConcurrencyError: If the application is not awaiting compliance check.
            ValueError: If the decision is not "APPROVED" or "REJECTED".
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError(
                "Decision requires compliance check first."
            )
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("Decision must be APPROVED or REJECTED.")
        if decision == "APPROVED" and approved_amount_usd is None:
            raise ValueError(
                "Approved applications must include an approved_amount_usd."
            )
        if decision == "REJECTED" and approved_amount_usd is not None:
            raise ValueError(
                "Rejected applications must not include an approved_amount_usd."
            )
        self._raise_event(
            "DecisionGenerated",
            {"decision": decision, "approved_amount_usd": approved_amount_usd},
        )

    def require_human_review(self, reason: str):
        """
        Records a human review request for an application.

        The `require_human_review` method records a human review request for an application with the given reason.

        It raises an OptimisticConcurrencyError if the application is not awaiting compliance check.

        Args:
            reason (str): The reason for the human review request.

        Raises:
            OptimisticConcurrencyError: If the application is not awaiting compliance check.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError("Application not ready for human review.")
        self._raise_event("HumanReviewRequired", {"reason": reason})

    def archive(self, archived_at: str):
        """
        Archives an application, marking it as archived.

        Raises an OptimisticConcurrencyError if the application is not in the DECIDED or HUMAN_REVIEW state.

        Args:
            archived_at (str): The timestamp when the application was archived.
        """
        if self.state not in {ApplicationState.DECIDED, ApplicationState.HUMAN_REVIEW}:
            raise OptimisticConcurrencyError("Application not ready for archive.")
        self._raise_event("ApplicationArchived", {"archived_at": archived_at})

    def _raise_event(self, event_type: str, payload: dict):
        """
        Raises an event of the specified type with the given payload.

        The event is appended to the aggregate's events list.

        Args:
            event_type (str): The type of event to raise.
            payload (dict): The event payload.
        """
        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions for command handlers ---
    def assert_not_submitted(self):
        """
        Asserts that the application has not been submitted.

        Raises an OptimisticConcurrencyError if the application is not in the NEW state.

        This assertion is used to ensure that the application has not been submitted before attempting to submit it.
        """
        if self.state != ApplicationState.NEW:
            raise OptimisticConcurrencyError("Application already submitted.")

    def assert_awaiting_credit_analysis(self):
        """
        Asserts that the application is awaiting credit analysis.

        Raises an OptimisticConcurrencyError if the application is not in the SUBMITTED state.

        This assertion is used to ensure that the application is awaiting credit analysis before attempting to record a credit analysis result.
        """
        if self.state != ApplicationState.SUBMITTED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting credit analysis."
            )

    def assert_awaiting_fraud_screening(self):
        """
        Asserts that the application is awaiting fraud screening.

        Raises an OptimisticConcurrencyError if the application is not in the CREDIT_ANALYZED state.

        This assertion is used to ensure that the application is awaiting fraud screening before attempting to record a fraud screening result.
        """
        if self.state != ApplicationState.CREDIT_ANALYZED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting fraud screening."
            )

    def assert_awaiting_compliance_check(self):
        """
        Asserts that the application is awaiting compliance check.

        Raises an OptimisticConcurrencyError if the application is not in the FRAUD_SCREENED state.

        This assertion is used to ensure that the application is awaiting compliance check before attempting to record a compliance check result.
        """
        if self.state != ApplicationState.FRAUD_SCREENED:
            raise OptimisticConcurrencyError(
                "Application is not awaiting compliance check."
            )

    def assert_ready_for_decision(self):
        """
        Asserts that the application is ready for decision.

        Raises an OptimisticConcurrencyError if the application is not in the COMPLIANCE_CHECKED state.

        This assertion is used to ensure that the application is ready for decision before attempting to generate a decision.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError("Application is not ready for decision.")

    def assert_ready_for_archive(self):
        """
        Asserts that the application is ready for archive.

        Raises an OptimisticConcurrencyError if the application is not in the DECIDED or HUMAN_REVIEW state.

        This assertion is used to ensure that the application is ready for archive before attempting to archive it.
        """
        if self.state not in {ApplicationState.DECIDED, ApplicationState.HUMAN_REVIEW}:
            raise OptimisticConcurrencyError("Application not ready for archive.")

    def assert_ready_for_human_review(self):
        """
        Asserts that the application is ready for human review.

        Raises an OptimisticConcurrencyError if the application is not in the COMPLIANCE_CHECKED state.

        This assertion is used to ensure that the application is ready for human review before attempting to record a human review result.
        """
        if self.state != ApplicationState.COMPLIANCE_CHECKED:
            raise OptimisticConcurrencyError("Application not ready for human review.")
