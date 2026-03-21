# src/aggregates/agent_session.py
# This is an agent session aggregate

from typing import Optional

from src.models.aggregates import (
    AgentSessionArchivedPayload,
    AgentSessionEndedPayload,
    AgentSessionStartedPayload,
    AgentSessionState,
)
from src.models.events import (
    BaseEvent,
    DomainError,
    OptimisticConcurrencyError,
    StoredEvent,
)


class AgentSessionAggregate:
    def __init__(self, session_id: str):
        """
        Initialises a new AgentSessionAggregate.

        Args:
            session_id (str): The unique identifier for this agent session.

        Attributes:
            session_id (str): The unique identifier for this agent session.
            state (AgentSessionState): The current state of the agent session.
            stream_position (int): The current position of the event stream.
            events (List[BaseEvent]): The list of events that have occurred in the agent session.
            agent_id (Optional[str]): The identifier of the agent that started this session.
            model_version (Optional[str]): The version of the model used in this session.
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

        Args:
            store (EventStore): The event store to load from.
            session_id (str): The unique identifier for this agent session.

        Returns:
            AgentSessionAggregate: The loaded AgentSessionAggregate.
        """
        events = await store.load_stream(f"agent-session-{session_id}")
        agg = cls(session_id)
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

        Returns:
            None
        """
        handler = getattr(self, f"_on_{event.event_type}", None)
        if handler:
            handler(event)
        self.stream_position = event.stream_position

    # --- Event Handlers ---
    def _on_AgentSessionStarted(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionStarted event to the aggregate.

        Args:
            event (StoredEvent): The stored event to apply.

        Notes:
            - Sets the state to ACTIVE.
            - Sets the agent_id, model_version, and started_at from the event payload.

        Returns:
            None
        """
        self.state = AgentSessionState.ACTIVE
        self.agent_id = event.payload["agent_id"]
        self.model_version = event.payload["model_version"]
        self.started_at = event.payload["started_at"]

    def _on_AgentSessionEnded(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionEnded event to the aggregate.

        Args:
            event (StoredEvent): The stored event to apply.

        Notes:
            - Sets the state to ENDED.
            - Sets the ended_at from the event payload.

        Returns:
            None
        """
        self.state = AgentSessionState.ENDED
        self.ended_at = event.payload["ended_at"]

    def _on_AgentSessionArchived(self, event: StoredEvent) -> None:
        """
        Applies an AgentSessionArchived event to the aggregate.

        Args:
            event (StoredEvent): The stored event to apply.

        Notes:
            - Sets the state to ARCHIVED.
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

        Args:
            agent_id (str): The identifier of the agent that started this session.
            model_version (str): The version of the model used in this session.
            started_at (str): The timestamp when the agent session was started.
            active_model_versions (list[str]): The list of model versions that are currently active.

        Raises:
            OptimisticConcurrencyError: If the session is already started.
            DomainError: If the model version already has an active session.

        Returns:
            None
        """
        if self.state != AgentSessionState.NEW:
            # raise OptimisticConcurrencyError("Session already started.")
            raise OptimisticConcurrencyError(
                "Session already started.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        if model_version in active_model_versions:
            raise DomainError(
                "Gas Town rule: model version already has an active session."
            )

        payload = AgentSessionStartedPayload(
            agent_id=agent_id, model_version=model_version, started_at=started_at
        )
        self._raise_event("AgentSessionStarted", payload.model_dump())

    def end_session(self, ended_at: str):
        """
        Ends an agent session.

        Args:
            ended_at (str): The timestamp when the agent session was ended.

        Raises:
            OptimisticConcurrencyError: If the session is not active.

        Returns:
            None
        """
        if self.state != AgentSessionState.ACTIVE:
            # raise OptimisticConcurrencyError("Only active sessions can be ended.")
            raise OptimisticConcurrencyError(
                "Only active sessions can be ended.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )
        payload = AgentSessionEndedPayload(ended_at=ended_at)
        self._raise_event("AgentSessionEnded", payload.model_dump())

    def archive(self, archived_at: str):
        """
        Archives an agent session.

        Args:
            archived_at (str): The timestamp when the agent session was archived.

        Raises:
            OptimisticConcurrencyError: If the session is not ended.

        Returns:
            None
        """
        if self.state != AgentSessionState.ENDED:
            # raise OptimisticConcurrencyError("Only ended sessions can be archived.")
            raise OptimisticConcurrencyError(
                "Only ended sessions can be archived.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

        payload = AgentSessionArchivedPayload(archived_at=archived_at)
        self._raise_event("AgentSessionArchived", payload.model_dump())

    def _raise_event(self, event_type: str, payload: dict):
        """
        Raises an event of the specified type with the given payload.

        Args:
            event_type (str): The type of the event to be raised.
            payload (dict): The payload of the event to be raised.

        Returns:
            None
        """
        event = BaseEvent(event_type=event_type, payload=payload, version=1)
        self.events.append(event)

    # --- Assertions ---
    def assert_context_loaded(self):
        """
        Asserts that the agent session context has been loaded.

        Raises:
            OptimisticConcurrencyError: If the agent session context has not been loaded.
        """
        if self.state != AgentSessionState.ACTIVE:
            raise OptimisticConcurrencyError(
                "Agent session context not loaded (Gas Town enforcement).",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )

    def assert_model_version_current(self, model_version: str):
        """
        Asserts that the model version of the agent session matches the given version.

        Args:
            model_version (str): The model version to be checked.

        Raises:
            OptimisticConcurrencyError: If the model version mismatch occurs.
        """
        if self.model_version != model_version:
            raise OptimisticConcurrencyError(
                "Model version mismatch — session locked to a different version.",
                expected_version=self.stream_position,
                actual_version=self.stream_position + 1,
            )
