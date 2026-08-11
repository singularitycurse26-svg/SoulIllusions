"""
SoulIllusions Action Logger — Event-Sourced Telemetry System

Records every user interaction, API call, button press, tab switch,
generation, and system event in an append-only JSON log file.

Based on event-sourcing and audit-log design patterns:
- Every event is an immutable fact (append-only, never modified)
- Structured JSON format (machine-parseable)
- Captures: who, what, when, where, on what, result, context
- Frontend events logged via /api/log endpoint
- Backend events logged via middleware + explicit calls
- Separate file for AI review and upgrade planning

Usage:
    from action_logger import ActionLogger
    logger = ActionLogger()
    logger.log("video.generate", {"model": "ltx", "prompt": "..."}, source="user")
"""

import json
import os
import time
import uuid
import threading
from datetime import datetime, timezone
from collections import deque
from typing import Optional


class ActionLogger:
    """Append-only event-sourced action logger for SoulIllusions."""

    def __init__(self, log_dir: str = None, enabled: bool = True):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)

        self.log_path = os.path.join(log_dir, "action_log.jsonl")
        self.upgrade_notes_path = os.path.join(log_dir, "upgrade_notes.md")
        self.enabled = enabled
        self._lock = threading.Lock()
        self._buffer = deque(maxlen=500)
        self._stats = {
            "total_events": 0,
            "events_by_category": {},
            "events_by_source": {},
            "errors": 0,
            "last_event_time": None,
        }

        if self.enabled:
            self._log_internal("system", "logger.started", {
                "log_path": self.log_path,
                "upgrade_notes_path": self.upgrade_notes_path,
            })

    def _log_internal(self, source: str, action: str, detail: dict, result: str = "success"):
        event = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "epoch": time.time(),
            "source": source,
            "action": action,
            "result": result,
            "detail": detail,
        }
        with self._lock:
            self._buffer.append(event)
            self._stats["total_events"] += 1
            self._stats["last_event_time"] = event["timestamp"]
            cat = action.split(".")[0] if "." in action else action
            self._stats["events_by_category"][cat] = self._stats["events_by_category"].get(cat, 0) + 1
            self._stats["events_by_source"][source] = self._stats["events_by_source"].get(source, 0) + 1
            if result == "failure":
                self._stats["errors"] += 1

            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                pass

        return event

    def log(self, action: str, detail: dict = None, source: str = "user", result: str = "success"):
        """Log an action event.

        Args:
            action: Dot-notation action name (e.g. 'video.generate', 'ui.button_click')
            detail: Dictionary of contextual data about the action
            source: Who/what triggered the action ('user', 'ai', 'system', 'api')
            result: 'success' or 'failure'
        """
        if not self.enabled:
            return None
        return self._log_internal(source, action, detail or {}, result)

    def log_ui(self, event_type: str, element_id: str, element_type: str = "button",
               value: str = None, page: str = None, extra: dict = None):
        """Log a frontend UI interaction.

        Args:
            event_type: 'click', 'change', 'input', 'focus', 'submit', 'switch'
            element_id: ID of the DOM element interacted with
            element_type: 'button', 'select', 'input', 'textarea', 'tab', 'slider'
            value: Current value of the element (if applicable)
            page: Which tab/section the user is on
            extra: Additional context
        """
        detail = {
            "event_type": event_type,
            "element_id": element_id,
            "element_type": element_type,
            "page": page or "unknown",
        }
        if value is not None:
            detail["value"] = value
        if extra:
            detail.update(extra)
        return self.log(f"ui.{event_type}", detail, source="user")

    def log_api(self, method: str, path: str, status_code: int = 200,
                duration_ms: float = 0, body_summary: dict = None, error: str = None):
        """Log a backend API call."""
        detail = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        if body_summary:
            detail["body"] = body_summary
        if error:
            detail["error"] = error
        result = "success" if status_code < 400 else "failure"
        return self.log(f"api.{method.lower()}", detail, source="api", result=result)

    def log_generation(self, model: str, prompt: str, style: str, frames: int,
                       fps: int, steps: int, seed: int = None, job_id: str = None,
                       status: str = "started", error: str = None):
        """Log a video generation event."""
        detail = {
            "model": model,
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "style": style,
            "frames": frames,
            "fps": fps,
            "steps": steps,
            "seed": seed,
            "job_id": job_id,
            "status": status,
        }
        if error:
            detail["error"] = error
        return self.log(f"video.generate", detail, source="system",
                       result="success" if status != "failed" else "failure")

    def log_production(self, action: str, entity_type: str, entity_id: str = None,
                       data: dict = None, result: str = "success"):
        """Log a production suite action (series, episode, scene operations)."""
        detail = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "data": data,
        }
        return self.log(f"production.{action}", detail, source="user", result=result)

    def note_upgrade_idea(self, idea: str, context: dict = None, severity: str = "info"):
        """Write an upgrade note for AI review.

        Args:
            idea: Description of the upgrade idea or observation
            context: Additional context data
            severity: 'info', 'suggestion', 'bug', 'critical'
        """
        if not self.enabled:
            return
        timestamp = datetime.now(timezone.utc).isoformat()
        entry = f"\n## [{severity.upper()}] {timestamp}\n{idea}\n"
        if context:
            entry += f"**Context:** `{json.dumps(context, ensure_ascii=False)}`\n"
        try:
            with self._lock:
                with open(self.upgrade_notes_path, "a", encoding="utf-8") as f:
                    f.write(entry)
        except Exception:
            pass
        self.log("upgrade.note", {"idea": idea, "severity": severity, "context": context},
                source="ai")

    def get_recent_events(self, count: int = 50, category: str = None,
                          source: str = None) -> list:
        """Get recent events from the in-memory buffer."""
        events = list(self._buffer)
        if category:
            events = [e for e in events if e["action"].startswith(category)]
        if source:
            events = [e for e in events if e["source"] == source]
        return events[-count:]

    def get_stats(self) -> dict:
        """Get logging statistics."""
        return {
            **self._stats,
            "enabled": self.enabled,
            "log_path": self.log_path,
            "buffer_size": len(self._buffer),
        }

    def read_log_file(self, lines: int = 100, offset: int = 0) -> list:
        """Read events from the log file."""
        if not os.path.exists(self.log_path):
            return []
        events = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
            start = max(0, len(all_lines) - offset - lines)
            end = len(all_lines) - offset
            for line in all_lines[start:end]:
                if line.strip():
                    try:
                        events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        return events

    def search_events(self, action_contains: str = None, source: str = None,
                      result: str = None, limit: int = 50) -> list:
        """Search the in-memory buffer for matching events."""
        matches = []
        for event in reversed(self._buffer):
            if action_contains and action_contains not in event["action"]:
                continue
            if source and event["source"] != source:
                continue
            if result and event["result"] != result:
                continue
            matches.append(event)
            if len(matches) >= limit:
                break
        return matches

    def clear_log(self):
        """Clear the log file (use with caution)."""
        with self._lock:
            try:
                open(self.log_path, "w").close()
                self._buffer.clear()
                self._stats = {
                    "total_events": 0,
                    "events_by_category": {},
                    "events_by_source": {},
                    "errors": 0,
                    "last_event_time": None,
                }
            except Exception:
                pass
        self.log("logger.cleared", {}, source="system")

    def set_enabled(self, enabled: bool):
        """Enable or disable logging (for performance)."""
        self.enabled = enabled
        if enabled:
            self.log("logger.enabled", {}, source="system")
        else:
            # Log one final event before disabling
            self._log_internal("system", "logger.disabled", {})
            self.enabled = False


# Global singleton instance
_logger_instance = None
_logger_lock = threading.Lock()


def get_logger() -> ActionLogger:
    """Get the global ActionLogger instance."""
    global _logger_instance
    if _logger_instance is None:
        with _logger_lock:
            if _logger_instance is None:
                _logger_instance = ActionLogger()
    return _logger_instance
