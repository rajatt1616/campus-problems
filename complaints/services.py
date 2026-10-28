from django.db import transaction
from django.utils import timezone

from .exceptions import AccessDenied, WorkflowError
from .models import Complaint, Notification, Remark, User


def notify(user, complaint, message):
    if user is None:
        return
    Notification.objects.create(user=user, complaint=complaint, message=message)


@transaction.atomic
def create_complaint(actor, title, description, category, priority):
    if not actor.is_student:
        raise AccessDenied("Only students can file complaints.")
    return Complaint.objects.create(
        title=title,
        description=description,
        category=category,
        priority=priority,
        created_by=actor,
        status=Complaint.Status.FILED,
    )


@transaction.atomic
def assign_complaint(actor, complaint, department_user):
    if not actor.is_administrator:
        raise AccessDenied("Only an admin can assign complaints.")
    if complaint.status != Complaint.Status.FILED:
        raise WorkflowError("Only newly filed complaints can be assigned.")
    if not department_user.is_department:
        raise AccessDenied("The selected user is not a department account.")

    complaint.assigned_to = department_user
    complaint.transition_to(
        Complaint.Status.ASSIGNED,
        actor,
        f"Assigned to {department_user.name}",
    )
    notify(
        department_user,
        complaint,
        f"{complaint.number} assigned to you",
    )
    notify(
        complaint.created_by,
        complaint,
        f"{complaint.number} assigned to {department_user.name}",
    )
    return complaint


@transaction.atomic
def start_work(actor, complaint):
    _require_assigned_department(actor, complaint)
    if complaint.status not in {Complaint.Status.ASSIGNED, Complaint.Status.REOPENED}:
        raise WorkflowError("Work can only start on an assigned or reopened complaint.")
    complaint.transition_to(Complaint.Status.IN_PROGRESS, actor, "Work started")
    notify(
        complaint.created_by,
        complaint,
        f"{actor.name} started working on {complaint.number}",
    )
    return complaint


@transaction.atomic
def resolve_complaint(actor, complaint, remark_text=""):
    _require_assigned_department(actor, complaint)
    if complaint.status != Complaint.Status.IN_PROGRESS:
        raise WorkflowError("Only complaints in progress can be resolved.")
    complaint.transition_to(Complaint.Status.RESOLVED, actor, "Marked as resolved")
    if remark_text:
        _add_remark(complaint, actor, remark_text)
    notify(
        complaint.created_by,
        complaint,
        f"{complaint.number} marked resolved — verify and accept",
    )
    return complaint


@transaction.atomic
def accept_complaint(actor, complaint):
    _require_complainant(actor, complaint)
    if complaint.status != Complaint.Status.RESOLVED:
        raise WorkflowError("Only resolved complaints can be accepted.")
    complaint.transition_to(
        Complaint.Status.CLOSED,
        actor,
        "Accepted by complainant",
    )
    notify(
        complaint.assigned_to,
        complaint,
        f"Student accepted the resolution of {complaint.number}",
    )
    return complaint


@transaction.atomic
def reject_complaint(actor, complaint, reason):
    _require_complainant(actor, complaint)
    if complaint.status != Complaint.Status.RESOLVED:
        raise WorkflowError("Only a resolved complaint can be rejected.")
    if not reason or not reason.strip():
        raise WorkflowError("A reason is required to reject a resolution.")
    _add_remark(complaint, actor, f"Rejected: {reason.strip()}")
    complaint.transition_to(
        Complaint.Status.IN_PROGRESS,
        actor,
        "Resolution rejected by complainant",
    )
    notify(
        complaint.assigned_to,
        complaint,
        f"Student rejected the resolution of {complaint.number}",
    )
    return complaint


@transaction.atomic
def reopen_complaint(actor, complaint):
    _require_complainant(actor, complaint)
    if complaint.status != Complaint.Status.CLOSED:
        raise WorkflowError("Only closed complaints can be reopened.")
    complaint.bump_priority()
    complaint.transition_to(
        Complaint.Status.REOPENED,
        actor,
        "Reopened by complainant",
    )
    notify(
        complaint.assigned_to,
        complaint,
        f"{complaint.number} reopened by the student",
    )
    return complaint


@transaction.atomic
def add_remark(actor, complaint, text):
    if not text or not text.strip():
        raise WorkflowError("Remark cannot be empty.")
    _add_remark(complaint, actor, text.strip())
    _notify_counterparts(actor, complaint, f"New remark on {complaint.number} by {actor.name}")
    return complaint


def _add_remark(complaint, actor, text):
    Remark.objects.create(
        complaint=complaint,
        author=actor,
        author_name=actor.name,
        author_role=actor.role,
        text=text.strip(),
    )
    complaint.updated_at = timezone.now()
    complaint.save(update_fields=["updated_at"])


def _notify_counterparts(actor, complaint, message):
    targets = {
        complaint.created_by,
        complaint.assigned_to,
    }
    targets.discard(None)
    targets.discard(actor)
    for target in targets:
        notify(target, complaint, message)


def _require_assigned_department(actor, complaint):
    if not actor.is_department or complaint.assigned_to_id != actor.id:
        raise AccessDenied("This complaint is not assigned to you.")


def _require_complainant(actor, complaint):
    if not actor.is_student or complaint.created_by_id != actor.id:
        raise AccessDenied("Only the complainant can perform this action.")


def can_edit(actor, complaint):
    return (
        actor.is_student
        and complaint.created_by_id == actor.id
        and complaint.status == Complaint.Status.FILED
    )


def can_delete(actor, complaint):
    return actor.is_administrator or can_edit(actor, complaint)


def visible_complaints_for(user):
    queryset = Complaint.objects.select_related("created_by", "assigned_to")
    if user.is_student:
        return queryset.filter(created_by=user)
    if user.is_department:
        return queryset.filter(assigned_to=user)
    return queryset.all()


def department_accounts():
    return User.objects.filter(role=User.Role.DEPARTMENT).order_by("department", "name")
