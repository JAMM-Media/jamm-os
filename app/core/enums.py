# app/core/enums.py

from enum import Enum


class UserRole(str, Enum):
    """
    The roles that exist in JAMM OS.

    firm_owner  → Full access to everything in their firm.
                  Can change firm settings, billing, add/remove staff.
    manager     → Access to all client/engagement data.
                  Cannot change firm settings or billing.
    staff       → Access to assigned engagements and tasks only.
                  Cannot see engagements they are not assigned to.
    client_portal_user → Client-facing role. Can only see their own data
                         through the client portal. Completely isolated
                         from the staff-facing side of the app.
    system_admin → JAMM OS internal use only. Cross-firm access for support.
                   Never assigned to a real firm's users.

    NOTE: The old "admin" role has been renamed to "firm_owner" to match
    accounting industry language and the master instructions domain model.
    The old "client" role has been renamed to "client_portal_user" to be
    explicit about what this role can and cannot access.
    """

    firm_owner = "firm_owner"
    manager = "manager"
    staff = "staff"
    client_portal_user = "client_portal_user"
    system_admin = "system_admin"


class EngagementStatus(str, Enum):
    """Valid status values for an Engagement."""
    draft = "draft"
    active = "active"
    in_review = "in_review"
    completed = "completed"
    archived = "archived"


class TaskStatus(str, Enum):
    """Valid status values for a Task."""
    todo = "todo"
    in_progress = "in_progress"
    done = "done"