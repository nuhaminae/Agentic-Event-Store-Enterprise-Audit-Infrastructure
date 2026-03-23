# src/commands/handlers.py
# Command handlers

from src.aggregates.agent_session import AgentSessionAggregate
from src.aggregates.compliance_record import ComplianceRecordAggregate
from src.aggregates.loan_application import LoanApplicationAggregate
from src.models.events import DomainError, OptimisticConcurrencyError


# --- Submit Application ---
async def handle_submit_application(cmd, store) -> dict:
    """
    Handles the SubmitApplication command.

    Args:
        cmd (SubmitApplicationCommand): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        app = await LoanApplicationAggregate.load(store, cmd.application_id)
        app.submit_application(cmd.applicant_id, cmd.requested_amount_usd)

        await store.append(
            stream_id=f"loan-{cmd.application_id}",
            events=app.events,
            expected_version=app.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Credit Analysis Completed ---
async def handle_credit_analysis_completed(cmd, store) -> dict:
    """
    Handles the CreditAnalysisCompleted command.

    Args:
        cmd (CreditAnalysisCompletedCommand): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """

    try:
        app = await LoanApplicationAggregate.load(store, cmd.application_id)
        agent = await AgentSessionAggregate.load(store, cmd.session_id)

        # enforce Gas Town rules
        app.assert_awaiting_credit_analysis()
        agent.assert_context_loaded()
        agent.assert_model_version_current(cmd.model_version)

        app.credit_analysis_completed(
            agent_id=cmd.agent_id,
            session_id=cmd.session_id,
            model_version=cmd.model_version,
            confidence_score=cmd.confidence_score,
            risk_tier=cmd.risk_tier,
            recommended_limit_usd=cmd.recommended_limit_usd,
            duration_ms=cmd.duration_ms,
            input_data_hash=cmd.input_data_hash,
        )

        await store.append(
            stream_id=f"loan-{cmd.application_id}",
            events=app.events,
            expected_version=app.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Fraud Screening ---
async def handle_fraud_screening(cmd, store) -> dict:
    """
    Handles the FraudScreening command.

    Args:
        cmd (FraudScreeningCommand): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        app = await LoanApplicationAggregate.load(store, cmd.application_id)

        # enforce Gas Town rules
        app.assert_awaiting_fraud_screening()
        app.fraud_screening_completed(result=cmd.result)

        await store.append(
            stream_id=f"loan-{cmd.application_id}",
            events=app.events,
            expected_version=app.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Compliance Check ---
async def handle_compliance_check(cmd, store) -> dict:
    """
    Handles the ComplianceCheck command.

    Args:
        cmd (ComplianceCheckCommand): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        record = await ComplianceRecordAggregate.load(store, cmd.compliance_id)
        record.record_check(cmd.check_type)

        await store.append(
            stream_id=f"compliance-{cmd.compliance_id}",
            events=record.events,
            expected_version=record.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Generate Decision ---
async def handle_generate_decision(cmd, store) -> dict:
    """
    Handles the GenerateDecision command.

    Args:
        cmd (GenerateDecision): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        app = await LoanApplicationAggregate.load(store, cmd.application_id)
        app.generate_decision(cmd.decision, cmd.approved_amount_usd)

        await store.append(
            stream_id=f"loan-{cmd.application_id}",
            events=app.events,
            expected_version=app.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Human Review ---
async def handle_human_review(cmd, store) -> dict:
    """
    Handles the HumanReview command.

    Args:
        cmd (HumanReview): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the command is invalid.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        app = await LoanApplicationAggregate.load(store, cmd.application_id)
        app.require_human_review(cmd.reason)

        await store.append(
            stream_id=f"loan-{cmd.application_id}",
            events=app.events,
            expected_version=app.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}


# --- Start Agent Session ---
async def handle_start_agent_session(cmd, store) -> dict:
    """
    Handles the StartAgentSession command.

    Args:
        cmd (StartAgentSession): The command to handle.
        store (EventStore): The event store to persist events to.

    Returns:
        dict: A dictionary containing the status and message of the command handling result.

    Raises:
        DomainError: If the agent session is already started.
        OptimisticConcurrencyError: If the event store version does not match the expected version.
    """
    try:
        agent = await AgentSessionAggregate.load(store, cmd.session_id)
        agent.start_session(
            cmd.agent_id, cmd.model_version, cmd.started_at, cmd.active_model_versions
        )

        await store.append(
            stream_id=f"agent-session-{cmd.session_id}",
            events=agent.events,
            expected_version=agent.stream_position,
            correlation_id=cmd.correlation_id,
            causation_id=cmd.causation_id,
        )
        return {"status": "success"}
    except DomainError as e:
        return {"status": "domain_error", "message": str(e)}
    except OptimisticConcurrencyError as e:
        return {"status": "concurrency_error", "message": str(e)}
