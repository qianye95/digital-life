"""Lifecycle feedback_layer migration manifest.

Owns result, error, audit, recovery, and state-signal feedback extracted from
Hermes lifecycle modules.
"""

from __future__ import annotations

from domain.core.models import LifecycleLayer, LifecycleSourceSlice
from .human_interaction import (
    NURTURE_KINDS,
    PATTERNS,
    merge_deltas,
    parse_message,
)
from .event_audit import feedback_from_event_audit
from .run_results import (
    feedback_from_blocked_execution,
    feedback_from_runtime_failure,
    feedback_from_runtime_result,
)
from .session_feedback import (
    feedback_from_proactive_report,
    feedback_from_session_summary,
)
from .vital_signals import feedback_from_vital_signal


LIFECYCLE_FEEDBACK_SLICES: tuple[LifecycleSourceSlice, ...] = (
    LifecycleSourceSlice(
        source_module="scheduler",
        layer=LifecycleLayer.FEEDBACK,
        target_package="domain.feedback.lifecycle_feedback.run_results",
        responsibility="Wake run timeout, empty response, rollback, auto-rest, and completion feedback.",
        adapter_boundary="Hermes runner returns outcomes; domain feedback decides recovery feedback.",
    ),
    LifecycleSourceSlice(
        source_module="memory_consolidation",
        layer=LifecycleLayer.FEEDBACK,
        target_package="domain.feedback.lifecycle_feedback.session_feedback",
        responsibility="Convert completed sessions and tool traces into feedback for memory consolidation.",
        adapter_boundary="Session DB is read through adapters, feedback is emitted to memory_layer services.",
    ),
    LifecycleSourceSlice(
        source_module="events",
        layer=LifecycleLayer.FEEDBACK,
        target_package="domain.feedback.lifecycle_feedback.event_audit",
        responsibility="Event consumption acknowledgement, dead-letter decisions, and audit trail.",
        adapter_boundary="Hermes event rows are acknowledged through package event feedback.",
    ),
    LifecycleSourceSlice(
        source_module="vitals",
        layer=LifecycleLayer.FEEDBACK,
        target_package="domain.feedback.lifecycle_feedback.vital_signals",
        responsibility="Vital threshold crossings, nurture logs, and body-state feedback signals.",
        adapter_boundary="Vitals produce feedback signals; orchestration decides whether to wake.",
    ),
    LifecycleSourceSlice(
        source_module="nurture",
        layer=LifecycleLayer.FEEDBACK,
        target_package="domain.feedback.lifecycle_feedback.human_interaction",
        responsibility="Human interaction deltas, relationship feedback, and inbound interaction audit.",
        adapter_boundary="Gateway emits interaction feedback before orchestration handoff.",
    ),
)


__all__ = [
    "LIFECYCLE_FEEDBACK_SLICES",
    "NURTURE_KINDS",
    "PATTERNS",
    "feedback_from_blocked_execution",
    "feedback_from_event_audit",
    "feedback_from_proactive_report",
    "feedback_from_runtime_failure",
    "feedback_from_runtime_result",
    "feedback_from_session_summary",
    "feedback_from_vital_signal",
    "parse_message",
    "merge_deltas",
]
