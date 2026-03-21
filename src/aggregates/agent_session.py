# src/aggregates/agent_session.py
# This is a agent session aggregate

from typing import Optional

from src.models.aggregates import AgentSessionState
from src.models.events import BaseEvent, OptimisticConcurrencyError, StoredEvent


class AgentSessionAggregate:
    def __init__(self, session_id: str):
        """
        Initialise a new AgentSessionAggregate.

        Args:
            session_id (str): The identifier for the agent session.

        Attributes:
            session_id (str): The identifier for the agent session.
            state (AgentSessionState): The current state of the agent session.
            stream_position (int): The current position in the event stream.
            events (list[BaseEvent]): The list of events in the agent session.
            agent_id (Optional[str]): The identifier for the agent.
            model_version (Optional[str]): The version of the model used for the agent session.
            started_at (Optional[str]): The timestamp when the agent session was started.
            ended_at (Optional[str]): The timestamp when the agent session was ended.
        """
        self.session_id = session_id
        self.state: AgentSessionState = AgentSessionState.NEW
        self.stream_position: int = 0
        self.events: list[BaseEvent] = []
        self.agent_id: Optional[str] = None
        self.model_version: Optional[str] = None
        self.started_at: Optional[str] = None
        self.ended_at: Optional[str] = None

    @classmethod
    async def load(cls, store, session_id: str) -> "AgentSessionAggregate":
        """
        Loads an AgentSessionAggregate from the event store.
        """
        events = await store.load_stream(f"agent-session-{session_id}")
        agg = cls(session_id)
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
    def _on_AgentSessionStarted(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionStarted event to the aggregate, updating its state and started_at field.

        The `_on_AgentSessionStarted` method takes an AgentSessionStarted event as input and applies it to the aggregate.
        It first updates the aggregate's state to `AgentSessionState.ACTIVE`.
        Then, it updates the aggregate's `agent_id` and `model_version` fields from the event payload.
        Finally, it updates the aggregate's `started_at` field from the event payload.
        """
        self.state = AgentSessionState.ACTIVE
        self.agent_id = event.payload["agent_id"]
        self.model_version = event.payload["model_version"]
        self.started_at = event.payload["started_at"]

    def _on_AgentSessionEnded(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionEnded event to the aggregate, updating its state and ended_at field.

        The `_on_AgentSessionEnded` method takes an AgentSessionEnded event as input and applies it to the aggregate.
        It first updates the aggregate's state to `AgentSessionState.ENDED`.
        Then, it updates the aggregate's `ended_at` field from the event payload.
        """
        self.state = AgentSessionState.ENDED
        self.ended_at = event.payload["ended_at"]

    def _on_AgentSessionArchived(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionArchived event to the aggregate, updating its state to ARCHIVED.

        The `_on_AgentSessionArchived` method takes an AgentSessionArchived event as input and applies it to the aggregate.
        It updates the aggregate's state to `AgentSessionState.ARCHIVED`.

        """
        self.state = AgentSessionState.ARCHIVED

    # --- Commands ---
    def start_session(
        self,
        agent_id: str,
        model_version: str,
        started_at: str,
        active_model_versions: list[str],
    ):
        """
        Starts a new agent session.

        Raises an OptimisticConcurrencyError if the session is not in the NEW state or
        if the model version already has an active session (Gas Town rule).

        :return: None
        :rtype: None
        """
        if self.state != AgentSessionState.NEW:
            raise OptimisticConcurrencyError("Session already started.")
        if model_version in active_model_versions:
            raise OptimisticConcurrencyError(
                "Gas Town rule: model version already has an active session."
            )
        self._raise_event(
            "AgentSessionStarted",
            {
                "agent_id": agent_id,
                "model_version": model_version,
                "started_at": started_at,
            },
        )

    def end_session(self, ended_at: str):
        """
        Ends an agent session, marking it as ended.

        Raises an OptimisticConcurrencyError if the session is not in the ACTIVE state.

        """
        if self.state != AgentSessionState.ACTIVE:
            raise OptimisticConcurrencyError("Only active sessions can be ended.")
        self._raise_event("AgentSessionEnded", {"ended_at": ended_at})

    def archive(self, archived_at: str):
        """
        Archives an agent session, marking it as archived.

        Raises an OptimisticConcurrencyError if the session is not in the ENDED state.
        """
        if self.state != AgentSessionState.ENDED:
            raise OptimisticConcurrencyError("Only ended sessions can be archived.")
        self._raise_event("AgentSessionArchived", {"archived_at": archived_at})

    def _raise_event(self, event_type: str, payload: dict):
        # schema version fixed at 1
        """
        Raises an event of the specified type with the given payload.

        The event is appended to the aggregate's events list.

        """
        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions ---
    def assert_context_loaded(self):
        """
        Asserts that the agent session context has been loaded.

        Raises an OptimisticConcurrencyError if the session is not in the ACTIVE state.

        This is a Gas Town enforcement, ensuring that the agent session context is loaded
        before any operations can be performed on the session.
        """
        if self.state != AgentSessionState.ACTIVE:
            raise OptimisticConcurrencyError(
                "Agent session context not loaded (Gas Town enforcement)."
            )

    def assert_model_version_current(self, model_version: str):
        """
        Asserts that the provided model version matches the model version stored in the session.

        Raises an OptimisticConcurrencyError if the model version does not match.

        This is a Gas Town enforcement, ensuring that the model version used in the
        session matches the model version used in the operation.
        """
        if self.model_version != model_version:
            raise OptimisticConcurrencyError(
                "Model version mismatch — session locked to a different version."
            )
