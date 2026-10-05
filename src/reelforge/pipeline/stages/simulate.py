"""Stage 4 Call Simulator for ReelForge.
Defines CallSimulator interface, ScriptedSimulator implementation, and LiveAgentSimulator stub.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from reelforge.pipeline.stages.dialogue import CallEvent, DialogueScript, DialogueTurn
from reelforge.pipeline.stages.profile import BusinessProfile


class SimulatedTurn(BaseModel):
    speaker: str
    text: str
    emotion: str
    pause_after_ms: int
    on_screen_event: Optional[str] = None


class SimulatedCall(BaseModel):
    turns: List[SimulatedTurn]
    events: List[CallEvent]
    owner_notification: Dict[str, Any]
    hook_text: str
    cta_text: str
    tool_call_trace: List[Dict[str, Any]] = []


class CallSimulator(ABC):
    @abstractmethod
    def run(self, script: DialogueScript, profile: BusinessProfile) -> SimulatedCall:
        """Execute simulated telephone dialogue."""
        pass


class ScriptedSimulator(CallSimulator):
    """Executes call simulation from the approved dialogue script."""

    def run(self, script: DialogueScript, profile: BusinessProfile) -> SimulatedCall:
        simulated_turns = [
            SimulatedTurn(
                speaker=t.speaker,
                text=t.text,
                emotion=t.emotion,
                pause_after_ms=t.pause_after_ms,
                on_screen_event=t.on_screen_event,
            )
            for t in script.turns
        ]

        trace = [
            {"turn": e.turn_index, "event_type": e.type, "payload": e.text}
            for e in script.events
        ]

        return SimulatedCall(
            turns=simulated_turns,
            events=script.events,
            owner_notification=script.owner_notification.model_dump(),
            hook_text=script.hook_text,
            cta_text=script.cta_text,
            tool_call_trace=trace,
        )


class LiveAgentSimulator(CallSimulator):
    """Extension stub for driving real live voice receptionist endpoints with scripted caller policies."""

    def __init__(
        self,
        agent_endpoint: str = "http://localhost:8080/v1/voice/call",
        caller_policy: str = "scripted_persona",
        max_turns: int = 12,
    ):
        self.agent_endpoint = agent_endpoint
        self.caller_policy = caller_policy
        self.max_turns = max_turns

    def run(self, script: DialogueScript, profile: BusinessProfile) -> SimulatedCall:
        # Stub for live streaming telephony endpoint integration
        raise NotImplementedError(
            "LiveAgentSimulator is an extension point for live telephony testing. Use ScriptedSimulator for offline video rendering."
        )
