"""In-memory session store.

Deliberate MVP limitation: state lives in process memory only and is lost
on restart. Fine for the "one weekly batch, one small team" workflow the
PRD scopes to; documented in README.md as the first thing to fix before
this becomes a shared/multi-user tool.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.models import FeedbackItem, Opportunity, Theme
from app.opportunities import derive_opportunities, opportunity_title_for_theme


@dataclass
class Session:
    id: str
    items: list[FeedbackItem]
    items_by_id: dict[str, FeedbackItem]
    themes: list[Theme]
    opportunities: list[Opportunity]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class SessionNotFound(KeyError):
    pass


class ThemeNotFound(KeyError):
    pass


class SessionStore:
    """A process-wide, in-memory session table."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def create(self, items: list[FeedbackItem], themes: list[Theme]) -> Session:
        session_id = str(uuid.uuid4())
        items_by_id = {item.id: item for item in items}
        session = Session(
            id=session_id,
            items=items,
            items_by_id=items_by_id,
            themes=themes,
            # Computed once at creation time; priorities set later mutate
            # these same Opportunity objects in place (see priorities.py),
            # so a rename must patch titles rather than ever recomputing
            # this list from scratch — that would silently drop priorities.
            opportunities=derive_opportunities(themes, items_by_id),
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise SessionNotFound(session_id) from exc

    def rename_theme(self, session_id: str, theme_id: str, label: str) -> Theme:
        session = self.get(session_id)
        clean_label = label.strip()
        for theme in session.themes:
            if theme.id == theme_id:
                theme.label = clean_label or theme.label
                for opportunity in session.opportunities:
                    if opportunity.theme_id == theme_id:
                        opportunity.title = opportunity_title_for_theme(theme)
                return theme
        raise ThemeNotFound(theme_id)

    def clear(self) -> None:
        """Test-only helper to reset state between test cases."""
        self._sessions.clear()


# One process-wide store, shared by the FastAPI app.
store = SessionStore()
