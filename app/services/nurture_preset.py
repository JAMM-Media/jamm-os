# app/services/nurture_preset.py
"""
Seeds the 75-node acquisition nurture preset tree (plus the D7 dead-end addition)
as real Sequence/SequenceVersion/Step/StepEdge/SequenceGoal data.

Source of truth: docs/jamm_nurture_preset_tree.html -- parsed here directly, not
hand-transcribed. Structure is complete and inert at seed time; actual email sends
require a future task to wire email-type steps to the send service.

Judgment calls baked in (made by Ben, not to be re-derived):
- 19 "wait" nodes mapped to wait_fixed or wait_until_event per the task spec table.
- loop_cap=2 on edge 39f->25 (alt-channel booking retry).
- loop_cap=3 on edge LD4->14 (drip re-entry).
- One new node D7 (drip exhausted dead-end) added with edge LD4->D7 (CAP REACHED).
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.enums import StepType
from app.models.sequence import Sequence, SequenceGoal, SequenceVersion, Step, StepEdge

logger = logging.getLogger(__name__)

PRESET_LINEAGE_KEY = "acquisition_nurture_v1"


# ---------------------------------------------------------------------------
# Raw tree data -- parsed from docs/jamm_nurture_preset_tree.html
# (extracted from the nodes[] and edges[] JavaScript arrays verbatim)
# ---------------------------------------------------------------------------

# Phase label mapped per node's visual group in the tree's phases[] array.
# Keyed by step_key.
_PHASE: dict[str, str] = {
    "T1": "triggers", "T2": "triggers", "T3": "triggers",
    "1": "phase_1_speed_to_lead", "2": "phase_1_speed_to_lead",
    "3": "phase_1_speed_to_lead", "4": "phase_1_speed_to_lead",
    "5": "phase_1_speed_to_lead", "6": "phase_1_speed_to_lead",
    "7": "phase_1_speed_to_lead", "8": "phase_1_speed_to_lead",
    "9": "phase_1_speed_to_lead", "10": "phase_1_speed_to_lead",
    "11": "phase_1_speed_to_lead", "12": "phase_1_speed_to_lead",
    "13": "phase_1_speed_to_lead", "D1": "phase_1_speed_to_lead",
    "14": "phase_2_qualify", "15": "phase_2_qualify",
    "16": "phase_2_qualify", "17": "phase_2_qualify",
    "18": "phase_2_qualify", "19": "phase_2_qualify",
    "20": "phase_2_qualify", "D2a": "phase_2_qualify",
    "21": "phase_2_qualify", "22": "phase_2_qualify",
    "R1": "phase_2_qualify", "D2": "phase_2_qualify",
    "23": "phase_2_qualify", "24": "phase_2_qualify",
    "25": "phase_3_book_the_call", "26": "phase_3_book_the_call",
    "27": "phase_3_book_the_call", "39a": "phase_3_book_the_call",
    "39b": "phase_3_book_the_call", "39c": "phase_3_book_the_call",
    "39d": "phase_3_book_the_call", "39e": "phase_3_book_the_call",
    "39f": "phase_3_book_the_call", "D3b": "phase_3_book_the_call",
    "G1": "phase_3_book_the_call", "28": "phase_3_book_the_call",
    "29": "phase_3_book_the_call", "30": "phase_3_book_the_call",
    "31": "phase_3_book_the_call", "32": "phase_3_book_the_call",
    "33": "phase_3_book_the_call", "34": "phase_3_book_the_call",
    "35": "phase_3_book_the_call", "36": "phase_3_book_the_call",
    "37": "phase_3_book_the_call", "38": "phase_3_book_the_call",
    "D3": "phase_3_book_the_call",
    "40": "phase_4_propose_and_close", "41": "phase_4_propose_and_close",
    "42": "phase_4_propose_and_close", "43": "phase_4_propose_and_close",
    "44": "phase_4_propose_and_close", "W1": "phase_4_propose_and_close",
    "45": "phase_4_propose_and_close", "45b": "phase_4_propose_and_close",
    "46": "phase_4_propose_and_close", "46b": "phase_4_propose_and_close",
    "47": "phase_4_propose_and_close", "48": "phase_4_propose_and_close",
    "48b": "phase_4_propose_and_close", "D4": "phase_4_propose_and_close",
    "D5": "phase_4_propose_and_close", "49": "phase_4_propose_and_close",
    "D6": "phase_4_propose_and_close",
    "LD1": "long_term_drip", "LD2": "long_term_drip",
    "LD3": "long_term_drip", "LD4": "long_term_drip",
    "D7": "long_term_drip",
}

# Wait node subtype table (per task judgment call 1).
# Keys are step_keys of the 19 wait nodes from the source tree.
_WAIT_CONFIG: dict[str, dict] = {
    "3":   {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 2},
    "6":   {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 3},
    "9":   {"subtype": "wait_until_event", "watched_event": "reply_or_click", "timeout_days": 4},
    "12":  {"subtype": "wait_until_event", "watched_event": "reply_or_click", "timeout_days": 5},
    "16":  {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 3},
    "19":  {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 3},
    "26":  {"subtype": "wait_until_event", "watched_event": "lead.call_booked", "timeout_days": 3},
    "29":  {"subtype": "wait_fixed", "anchor": "booking.start_time", "offset_hours": -24},
    "31":  {"subtype": "wait_fixed", "anchor": "booking.start_time", "offset_hours": 1},
    "34":  {"subtype": "wait_until_event", "watched_event": "lead.call_booked", "timeout_days": 2},
    "37":  {"subtype": "wait_until_event", "watched_event": "lead.call_booked", "timeout_days": 3},
    "39b": {"subtype": "wait_until_event", "watched_event": "lead.call_booked", "timeout_days": 3},
    "39e": {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 4},
    "41":  {"subtype": "wait_until_event", "watched_event": "staff_action_proposal_sent",
            "timeout_days": None, "nudge_at_days": 3},
    "43":  {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 4},
    "45b": {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 4},
    "46b": {"subtype": "wait_until_event", "watched_event": "reply", "timeout_days": 5},
    "LD3": {"subtype": "wait_until_event", "watched_event": "reply_or_click", "timeout_days": 90},
}

# Nodes extracted verbatim from the source tree's nodes[] array, with the
# t field mapped to StepType values and config built per node type.
# Format: (step_key, t_raw, headline, description)
_NODES: list[tuple[str, str, str, str]] = [
    # Triggers
    ("T1", "trigger", "Intake form submitted",
     "Public intake page. Source, platform, UTM captured automatically. Auto-enrolls."),
    ("T2", "trigger", "Lead created manually",
     "Staff adds a lead. Source picked from enum. Enroll toggle on create."),
    ("T3", "trigger", "Stage set to Contacted",
     "Manual stage move can enroll a lead that skipped the form."),
    # Phase 1
    ("1", "action", "Notify firm: new lead",
     "In-app + email alert to owner with source, platform, and form answers."),
    ("2", "email", "E1 - Welcome / received",
     '"Got your inquiry" + what happens next. Sends near-instant (speed-to-lead).'),
    ("3", "wait", "Wait until reply",
     "Timeout 2 days. Reply detected via inbound Postmark on the lead thread."),
    ("4", "branch", "Replied?",
     "Any reply routes to Qualification. Writes first_response_time to the lead."),
    ("5", "email", "E2 - Nudge + question",
     "Short bump. Embeds the first qualification question to invite an easy reply."),
    ("6", "wait", "Wait until reply", "Timeout 3 days."),
    ("7", "branch", "Replied?", ""),
    ("8", "email", "E3 - Value touch",
     "Lead magnet: deadline checklist / 'what to bring' guide. Click also counts as engagement."),
    ("9", "wait", "Wait until reply or click", "Timeout 4 days."),
    ("10", "branch", "Engaged?", ""),
    ("11", "email", "E4 - Breakup",
     '"Closing the file" + one-click "still interested" link. Highest reply rate of the set.'),
    ("12", "wait", "Wait until reply or click", "Timeout 5 days."),
    ("13", "branch", "Engaged?", ""),
    ("D1", "dead", "Lost - unresponsive",
     "Tag cold. lost_reason=unresponsive. To Long-Term Drip. Owner notified with one-click take-over."),
    # Phase 2
    ("14", "action", "Task: review reply",
     "Assign to owner/staff. Lead marked engaged. Response threaded onto the lead record."),
    ("15", "email", "E5 - Qualification ask",
     "Links to a short structured form: service need, individual vs business, entity type, revenue band, timeline question."),
    ("16", "wait", "Wait until reply", "Timeout 3 days."),
    ("17", "branch", "Answered?", ""),
    ("18", "email", "E6 - Gentle re-ask",
     'One retry only. Reframes the questions as "so we can point you to the right person."'),
    ("19", "wait", "Wait until reply", "Timeout 3 days."),
    ("20", "branch", "Answered?", ""),
    ("D2a", "dead", "Lost - unresponsive",
     "Engaged once, went dark on questions. lost_reason=unresponsive. To Long-Term Drip. Owner notified, one-click take-over."),
    ("21", "action", "Write structured fields",
     "service_interest, entity_type, revenue_band, urgency written from FORM answers (or staff capture from a prose reply). Never machine-parsed."),
    ("22", "branch", "Fit check",
     "Service offered by firm AND revenue/complexity above the firm-set floor?"),
    ("R1", "action", "Flag unqualified - owner review",
     "Owner notified with the answers the lead gave. Decline email HELD for one-click approval. Owner can override back into the sequence instead."),
    ("D2", "dead", "Lost - unqualified",
     "On approval: E7 polite decline + referral suggestion sends. lost_reason=unqualified. Filtered on purpose: never counts against conversion."),
    ("23", "branch", "Urgency?",
     "From the timeline question on the form (filing deadline / IRS notice in hand) or a staff mark. Never inferred from text."),
    ("24", "action", "Hot lead alert",
     "Immediate owner notification. Hot leads should get a human same-day, not just the sequence."),
    # Phase 3
    ("25", "email", "E8 - Booking invite",
     "Native JAMM booking link (firm calendar). lead.call_booked is the goal this phase watches."),
    ("26", "wait", "Wait until booked", "Goal-watched. Timeout 3 days."),
    ("27", "branch", "Booked?", ""),
    ("39a", "email", "E9 - Booking nudge",
     "Two suggested times in plain text + the link again."),
    ("39b", "wait", "Wait until booked", "Timeout 3 days."),
    ("39c", "branch", "Booked?", ""),
    ("39d", "email", "E10 - Alt channel offer",
     '"Prefer email? Reply with your questions." Also creates task: owner personal outreach.'),
    ("39e", "wait", "Wait until reply", "Timeout 4 days."),
    ("39f", "branch", "Engaged?", "Yes loops back to the booking invite."),
    ("D3b", "dead", "Lost - unresponsive",
     "Qualified but never booked. To Long-Term Drip. Owner notified, one-click take-over. This bucket is a metric worth watching."),
    ("G1", "goal", "GOAL - Call booked",
     "Fires from anywhere in Phases 1-3 the moment a booking lands. Skips everything between."),
    ("28", "email", "E11 - Confirmation",
     "Time, who they meet, what to have handy. Calendar attachment."),
    ("29", "wait", "Wait until 24h before call",
     "Anchored to the booked slot, not a fixed delay."),
    ("30", "email", "E12 - Reminder",
     "Short. Reschedule link included: a reschedule is not a no-show."),
    ("31", "wait", "Wait until call time +1h", "Then check what happened."),
    ("32", "branch", "Call happened?",
     "Staff marks held / no-show on the lead (one click from the task)."),
    ("33", "email", "E13 - Missed you",
     'No guilt. Rebook link. "Want us to just handle it by email instead?"'),
    ("34", "wait", "Wait until rebooked", "Timeout 2 days."),
    ("35", "branch", "Rebooked?",
     "Yes loops to confirmation. Max 2 rebook loops, then falls through."),
    ("36", "email", "E14 - Second nudge",
     "Last rebook attempt, offers the email-only path."),
    ("37", "wait", "Wait until rebooked", "Timeout 3 days."),
    ("38", "branch", "Rebooked?", ""),
    ("D3", "dead", "Lost - unresponsive",
     "Booked once, vanished. To Long-Term Drip. Owner notified, one-click take-over."),
    # Phase 4
    ("40", "action", "Stage to Proposal + task",
     "Auto stage move. Task: prepare and send proposal, assigned from the call."),
    ("41", "wait", "Wait until proposal sent",
     "Waits on the staff action, not a timer. Nudges staff internally at 3 days."),
    ("42", "email", "E15 - Proposal delivered",
     "Generated from the firm engagement letter template for the selected service type, unsigned. Scope, fee, start date, one clear accept action."),
    ("43", "wait", "Wait until reply", "Timeout 4 days."),
    ("44", "branch", "Response?",
     "Accepted goes straight to Won. Anything else routes right."),
    ("W1", "won", "WON - Convert to Client",
     "Client created. Attribution + provenance flow forward. Accepted proposal becomes the e-sign engagement letter. Exits every sequence. Onboarding begins."),
    ("45", "email", "E16 - Follow-up 1",
     '"Any questions on the proposal?" Light.'),
    ("45b", "wait", "Wait until reply", "Timeout 4 days."),
    ("46", "email", "E17 - Follow-up 2",
     "Addresses the two most common objections head-on. Offers a 10-minute call."),
    ("46b", "wait", "Wait until reply", "Timeout 5 days."),
    ("47", "branch", "Outcome?",
     "Reply parsed / staff tags it: price, competitor, timing, or silence."),
    ("48", "action", "Task: owner call",
     "Price objection gets a human. Optionally an adjusted proposal."),
    ("48b", "branch", "Closed?", "Yes routes to Won."),
    ("D4", "dead", "Lost - price",
     "Graceful close, door open. Light drip (2x/year)."),
    ("D5", "dead", "Lost - chose competitor",
     "Graceful close + door-open email. Light drip. Competitor named if offered: gold for intelligence later."),
    ("49", "action", "Schedule re-engagement",
     '"After tax season" gets a date. lost_reason=timing recorded now; lead re-enters at Booking on that date.'),
    ("D6", "dead", "Lost - unresponsive",
     "Silence after proposal. To Long-Term Drip. Owner notified, one-click take-over."),
    # Long-term drip
    ("LD1", "trigger", "Drip entry",
     "Enrolled from any unresponsive/price/competitor dead end. Suppression list checked before every send."),
    ("LD2", "email", "E18 - Quarterly value",
     'Deadline reminders, law changes, one useful thing. Never "just checking in."'),
    ("LD3", "wait", "Wait reply/click or 90d", "Whichever first."),
    ("LD4", "branch", "Engaged?",
     "Yes re-enters Qualification with history intact. No loops the drip. Unsubscribe exits forever."),
    # D7: new node, not in source tree -- added per task judgment call 2 (drip loop cap)
    ("D7", "dead", "Long-term drip exhausted",
     "Lead has cycled through re-engagement 3 times without converting."),
]

# Edges from the source tree's edges[] array.
# Format: (from_key, to_key, condition_label)
# loop_cap is None for all except the two named in judgment call 2.
_EDGES: list[tuple[str, str, Optional[str], Optional[int]]] = [
    ("T1", "1", None, None),
    ("T2", "1", None, None),
    ("T3", "1", None, None),
    ("1", "2", None, None),
    ("2", "3", None, None),
    ("3", "4", None, None),
    ("4", "14", "YES", None),
    ("4", "5", "NO", None),
    ("5", "6", None, None),
    ("6", "7", None, None),
    ("7", "14", "YES", None),
    ("7", "8", "NO", None),
    ("8", "9", None, None),
    ("9", "10", None, None),
    ("10", "14", "YES", None),
    ("10", "11", "NO", None),
    ("11", "12", None, None),
    ("12", "13", None, None),
    ("13", "14", "YES", None),
    ("13", "D1", "NO", None),
    ("14", "15", None, None),
    ("15", "16", None, None),
    ("16", "17", None, None),
    ("17", "21", "YES", None),
    ("17", "18", "NO", None),
    ("18", "19", None, None),
    ("19", "20", None, None),
    ("20", "21", "YES", None),
    ("20", "D2a", "NO", None),
    ("21", "22", None, None),
    ("22", "23", "FIT", None),
    ("22", "R1", "NOT FIT", None),
    ("R1", "D2", "APPROVED", None),
    ("R1", "23", "OVERRIDE", None),
    ("23", "25", "WARM", None),
    ("23", "24", "HOT", None),
    ("24", "25", None, None),
    ("25", "26", None, None),
    ("26", "27", None, None),
    ("27", "G1", "YES", None),
    ("27", "39a", "NO", None),
    ("39a", "39b", None, None),
    ("39b", "39c", None, None),
    ("39c", "G1", "YES", None),
    ("39c", "39d", "NO", None),
    ("39d", "39e", None, None),
    ("39e", "39f", None, None),
    # loop_cap=2: the alt-channel booking retry loop (judgment call 2)
    ("39f", "25", "YES", 2),
    ("39f", "D3b", "NO", None),
    ("G1", "28", None, None),
    ("28", "29", None, None),
    ("29", "30", None, None),
    ("30", "31", None, None),
    ("31", "32", None, None),
    ("32", "40", "HELD", None),
    ("32", "33", "NO-SHOW", None),
    ("33", "34", None, None),
    ("34", "35", None, None),
    ("35", "28", "YES", None),
    ("35", "36", "NO", None),
    ("36", "37", None, None),
    ("37", "38", None, None),
    ("38", "28", "YES", None),
    ("38", "D3", "NO", None),
    ("40", "41", None, None),
    ("41", "42", None, None),
    ("42", "43", None, None),
    ("43", "44", None, None),
    ("44", "W1", "ACCEPTED", None),
    ("44", "45", "ELSE", None),
    ("45", "45b", None, None),
    ("45b", "46", None, None),
    ("46", "46b", None, None),
    ("46b", "47", None, None),
    ("47", "48", "PRICE", None),
    ("47", "D5", "COMPETITOR", None),
    ("47", "49", "TIMING", None),
    ("47", "D6", "SILENCE", None),
    ("48", "48b", None, None),
    ("48b", "W1", "YES", None),
    ("48b", "D4", "NO", None),
    ("49", "25", "AT DATE", None),
    ("D1", "LD1", None, None),
    ("D3b", "LD1", None, None),
    ("LD1", "LD2", None, None),
    ("LD2", "LD3", None, None),
    ("LD3", "LD4", None, None),
    ("LD4", "LD2", "NO - LOOP", None),
    # loop_cap=3: the drip re-entry into Qualification (judgment call 2)
    ("LD4", "14", "YES - RE-ENROLL", 3),
    # New edge: LD4->D7 when drip loop cap is reached (judgment call 2)
    ("LD4", "D7", "CAP REACHED", None),
]


def _node_type(t_raw: str) -> StepType:
    """Map the tree's node type string to the StepType enum."""
    mapping = {
        "trigger": StepType.trigger,
        "email": StepType.email,
        "wait": None,  # resolved via _WAIT_CONFIG
        "branch": StepType.branch,
        "action": StepType.action,
        "goal": StepType.goal,
        "won": StepType.won,
        "dead": StepType.dead_end,
    }
    return mapping[t_raw]


def _build_step_config(step_key: str, t_raw: str, headline: str, description: str) -> dict:
    """Build the type-specific config dict for a step."""
    if t_raw == "email":
        config: dict = {
            "subject": "PENDING COPY",
            "body": "PENDING COPY",
            "headline": headline,
            "description": description,
        }
        if step_key == "2":
            # E1 (Welcome / received) sends immediately regardless of business hours.
            # Speed-to-lead: contact/qualification odds decay sharply within minutes
            # (MIT/InsideSales Lead Response Management Study, 15k+ leads). Every
            # other email step in the tree respects the business-hours window.
            config["bypass_business_hours"] = True
        return config
    if t_raw == "wait":
        wc = _WAIT_CONFIG[step_key]
        return {"headline": headline, "description": description, **wc}
    if t_raw == "branch":
        return {"headline": headline, "description": description}
    if t_raw == "action":
        # Infer action_kind from description text
        d_lower = description.lower()
        if "notify" in d_lower or "alert" in d_lower or "notification" in d_lower:
            action_kind = "notify_owner"
        elif "task" in d_lower:
            action_kind = "create_task"
        elif "write" in d_lower or "field" in d_lower or "stage" in d_lower or "tag" in d_lower:
            action_kind = "write_lead_fields"
        elif "schedule" in d_lower or "date" in d_lower:
            action_kind = "schedule_re_engagement"
        elif "flag" in d_lower or "held" in d_lower:
            action_kind = "notify_owner"
        else:
            action_kind = "internal_action"
        config: dict = {"headline": headline, "description": description, "action_kind": action_kind}
        if step_key == "R1":
            # R1 is the only step whose external consequence (the unqualified decline email)
            # must be held for firm-owner approval before sending -- Contract section 6.7.
            config["hold_for_approval"] = True
        return config
    if t_raw in ("trigger", "goal", "won", "dead"):
        return {"headline": headline, "description": description}
    return {"headline": headline, "description": description}


def _resolve_step_type(step_key: str, t_raw: str) -> StepType:
    if t_raw != "wait":
        return _node_type(t_raw)
    wc = _WAIT_CONFIG[step_key]
    if wc["subtype"] == "wait_fixed":
        return StepType.wait_fixed
    return StepType.wait_until_event


def seed_firm_nurture_preset(firm_id: UUID, db: Session) -> int:
    """Seed the acquisition nurture preset tree for one firm.

    Creates one Sequence, one SequenceVersion, 76 Steps (75 from the source
    tree plus D7), 90 StepEdges (89 from the source tree plus LD4->D7),
    and one SequenceGoal.

    Returns the number of Step rows created (76).
    Raises ValueError if this firm already has a sequence with
    preset_lineage_key=acquisition_nurture_v1 (safe no-op caller should
    check first, or catch and ignore).
    """
    existing = (
        db.query(SequenceVersion)
        .join(Sequence, SequenceVersion.sequence_id == Sequence.id)
        .filter(
            Sequence.firm_id == firm_id,
            SequenceVersion.preset_lineage_key == PRESET_LINEAGE_KEY,
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"Firm {firm_id} already has a sequence with preset_lineage_key={PRESET_LINEAGE_KEY!r}. "
            "Skipping to prevent duplicate."
        )

    now = datetime.now(timezone.utc)

    # 1. Create the Sequence shell (current_version_id set after version is created).
    seq = Sequence(
        id=uuid4(),
        firm_id=firm_id,
        name="Acquisition Nurture (Preset v1)",
        is_active=True,
        current_version_id=None,
        created_at=now,
        updated_at=now,
    )
    db.add(seq)
    db.flush()

    # 2. Create the SequenceVersion.
    ver = SequenceVersion(
        id=uuid4(),
        sequence_id=seq.id,
        version_number=1,
        preset_lineage_key=PRESET_LINEAGE_KEY,
        created_at=now,
    )
    db.add(ver)
    db.flush()

    # 3. Create all Step rows, tracking step_key -> Step.id for edge resolution.
    step_id_by_key: dict[str, UUID] = {}
    step_objects: list[Step] = []
    for step_key, t_raw, headline, description in _NODES:
        step_type = _resolve_step_type(step_key, t_raw)
        config = _build_step_config(step_key, t_raw, headline, description)
        step = Step(
            id=uuid4(),
            sequence_version_id=ver.id,
            step_key=step_key,
            step_type=step_type,
            channel="email",
            phase=_PHASE.get(step_key),
            is_modified_from_preset=False,
            config=config,
            created_at=now,
        )
        db.add(step)
        step_id_by_key[step_key] = step.id
        step_objects.append(step)
    db.flush()

    # 4. Create all StepEdge rows.
    for from_key, to_key, condition_label, loop_cap in _EDGES:
        from_id = step_id_by_key[from_key]
        to_id = step_id_by_key[to_key]
        edge = StepEdge(
            id=uuid4(),
            from_step_id=from_id,
            to_step_id=to_id,
            condition_label=condition_label,
            loop_cap=loop_cap,
            created_at=now,
        )
        db.add(edge)
    db.flush()

    # 5. Create the one SequenceGoal row.
    goal = SequenceGoal(
        id=uuid4(),
        sequence_version_id=ver.id,
        goal_event="lead.call_booked",
        target_step_id=step_id_by_key["G1"],
        applies_to_phase=None,  # applies across the whole version
        created_at=now,
    )
    db.add(goal)

    # 6. Point the Sequence at its version.
    seq.current_version_id = ver.id
    db.commit()

    n_steps = len(_NODES)
    logger.info(
        "seed_firm_nurture_preset: seeded %d steps for firm %s (preset_lineage_key=%s)",
        n_steps, firm_id, PRESET_LINEAGE_KEY,
    )
    return n_steps
