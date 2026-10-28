from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.utils import timezone

from .exceptions import WorkflowError


class UserManager(DjangoUserManager):
    """Create users with an email address as the login identifier."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        ADMIN = "ADMIN", "Admin"
        DEPARTMENT = "DEPARTMENT", "Department"

    username = models.CharField(max_length=150, unique=True, blank=True)
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    department = models.CharField(
        max_length=80,
        blank=True,
        help_text="Only used for department accounts (e.g. Mess, Hostel).",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        if not self.name:
            self.name = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name or self.email

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_department(self):
        return self.role == self.Role.DEPARTMENT

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMIN


class Complaint(models.Model):
    class Category(models.TextChoices):
        MESS = "MESS", "Mess"
        HOSTEL = "HOSTEL", "Hostel"
        ACADEMICS = "ACADEMICS", "Academics"
        INFRASTRUCTURE = "INFRASTRUCTURE", "Infrastructure"
        OTHERS = "OTHERS", "Others"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        FILED = "FILED", "Filed"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"
        REOPENED = "REOPENED", "Reopened"

    ALLOWED_TRANSITIONS = {
        Status.FILED: {Status.ASSIGNED},
        Status.ASSIGNED: {Status.IN_PROGRESS},
        Status.IN_PROGRESS: {Status.RESOLVED},
        Status.RESOLVED: {Status.CLOSED, Status.IN_PROGRESS},
        Status.CLOSED: {Status.REOPENED},
        Status.REOPENED: {Status.IN_PROGRESS},
    }

    number = models.CharField(max_length=12, unique=True, editable=False, blank=True)
    title = models.CharField(max_length=120)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.FILED,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="filed_complaints",
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_complaints",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        if not self.number:
            last = Complaint.objects.order_by("-id").only("id").first()
            next_id = (last.id + 1) if last else 1
            self.number = f"CMP-{next_id:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"

    def touch(self):
        self.updated_at = timezone.now()

    def can_transition_to(self, target):
        return target in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, target, actor, note=""):
        if target == self.status:
            raise WorkflowError(
                f"Complaint is already {self.get_status_display().lower()}."
            )
        if not self.can_transition_to(target):
            raise WorkflowError(
                "Cannot move from "
                f"{self.get_status_display()} to "
                f"{dict(self.Status.choices).get(target, target)}."
            )
        previous = self.status
        self.status = target
        self.touch()
        if target == self.Status.CLOSED:
            self.closed_at = timezone.now()
        self.save()
        StatusEvent.objects.create(
            complaint=self,
            from_status=previous,
            to_status=target,
            actor=actor,
            actor_name=actor.name if actor else "System",
            note=note,
        )
        return self

    def bump_priority(self):
        order = list(self.Priority.values)
        index = order.index(self.priority)
        self.priority = order[min(index + 1, len(order) - 1)]

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    @property
    def can_reopen(self):
        return self.status == self.Status.CLOSED


class Remark(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="remarks",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="remarks",
    )
    author_name = models.CharField(max_length=120)
    author_role = models.CharField(max_length=20)
    text = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Remark by {self.author_name} on {self.complaint.number}"


class StatusEvent(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="history",
    )
    from_status = models.CharField(max_length=20, choices=Complaint.Status.choices)
    to_status = models.CharField(max_length=20, choices=Complaint.Status.choices)
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="status_events",
    )
    actor_name = models.CharField(max_length=120)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.complaint.number}: {self.from_status} → {self.to_status}"


class Notification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message
