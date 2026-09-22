"""Render a DecisionBrief as Markdown or a JSON-serializable dict."""

from __future__ import annotations

from app.models import DecisionBrief
from app.serialize import opportunity_to_dict


def _evidence_lines(label: str, evidence) -> list[str]:
    if not evidence:
        return [f"  - _{label}: none found_"]
    lines = [f"  - {label}:"]
    for item in evidence:
        lines.append(f'    - "{item.quote}" (row {item.source_row})')
    return lines


def render_brief_markdown(brief: DecisionBrief) -> str:
    lines = [
        "# Feedback Decision Brief",
        "",
        f"- Generated: {brief.generated_at}",
        f"- Total feedback items analyzed: {brief.total_feedback_items}",
        "- Evidence policy: every quote below is copied verbatim from the "
        "uploaded CSV; nothing is paraphrased or invented.",
        "",
        "## Opportunities",
        "",
    ]
    for opportunity in brief.opportunities:
        lines.append(f"### {opportunity.title}")
        lines.append("")
        lines.append(f"- Priority: **{opportunity.priority}**")
        lines.append(f"- Feedback items in this theme: {opportunity.count}")
        if opportunity.notes:
            lines.append(f"- Notes: {opportunity.notes}")
        lines.extend(_evidence_lines("Supporting evidence", opportunity.supporting_evidence))
        lines.extend(_evidence_lines("Conflicting evidence", opportunity.conflicting_evidence))
        lines.append("")
    return "\n".join(lines)


def render_brief_json(brief: DecisionBrief) -> dict:
    return {
        "session_id": brief.session_id,
        "generated_at": brief.generated_at,
        "total_feedback_items": brief.total_feedback_items,
        "opportunities": [opportunity_to_dict(o) for o in brief.opportunities],
    }