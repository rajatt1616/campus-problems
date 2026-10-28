import json
import re
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .exceptions import AccessDenied, WorkflowError
from .forms import AssignForm, ComplaintForm, SearchForm
from .models import Complaint, Notification, Remark, StatusEvent, User
from . import services


class BaseComplaintTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = User.objects.create_user(
            email="student@campus.test",
            password="testpass123",
            name="Test Student",
            role=User.Role.STUDENT,
        )
        cls.other_student = User.objects.create_user(
            email="other@campus.test",
            password="testpass123",
            name="Other Student",
            role=User.Role.STUDENT,
        )
        cls.admin = User.objects.create_user(
            email="admin@campus.test",
            password="testpass123",
            name="Test Admin",
            role=User.Role.ADMIN,
        )
        cls.dept = User.objects.create_user(
            email="mess@campus.test",
            password="testpass123",
            name="Mess Department",
            role=User.Role.DEPARTMENT,
            department="Mess",
        )
        cls.other_dept = User.objects.create_user(
            email="hostel@campus.test",
            password="testpass123",
            name="Hostel Department",
            role=User.Role.DEPARTMENT,
            department="Hostel",
        )

        cls.filed = Complaint.objects.create(
            title="Broken washroom tap",
            description="The tap in the first floor washroom keeps running all day.",
            category=Complaint.Category.HOSTEL,
            priority=Complaint.Priority.LOW,
            status=Complaint.Status.FILED,
            created_by=cls.student,
        )
        cls.assigned = Complaint.objects.create(
            title="Washroom light is broken",
            description="The first floor washroom light has not worked for three days.",
            category=Complaint.Category.HOSTEL,
            priority=Complaint.Priority.HIGH,
            status=Complaint.Status.ASSIGNED,
            created_by=cls.student,
            assigned_to=cls.dept,
        )
        StatusEvent.objects.create(
            complaint=cls.assigned,
            from_status=Complaint.Status.FILED,
            to_status=Complaint.Status.ASSIGNED,
            actor=cls.admin,
            actor_name=cls.admin.name,
            note="Assigned",
        )
        cls.resolved = Complaint.objects.create(
            title="Lab computer will not boot",
            description="The computer at desk four in the database lab does not boot.",
            category=Complaint.Category.ACADEMICS,
            priority=Complaint.Priority.MEDIUM,
            status=Complaint.Status.RESOLVED,
            created_by=cls.student,
            assigned_to=cls.dept,
        )
        cls.closed = Complaint.objects.create(
            title="Duplicate fee receipt",
            description="The printed receipt shows the same lab fee charged twice.",
            category=Complaint.Category.ACADEMICS,
            priority=Complaint.Priority.URGENT,
            status=Complaint.Status.CLOSED,
            created_by=cls.student,
            assigned_to=cls.dept,
            closed_at=timezone.now(),
        )
        cls.other_complaint = Complaint.objects.create(
            title="Other student complaint",
            description="This complaint belongs to another student for scope testing.",
            category=Complaint.Category.OTHERS,
            priority=Complaint.Priority.MEDIUM,
            status=Complaint.Status.FILED,
            created_by=cls.other_student,
        )

    def login(self, user):
        self.client.force_login(user)


class ComplaintModelTests(BaseComplaintTestCase):
    def test_number_is_generated_and_matches_regex(self):
        self.assertTrue(re.fullmatch(r"CMP-\d{4}", self.filed.number))

    def test_valid_transition_creates_history(self):
        complaint = Complaint.objects.create(
            title="Transition test complaint",
            description="A valid transition should be recorded in the history.",
            category=Complaint.Category.MESS,
            priority=Complaint.Priority.MEDIUM,
            created_by=self.student,
            assigned_to=self.dept,
        )
        complaint.transition_to(Complaint.Status.ASSIGNED, self.admin, "Assigned")
        self.assertEqual(complaint.status, Complaint.Status.ASSIGNED)
        self.assertEqual(complaint.history.count(), 1)
        self.assertEqual(complaint.history.first().to_status, Complaint.Status.ASSIGNED)

    def test_invalid_transition_raises(self):
        with self.assertRaises(WorkflowError):
            self.filed.transition_to(Complaint.Status.RESOLVED, self.admin)

    def test_same_status_transition_raises(self):
        with self.assertRaises(WorkflowError):
            self.filed.transition_to(Complaint.Status.FILED, self.admin)

    def test_closing_sets_closed_at(self):
        complaint = Complaint.objects.create(
            title="Complete lifecycle complaint",
            description="This complaint will move through every allowed state.",
            category=Complaint.Category.ACADEMICS,
            priority=Complaint.Priority.MEDIUM,
            created_by=self.student,
            assigned_to=self.dept,
        )
        complaint.transition_to(Complaint.Status.ASSIGNED, self.admin)
        complaint.transition_to(Complaint.Status.IN_PROGRESS, self.dept)
        complaint.transition_to(Complaint.Status.RESOLVED, self.dept)
        complaint.transition_to(Complaint.Status.CLOSED, self.student)
        self.assertIsNotNone(complaint.closed_at)
        self.assertTrue(complaint.is_closed)

    def test_priority_bump_respects_maximum(self):
        self.filed.bump_priority()
        self.assertEqual(self.filed.priority, Complaint.Priority.MEDIUM)
        self.closed.bump_priority()
        self.assertEqual(self.closed.priority, Complaint.Priority.URGENT)


class ServiceTests(BaseComplaintTestCase):
    def test_only_students_can_file(self):
        with self.assertRaises(AccessDenied):
            services.create_complaint(
                self.admin,
                "Admin filing complaint",
                "An admin is not allowed to file a complaint in this system.",
                Complaint.Category.OTHERS,
                Complaint.Priority.LOW,
            )

    def test_only_admin_can_assign(self):
        with self.assertRaises(AccessDenied):
            services.assign_complaint(self.student, self.filed, self.dept)

    def test_assignment_requires_department_account(self):
        with self.assertRaises(AccessDenied):
            services.assign_complaint(self.admin, self.filed, self.student)

    def test_assignment_notifies_both_parties(self):
        services.assign_complaint(self.admin, self.filed, self.dept)
        self.filed.refresh_from_db()
        self.assertEqual(self.filed.status, Complaint.Status.ASSIGNED)
        self.assertEqual(self.filed.assigned_to, self.dept)
        self.assertTrue(
            Notification.objects.filter(
                user=self.dept, complaint=self.filed
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.student, complaint=self.filed
            ).exists()
        )

    def test_wrong_department_cannot_start_work(self):
        with self.assertRaises(AccessDenied):
            services.start_work(self.other_dept, self.assigned)

    def test_assigned_department_can_start_and_resolve(self):
        services.start_work(self.dept, self.assigned)
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.status, Complaint.Status.IN_PROGRESS)
        services.resolve_complaint(self.dept, self.assigned, "Part replaced")
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.status, Complaint.Status.RESOLVED)
        self.assertEqual(self.assigned.remarks.count(), 1)

    def test_only_owner_can_accept(self):
        with self.assertRaises(AccessDenied):
            services.accept_complaint(self.other_student, self.resolved)

    def test_reject_requires_reason(self):
        with self.assertRaises(WorkflowError):
            services.reject_complaint(self.student, self.resolved, "   ")

    def test_reject_moves_back_to_progress(self):
        services.reject_complaint(self.student, self.resolved, "Still broken")
        self.resolved.refresh_from_db()
        self.assertEqual(self.resolved.status, Complaint.Status.IN_PROGRESS)
        self.assertTrue(
            self.resolved.remarks.filter(text__startswith="Rejected:").exists()
        )

    def test_reopen_bumps_priority(self):
        services.reopen_complaint(self.student, self.closed)
        self.closed.refresh_from_db()
        self.assertEqual(self.closed.status, Complaint.Status.REOPENED)
        self.assertEqual(self.closed.priority, Complaint.Priority.URGENT)

    def test_remark_updates_timestamp_and_notifies(self):
        old_updated_at = self.assigned.updated_at
        services.add_remark(self.student, self.assigned, "Any update?")
        self.assigned.refresh_from_db()
        self.assertGreater(self.assigned.updated_at, old_updated_at)
        self.assertTrue(
            Notification.objects.filter(
                user=self.dept, complaint=self.assigned
            ).exists()
        )


class FormTests(BaseComplaintTestCase):
    def valid_form_data(self, **overrides):
        data = {
            "title": "Broken desk in the lab",
            "description": "The desk at the back of the lab is broken and unsafe.",
            "category": Complaint.Category.INFRASTRUCTURE,
            "priority": Complaint.Priority.MEDIUM,
        }
        data.update(overrides)
        return data

    def test_valid_complaint_form(self):
        form = ComplaintForm(data=self.valid_form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_title_too_short(self):
        form = ComplaintForm(data=self.valid_form_data(title="Short"))
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_title_rejects_html_characters(self):
        form = ComplaintForm(
            data=self.valid_form_data(title="<script>alert('xss')</script>")
        )
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_description_too_short(self):
        form = ComplaintForm(data=self.valid_form_data(description="Too short"))
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_title_is_normalized(self):
        form = ComplaintForm(
            data=self.valid_form_data(title="   Broken   desk in lab   ")
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["title"], "Broken desk in lab")

    def test_assign_form_only_lists_departments(self):
        form = AssignForm()
        queryset = form.fields["department"].queryset
        self.assertIn(self.dept, queryset)
        self.assertNotIn(self.admin, queryset)
        self.assertNotIn(self.student, queryset)

    def test_search_form_rejects_unknown_status(self):
        form = SearchForm(data={"status": "NOT_A_STATUS"})
        self.assertFalse(form.is_valid())


class AuthenticationViewTests(BaseComplaintTestCase):
    def test_login_page_is_public(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")

    def test_email_login_works(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.student.email,
                "password": "testpass123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    def test_invalid_login_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.student.email,
                "password": "wrong-password",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")

    def test_protected_page_redirects_to_login(self):
        response = self.client.get(reverse("dashboard_student"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_logout_is_post_only(self):
        self.login(self.student)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("logout")).status_code, 302)


class DashboardAndCRUDViewTests(BaseComplaintTestCase):
    def test_home_redirects_by_role(self):
        self.login(self.student)
        self.assertRedirects(self.client.get(reverse("home")), reverse("dashboard_student"))
        self.login(self.admin)
        self.assertRedirects(self.client.get(reverse("home")), reverse("dashboard_admin"))
        self.login(self.dept)
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("dashboard_department")
        )

    def test_student_dashboard_only_shows_own_complaints(self):
        self.login(self.student)
        response = self.client.get(reverse("dashboard_student"))
        self.assertContains(response, self.filed.number)
        self.assertNotContains(response, self.other_complaint.number)

    def test_admin_dashboard_shows_all_complaints(self):
        self.login(self.admin)
        response = self.client.get(reverse("dashboard_admin"))
        self.assertContains(response, self.filed.number)
        self.assertContains(response, self.other_complaint.number)

    def test_department_dashboard_only_shows_assigned(self):
        self.login(self.dept)
        response = self.client.get(reverse("dashboard_department"))
        self.assertContains(response, self.assigned.number)
        self.assertNotContains(response, self.filed.number)

    def test_wrong_role_dashboard_redirects(self):
        self.login(self.student)
        response = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))

    def test_student_can_create_complaint(self):
        self.login(self.student)
        response = self.client.post(
            reverse("complaint_create"),
            {
                "title": "New water cooler issue",
                "description": "The water cooler near the library is leaking again.",
                "category": Complaint.Category.INFRASTRUCTURE,
                "priority": Complaint.Priority.HIGH,
            },
        )
        complaint = Complaint.objects.get(title="New water cooler issue")
        self.assertRedirects(
            response, reverse("complaint_detail", args=[complaint.number])
        )
        self.assertEqual(complaint.created_by, self.student)
        self.assertEqual(complaint.status, Complaint.Status.FILED)

    def test_invalid_complaint_form_redisplays_errors(self):
        self.login(self.student)
        response = self.client.post(
            reverse("complaint_create"),
            {
                "title": "Short",
                "description": "Too short",
                "category": Complaint.Category.MESS,
                "priority": Complaint.Priority.LOW,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Title must be at least 8 characters.")
        self.assertContains(response, "Description must be at least 20 characters.")

    def test_owner_can_edit_filed_complaint(self):
        self.login(self.student)
        response = self.client.post(
            reverse("complaint_edit", args=[self.filed.number]),
            {
                "title": "Broken washroom tap fixed?",
                "description": "The tap still runs, so the update is needed today.",
                "category": Complaint.Category.HOSTEL,
                "priority": Complaint.Priority.HIGH,
            },
        )
        self.assertRedirects(
            response, reverse("complaint_detail", args=[self.filed.number])
        )
        self.filed.refresh_from_db()
        self.assertEqual(self.filed.title, "Broken washroom tap fixed?")
        self.assertEqual(self.filed.priority, Complaint.Priority.HIGH)

    def test_edit_denied_once_assigned(self):
        self.login(self.student)
        response = self.client.get(reverse("complaint_edit", args=[self.assigned.number]))
        self.assertEqual(response.status_code, 302)

    def test_owner_can_delete_filed_complaint(self):
        self.login(self.student)
        response = self.client.post(reverse("complaint_delete", args=[self.filed.number]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Complaint.objects.filter(pk=self.filed.pk).exists())

    def test_delete_denied_once_assigned(self):
        self.login(self.student)
        self.client.post(reverse("complaint_delete", args=[self.assigned.number]))
        self.assertTrue(Complaint.objects.filter(pk=self.assigned.pk).exists())

    def test_admin_can_delete_any_complaint(self):
        self.login(self.admin)
        response = self.client.post(reverse("complaint_delete", args=[self.closed.number]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Complaint.objects.filter(pk=self.closed.pk).exists())

    def test_unknown_complaint_returns_404(self):
        self.login(self.admin)
        response = self.client.get(
            reverse("complaint_detail", args=["CMP-9999"])
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False)
    def test_custom_404_page_is_rendered(self):
        self.login(self.admin)
        response = self.client.get(reverse("complaint_detail", args=["CMP-9999"]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "errors/404.html")

    def test_search_by_keyword_and_status(self):
        self.login(self.student)
        response = self.client.get(reverse("search"), {"keyword": "washroom"})
        self.assertContains(response, self.assigned.number)
        self.assertNotContains(response, self.resolved.number)

        response = self.client.get(reverse("search"), {"status": Complaint.Status.CLOSED})
        self.assertContains(response, self.closed.number)
        self.assertNotContains(response, self.filed.number)

    def test_search_by_category(self):
        self.login(self.student)
        response = self.client.get(
            reverse("search"), {"category": Complaint.Category.HOSTEL}
        )
        self.assertContains(response, self.filed.number)
        self.assertNotContains(response, self.closed.number)

    def test_search_invalid_filter_is_handled(self):
        self.login(self.student)
        response = self.client.get(reverse("search"), {"status": "BOGUS"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid search filters")


class WorkflowViewTests(BaseComplaintTestCase):
    def test_full_complaint_lifecycle_through_views(self):
        self.login(self.student)
        self.client.post(
            reverse("complaint_create"),
            {
                "title": "Lifecycle complaint test",
                "description": "This complaint will be used for the full workflow test.",
                "category": Complaint.Category.MESS,
                "priority": Complaint.Priority.MEDIUM,
            },
        )
        complaint = Complaint.objects.get(title="Lifecycle complaint test")

        self.login(self.admin)
        self.client.post(
            reverse("assign_complaint", args=[complaint.number]),
            {"department": self.dept.pk},
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.ASSIGNED)
        self.assertEqual(complaint.assigned_to, self.dept)

        self.login(self.dept)
        self.client.post(reverse("start_complaint", args=[complaint.number]))
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.IN_PROGRESS)

        self.client.post(
            reverse("resolve_complaint", args=[complaint.number]),
            {"remark": "Filter replaced"},
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.RESOLVED)

        self.login(self.student)
        self.client.post(
            reverse("reject_complaint", args=[complaint.number]),
            {"reason": "Still not fixed"},
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.IN_PROGRESS)

        self.login(self.dept)
        self.client.post(
            reverse("resolve_complaint", args=[complaint.number]),
            {"remark": "Second attempt complete"},
        )
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.RESOLVED)

        self.login(self.student)
        self.client.post(reverse("accept_complaint", args=[complaint.number]))
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.CLOSED)
        self.assertIsNotNone(complaint.closed_at)

        self.client.post(reverse("reopen_complaint", args=[complaint.number]))
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, Complaint.Status.REOPENED)
        self.assertEqual(complaint.priority, Complaint.Priority.HIGH)
        self.assertEqual(complaint.history.count(), 7)
        self.assertEqual(complaint.remarks.count(), 3)

    def test_action_without_permission_is_rejected(self):
        self.login(self.student)
        response = self.client.post(
            reverse("start_complaint", args=[self.assigned.number])
        )
        self.assertEqual(response.status_code, 302)
        self.assigned.refresh_from_db()
        self.assertEqual(self.assigned.status, Complaint.Status.ASSIGNED)

    def test_invalid_transition_shows_message(self):
        self.login(self.student)
        self.client.post(reverse("accept_complaint", args=[self.filed.number]))
        self.filed.refresh_from_db()
        self.assertEqual(self.filed.status, Complaint.Status.FILED)

    def test_remark_is_added_through_view(self):
        self.login(self.student)
        response = self.client.post(
            reverse("add_remark", args=[self.assigned.number]),
            {"text": "Please share an update."},
        )
        self.assertRedirects(
            response, reverse("complaint_detail", args=[self.assigned.number])
        )
        self.assertTrue(
            Remark.objects.filter(
                complaint=self.assigned, text="Please share an update."
            ).exists()
        )


class JsonAndNotificationTests(BaseComplaintTestCase):
    def test_stats_api_is_role_scoped(self):
        self.login(self.student)
        response = self.client.get(reverse("api_stats"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = response.json()
        self.assertEqual(data["role"], "STUDENT")
        self.assertEqual(data["total"], 4)
        self.assertEqual(len(data["by_status"]), 6)

        self.login(self.admin)
        data = self.client.get(reverse("api_stats")).json()
        self.assertEqual(data["role"], "ADMIN")
        self.assertEqual(data["total"], 5)

    def test_export_requires_admin(self):
        self.login(self.student)
        response = self.client.get(reverse("export_complaints"))
        self.assertEqual(response.status_code, 302)

    def test_export_returns_valid_json(self):
        self.login(self.admin)
        response = self.client.get(reverse("export_complaints"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        payload = json.loads(response.content)
        self.assertEqual(len(payload), Complaint.objects.count())
        self.assertIn("history", payload[0])
        self.assertIn("remarks", payload[0])

    def test_mark_notifications_read(self):
        notification = Notification.objects.create(
            user=self.student,
            complaint=self.filed,
            message="A notification for testing.",
        )
        self.login(self.student)
        response = self.client.post(
            reverse("mark_notifications_read"),
            {"next": reverse("search")},
        )
        self.assertRedirects(response, reverse("search"))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_notification_redirect_blocks_external_hosts(self):
        self.login(self.student)
        response = self.client.post(
            reverse("mark_notifications_read"),
            {"next": "https://evil.example.com/"},
        )
        self.assertRedirects(
            response, reverse("home"), fetch_redirect_response=False
        )
