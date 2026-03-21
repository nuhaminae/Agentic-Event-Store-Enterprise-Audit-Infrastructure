# src/commands/handlers.py
# Command handlers

from src.aggregates.agent_session import AgentSessionAggregate
from src.aggregates.compliance_record import ComplianceRecordAggregate
from src.aggregates.loan_application import LoanApplicationAggregate


# --- Submit Application ---
async def handle_submit_application(cmd, store) -> None:
    """
    Handle a submit application command.

    This command creates a new loan application aggregate and
    submits the application with the given applicant ID and
    requested amount.

    :param cmd: SubmitApplicationCommand
    :param store: EventStore
    :return: None
    """
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    app.submit_application(cmd.applicant_id, cmd.requested_amount_usd)

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=app.events,
        expected_version=app.stream_position,
        correlation_id=cmd.correlation_id,
        causation_id=cmd.causation_id,
    )


# --- Credit Analysis Completed ---
async def handle_credit_analysis_completed(cmd, store) -> None:
    """
    Handle a credit analysis completed command.

    This command completes a credit analysis for an application
    and records the results of the analysis.

    :param cmd: CreditAnalysisCompletedCommand
    :param store: EventStore
    :return: None
    """
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


# --- Fraud Screening ---
async def handle_fraud_screening(cmd, store) -> None:
    """
    Handle a fraud screening command.

    This command completes a fraud screening for an application
    and records the results of the screening.

    :param cmd: FraudScreeningCommand
    :param store: EventStore
    :return: None
    """
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


# --- Compliance Check ---
async def handle_compliance_check(cmd, store) -> None:
    """
    Handle a compliance check command.

    This command records a compliance check for a compliance record.

    :param cmd: ComplianceCheckCommand
    :param store: EventStore
    :return: None
    """
    record = await ComplianceRecordAggregate.load(store, cmd.record_id)
    record.record_check(cmd.check_type)

    await store.append(
        stream_id=f"compliance-{cmd.record_id}",
        events=record.events,
        expected_version=record.stream_position,
        correlation_id=cmd.correlation_id,
        causation_id=cmd.causation_id,
    )


# --- Generate Decision ---
async def handle_generate_decision(cmd, store) -> None:
    """
    Handle a generate decision command.

    This command generates a decision for a loan application
    and records the results of the decision.

    :param cmd: GenerateDecisionCommand
    :param store: EventStore
    :return: None
    """
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    app.generate_decision(cmd.decision, cmd.approved_amount_usd)

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=app.events,
        expected_version=app.stream_position,
        correlation_id=cmd.correlation_id,
        causation_id=cmd.causation_id,
    )


# --- Human Review ---
async def handle_human_review(cmd, store) -> None:
    """
    Handle a human review command.

    This command records a human review request for a loan application
    and requires the application to be reviewed by a human.

    :param cmd: HumanReviewCommand
    :param store: EventStore
    :return: None
    """
    app = await LoanApplicationAggregate.load(store, cmd.application_id)
    app.require_human_review(cmd.reason)

    await store.append(
        stream_id=f"loan-{cmd.application_id}",
        events=app.events,
        expected_version=app.stream_position,
        correlation_id=cmd.correlation_id,
        causation_id=cmd.causation_id,
    )


# --- Start Agent Session ---
async def handle_start_agent_session(cmd, store) -> None:
    """
    Handle a start agent session command.

    This command starts a new agent session
    and records the results of the session.

    :param cmd: StartAgentSessionCommand
    :param store: EventStore
    :return: None
    """
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
