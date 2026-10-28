from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from complaints.models import (
    Complaint,
    Notification,
    Remark,
    StatusEvent,
    User,
)

DEMO_PASSWORDS = {
    "rajat@student.srmist.edu": "student123",
    "admin@srmist.edu": "admin123",
    "mess@srmist.edu": "dept123",
    "hostel@srmist.edu": "dept123",
    "academics@srmist.edu": "dept123",
}


class Command(BaseCommand):
    help = "Create demo users and sample complaints (idempotent)."

    def handle(self, *args, **options):
        users = self._seed_users()
        student = users["student"]
        admin = users["admin"]
        mess = users["mess"]
        hostel = users["hostel"]
        academics = users["academics"]

        if Complaint.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Complaints already exist, so sample complaints were skipped. "
                    "Demo user passwords were refreshed."
                )
            )
            self._print_credentials()
            return

        now = timezone.now()

        c1 = Complaint.objects.create(
            title="Cold food at breakfast every day",
            description=(
                "Breakfast items at the mess are served cold since last week. "
                "Multiple students have complained informally but nothing has changed."
            ),
            category=Complaint.Category.MESS,
            priority=Complaint.Priority.MEDIUM,
            status=Complaint.Status.FILED,
            created_by=student,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )

        c2 = Complaint.objects.create(
            title="Hostel washroom light not working",
            description=(
                "The second-floor washroom light in Block C has been out for three "
                "days. It is unsafe at night."
            ),
            category=Complaint.Category.HOSTEL,
            priority=Complaint.Priority.HIGH,
            status=Complaint.Status.ASSIGNED,
            created_by=student,
            assigned_to=hostel,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=30),
        )
        self._event(
            c2,
            Complaint.Status.FILED,
            Complaint.Status.ASSIGNED,
            admin,
            "Assigned to Hostel Warden",
            now - timedelta(hours=30),
        )

        c3 = Complaint.objects.create(
            title="Lab machines too slow for DB practicals",
            description=(
                "Computers in the DB lab take almost ten minutes to boot and Practical 4 "
                "cannot be completed in the allotted slot."
            ),
            category=Complaint.Category.ACADEMICS,
            priority=Complaint.Priority.MEDIUM,
            status=Complaint.Status.IN_PROGRESS,
            created_by=student,
            assigned_to=academics,
            created_at=now - timedelta(days=3),
            updated_at=now - timedelta(hours=26),
        )
        self._event(
            c3,
            Complaint.Status.FILED,
            Complaint.Status.ASSIGNED,
            admin,
            "Assigned to Academic Office",
            now - timedelta(days=2, hours=20),
        )
        self._event(
            c3,
            Complaint.Status.ASSIGNED,
            Complaint.Status.IN_PROGRESS,
            academics,
            "Under inspection",
            now - timedelta(hours=26),
        )

        c4 = Complaint.objects.create(
            title="Broken desk in lecture hall L-204",
            description=(
                "Second-row desk has a broken top and is unusable. Seat allocation forces "
                "students to share."
            ),
            category=Complaint.Category.INFRASTRUCTURE,
            priority=Complaint.Priority.LOW,
            status=Complaint.Status.RESOLVED,
            created_by=student,
            assigned_to=academics,
            created_at=now - timedelta(days=4),
            updated_at=now - timedelta(hours=20),
        )
        self._event(
            c4,
            Complaint.Status.FILED,
            Complaint.Status.ASSIGNED,
            admin,
            "Assigned to Academic Office",
            now - timedelta(days=3, hours=12),
        )
        self._event(
            c4,
            Complaint.Status.ASSIGNED,
            Complaint.Status.IN_PROGRESS,
            academics,
            "Carpenter notified",
            now - timedelta(days=1, hours=6),
        )
        self._event(
            c4,
            Complaint.Status.IN_PROGRESS,
            Complaint.Status.RESOLVED,
            academics,
            "Desk replaced",
            now - timedelta(hours=20),
        )
        Remark.objects.create(
            complaint=c4,
            author=academics,
            author_name=academics.name,
            author_role=academics.role,
            text="New desk installed, please verify and accept.",
            created_at=now - timedelta(hours=20),
        )

        c5 = Complaint.objects.create(
            title="Duplicate charge in lab fee receipt",
            description=(
                "Receipt shows lab fee charged twice for this semester. Attached scan "
                "available with the office."
            ),
            category=Complaint.Category.ACADEMICS,
            priority=Complaint.Priority.URGENT,
            status=Complaint.Status.CLOSED,
            created_by=student,
            assigned_to=academics,
            created_at=now - timedelta(days=6),
            updated_at=now - timedelta(hours=12),
            closed_at=now - timedelta(hours=12),
        )
        for from_status, to_status, actor, note, delta in [
            (
                Complaint.Status.FILED,
                Complaint.Status.ASSIGNED,
                admin,
                "Assigned to Academic Office",
                timedelta(days=5, hours=18),
            ),
            (
                Complaint.Status.ASSIGNED,
                Complaint.Status.IN_PROGRESS,
                academics,
                "Checked accounts",
                timedelta(days=3),
            ),
            (
                Complaint.Status.IN_PROGRESS,
                Complaint.Status.RESOLVED,
                academics,
                "Refund initiated",
                timedelta(days=1),
            ),
            (
                Complaint.Status.RESOLVED,
                Complaint.Status.CLOSED,
                student,
                "Accepted by complainant",
                timedelta(hours=12),
            ),
        ]:
            self._event(c5, from_status, to_status, actor, note, now - delta)

        c6 = Complaint.objects.create(
            title="Water cooler on floor 3 not cooling",
            description=(
                "The water cooler outside the reading room has stopped cooling since Monday."
            ),
            category=Complaint.Category.INFRASTRUCTURE,
            priority=Complaint.Priority.HIGH,
            status=Complaint.Status.REOPENED,
            created_by=student,
            assigned_to=hostel,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(hours=18),
        )
        for from_status, to_status, actor, note, delta in [
            (
                Complaint.Status.FILED,
                Complaint.Status.ASSIGNED,
                admin,
                "Assigned to Hostel Warden",
                timedelta(days=1, hours=20),
            ),
            (
                Complaint.Status.ASSIGNED,
                Complaint.Status.IN_PROGRESS,
                hostel,
                "Technician scheduled",
                timedelta(days=1, hours=16),
            ),
            (
                Complaint.Status.IN_PROGRESS,
                Complaint.Status.RESOLVED,
                hostel,
                "Filter replaced",
                timedelta(days=1, hours=12),
            ),
            (
                Complaint.Status.RESOLVED,
                Complaint.Status.CLOSED,
                student,
                "Accepted by complainant",
                timedelta(days=1, hours=6),
            ),
            (
                Complaint.Status.CLOSED,
                Complaint.Status.REOPENED,
                student,
                "Issue recurred — reopened",
                timedelta(hours=18),
            ),
        ]:
            self._event(c6, from_status, to_status, actor, note, now - delta)

        Notification.objects.create(
            user=academics,
            complaint=c4,
            message=f"{c4.number} marked resolved — verify and accept",
            created_at=now - timedelta(hours=20),
        )
        Notification.objects.create(
            user=student,
            complaint=c4,
            message=f"{c4.number} marked resolved — verify and accept",
            created_at=now - timedelta(hours=20),
        )
        Notification.objects.create(
            user=hostel,
            complaint=c6,
            message=f"{c6.number} reopened by the student",
            created_at=now - timedelta(hours=18),
        )
        Notification.objects.create(
            user=admin,
            complaint=c1,
            message=f"{c1.number} filed by {student.name}",
            created_at=now - timedelta(days=1),
            is_read=True,
        )

        self.stdout.write(self.style.SUCCESS("Demo data created successfully."))
        self._print_credentials()

    def _seed_users(self):
        definitions = [
            {
                "key": "student",
                "email": "rajat@student.srmist.edu",
                "name": "Rajat Tyagi",
                "role": User.Role.STUDENT,
                "department": "",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "key": "admin",
                "email": "admin@srmist.edu",
                "name": "Registrar Office",
                "role": User.Role.ADMIN,
                "department": "",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "key": "mess",
                "email": "mess@srmist.edu",
                "name": "Mess Authority",
                "role": User.Role.DEPARTMENT,
                "department": "Mess",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "key": "hostel",
                "email": "hostel@srmist.edu",
                "name": "Hostel Warden",
                "role": User.Role.DEPARTMENT,
                "department": "Hostel",
                "is_staff": False,
                "is_superuser": False,
            },
            {
                "key": "academics",
                "email": "academics@srmist.edu",
                "name": "Academic Office",
                "role": User.Role.DEPARTMENT,
                "department": "Academics",
                "is_staff": False,
                "is_superuser": False,
            },
        ]

        users = {}
        for definition in definitions:
            email = definition["email"]
            user, _created = User.objects.update_or_create(
                email=email,
                defaults={
                    "username": email,
                    "name": definition["name"],
                    "role": definition["role"],
                    "department": definition["department"],
                    "is_staff": definition["is_staff"],
                    "is_superuser": definition["is_superuser"],
                },
            )
            user.set_password(DEMO_PASSWORDS[email])
            user.save()
            users[definition["key"]] = user

        return users

    def _event(self, complaint, from_status, to_status, actor, note, at):
        StatusEvent.objects.create(
            complaint=complaint,
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            actor_name=actor.name,
            note=note,
            created_at=at,
        )

    def _print_credentials(self):
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write("  Student    rajat@student.srmist.edu / student123")
        self.stdout.write("  Admin      admin@srmist.edu / admin123")
        self.stdout.write("  Department mess@ / hostel@ / academics@srmist.edu / dept123")
