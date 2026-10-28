import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .decorators import role_required
from .exceptions import CampusComplaintError
from .forms import (
    AssignForm,
    ComplaintForm,
    EmailAuthenticationForm,
    RejectForm,
    RemarkForm,
    ResolutionForm,
    SearchForm,
)
from .models import Complaint, User


class ComplaintLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class ComplaintLogoutView(LogoutView):
    next_page = "login"


def dashboard_url(user):
    if user.is_department:
        return reverse("dashboard_department")
    if user.is_administrator:
        return reverse("dashboard_admin")
    return reverse("dashboard_student")


@login_required
def home(request):
    return redirect(dashboard_url(request.user))


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    complaints = services.visible_complaints_for(request.user)
    stats = [
        {"label": "Total filed", "value": complaints.count()},
        {
            "label": "Open",
            "value": complaints.exclude(status=Complaint.Status.CLOSED).count(),
        },
        {
            "label": "Awaiting you",
            "value": complaints.filter(status=Complaint.Status.RESOLVED).count(),
        },
        {
            "label": "Closed",
            "value": complaints.filter(status=Complaint.Status.CLOSED).count(),
        },
    ]
    return render(
        request,
        "dashboard.html",
        {
            "complaints": complaints,
            "stats": stats,
            "page": "student",
            "active": "dashboard",
        },
    )


@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    complaints = Complaint.objects.select_related("created_by", "assigned_to")
    stats = [
        {"label": "Total", "value": complaints.count()},
        {
            "label": "Unassigned",
            "value": complaints.filter(status=Complaint.Status.FILED).count(),
        },
        {
            "label": "In progress",
            "value": complaints.filter(
                status=Complaint.Status.IN_PROGRESS
            ).count(),
        },
        {
            "label": "Closed",
            "value": complaints.filter(status=Complaint.Status.CLOSED).count(),
        },
    ]
    return render(
        request,
        "dashboard.html",
        {
            "complaints": complaints,
            "stats": stats,
            "departments": services.department_accounts(),
            "page": "admin",
            "active": "dashboard",
        },
    )


@role_required(User.Role.DEPARTMENT)
def department_dashboard(request):
    complaints = services.visible_complaints_for(request.user)
    stats = [
        {"label": "Assigned to me", "value": complaints.count()},
        {
            "label": "In progress",
            "value": complaints.filter(
                status=Complaint.Status.IN_PROGRESS
            ).count(),
        },
        {
            "label": "Awaiting student",
            "value": complaints.filter(status=Complaint.Status.RESOLVED).count(),
        },
        {
            "label": "Closed",
            "value": complaints.filter(status=Complaint.Status.CLOSED).count(),
        },
    ]
    return render(
        request,
        "dashboard.html",
        {
            "complaints": complaints,
            "stats": stats,
            "page": "department",
            "active": "dashboard",
        },
    )


@role_required(User.Role.STUDENT)
def complaint_create(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST)
        if form.is_valid():
            try:
                complaint = services.create_complaint(
                    request.user,
                    form.cleaned_data["title"],
                    form.cleaned_data["description"],
                    form.cleaned_data["category"],
                    form.cleaned_data["priority"],
                )
            except CampusComplaintError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"Complaint {complaint.number} filed.")
                return redirect(
                    "complaint_detail",
                    number=complaint.number,
                )
    else:
        form = ComplaintForm()

    return render(
        request,
        "complaints/form.html",
        {
            "form": form,
            "heading": "File a Complaint",
            "eyebrow": "New Complaint",
            "submit_label": "Submit Complaint",
            "active": "new",
        },
    )


@login_required
def complaint_detail(request, number):
    complaint = get_object_or_404(
        Complaint.objects.select_related("created_by", "assigned_to"),
        number__iexact=number,
    )
    user = request.user
    is_owner = user.is_student and complaint.created_by_id == user.id
    is_assigned_department = (
        user.is_department and complaint.assigned_to_id == user.id
    )

    context = {
        "c": complaint,
        "departments": services.department_accounts() if user.is_administrator else None,
        "assign_form": AssignForm(),
        "remark_form": RemarkForm(),
        "resolution_form": ResolutionForm(),
        "reject_form": RejectForm(),
        "is_owner": is_owner,
        "is_assigned_department": is_assigned_department,
        "can_assign": user.is_administrator
        and complaint.status == Complaint.Status.FILED,
        "can_start": is_assigned_department
        and complaint.status in {Complaint.Status.ASSIGNED, Complaint.Status.REOPENED},
        "can_resolve": is_assigned_department
        and complaint.status == Complaint.Status.IN_PROGRESS,
        "can_accept": is_owner and complaint.status == Complaint.Status.RESOLVED,
        "can_reject": is_owner and complaint.status == Complaint.Status.RESOLVED,
        "can_reopen": is_owner and complaint.can_reopen,
        "can_edit": services.can_edit(user, complaint),
        "can_delete": services.can_delete(user, complaint),
        "active": "",
    }
    return render(request, "complaints/detail.html", context)


@role_required(User.Role.STUDENT)
def complaint_edit(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    if not services.can_edit(request.user, complaint):
        messages.error(
            request,
            "Only the complainant can edit a complaint while it is still filed.",
        )
        return redirect("complaint_detail", number=complaint.number)

    if request.method == "POST":
        form = ComplaintForm(request.POST, instance=complaint)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.updated_at = timezone.now()
            complaint.save()
            messages.success(request, "Complaint updated.")
            return redirect("complaint_detail", number=complaint.number)
    else:
        form = ComplaintForm(instance=complaint)

    return render(
        request,
        "complaints/form.html",
        {
            "form": form,
            "complaint": complaint,
            "heading": f"Edit {complaint.number}",
            "eyebrow": "Update Complaint",
            "submit_label": "Save Changes",
            "active": "",
        },
    )


@login_required
def complaint_delete(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    if not services.can_delete(request.user, complaint):
        messages.error(
            request,
            "You cannot delete this complaint once it has been assigned.",
        )
        return redirect("complaint_detail", number=complaint.number)

    if request.method == "POST":
        label = complaint.number
        complaint.delete()
        messages.success(request, f"Complaint {label} deleted.")
        return redirect(dashboard_url(request.user))

    return render(
        request,
        "complaints/confirm_delete.html",
        {"c": complaint, "active": ""},
    )


@role_required(User.Role.ADMIN)
@require_POST
def assign_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    form = AssignForm(request.POST)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, first_error)
        return redirect("complaint_detail", number=complaint.number)
    try:
        services.assign_complaint(
            request.user,
            complaint,
            form.cleaned_data["department"],
        )
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Complaint assigned.")
    return redirect("complaint_detail", number=complaint.number)


@role_required(User.Role.DEPARTMENT)
@require_POST
def start_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    try:
        services.start_work(request.user, complaint)
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Work started.")
    return redirect("complaint_detail", number=complaint.number)


@role_required(User.Role.DEPARTMENT)
@require_POST
def resolve_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    form = ResolutionForm(request.POST)
    remark = ""
    if form.is_valid():
        remark = form.cleaned_data.get("remark", "").strip()
    try:
        services.resolve_complaint(request.user, complaint, remark)
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Complaint marked resolved.")
    return redirect("complaint_detail", number=complaint.number)


@role_required(User.Role.STUDENT)
@require_POST
def accept_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    try:
        services.accept_complaint(request.user, complaint)
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Complaint closed. Thank you for confirming.")
    return redirect("complaint_detail", number=complaint.number)


@role_required(User.Role.STUDENT)
@require_POST
def reject_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    form = RejectForm(request.POST)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, first_error)
        return redirect("complaint_detail", number=complaint.number)
    try:
        services.reject_complaint(
            request.user,
            complaint,
            form.cleaned_data["reason"],
        )
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Resolution rejected. Work will resume.")
    return redirect("complaint_detail", number=complaint.number)


@role_required(User.Role.STUDENT)
@require_POST
def reopen_complaint(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    try:
        services.reopen_complaint(request.user, complaint)
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Complaint reopened with a higher priority.")
    return redirect("complaint_detail", number=complaint.number)


@login_required
@require_POST
def add_remark(request, number):
    complaint = get_object_or_404(Complaint, number__iexact=number)
    form = RemarkForm(request.POST)
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        messages.error(request, first_error)
        return redirect("complaint_detail", number=complaint.number)
    try:
        services.add_remark(request.user, complaint, form.cleaned_data["text"])
    except CampusComplaintError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Remark added.")
    return redirect("complaint_detail", number=complaint.number)


@login_required
def search(request):
    form = SearchForm(request.GET or None)
    results = Complaint.objects.select_related("created_by", "assigned_to")

    if request.GET and not form.is_valid():
        messages.error(request, "Invalid search filters; showing all complaints.")
    elif form.is_valid():
        keyword = form.cleaned_data.get("keyword", "").strip()
        status = form.cleaned_data.get("status", "")
        category = form.cleaned_data.get("category", "")
        if keyword:
            results = results.filter(
                Q(number__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(description__icontains=keyword)
            )
        if status:
            results = results.filter(status=status)
        if category:
            results = results.filter(category=category)

    return render(
        request,
        "search.html",
        {
            "form": form,
            "results": results,
            "active": "search",
        },
    )


@login_required
@require_POST
def mark_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect("home")


@login_required
def api_stats(request):
    complaints = services.visible_complaints_for(request.user)
    status_counts = {
        value: complaints.filter(status=value).count()
        for value, _label in Complaint.Status.choices
    }
    category_counts = {
        value: complaints.filter(category=value).count()
        for value, _label in Complaint.Category.choices
    }
    data = {
        "role": request.user.role,
        "total": complaints.count(),
        "by_status": [
            {"key": value, "label": label, "count": status_counts[value]}
            for value, label in Complaint.Status.choices
        ],
        "by_category": [
            {"key": value, "label": label, "count": category_counts[value]}
            for value, label in Complaint.Category.choices
        ],
        "generated_at": timezone.now().isoformat(),
    }
    return JsonResponse(data)


@role_required(User.Role.ADMIN)
def export_complaints(request):
    complaints = (
        Complaint.objects.select_related("created_by", "assigned_to")
        .prefetch_related("remarks", "history")
        .all()
    )
    payload = []
    for complaint in complaints:
        payload.append(
            {
                "number": complaint.number,
                "title": complaint.title,
                "description": complaint.description,
                "category": complaint.category,
                "category_label": complaint.get_category_display(),
                "priority": complaint.priority,
                "priority_label": complaint.get_priority_display(),
                "status": complaint.status,
                "status_label": complaint.get_status_display(),
                "created_by": {
                    "name": complaint.created_by.name,
                    "email": complaint.created_by.email,
                },
                "assigned_to": (
                    {
                        "name": complaint.assigned_to.name,
                        "department": complaint.assigned_to.department,
                    }
                    if complaint.assigned_to
                    else None
                ),
                "created_at": complaint.created_at.isoformat(),
                "updated_at": complaint.updated_at.isoformat(),
                "closed_at": (
                    complaint.closed_at.isoformat() if complaint.closed_at else None
                ),
                "remarks": [
                    {
                        "author": remark.author_name,
                        "role": remark.author_role,
                        "text": remark.text,
                        "created_at": remark.created_at.isoformat(),
                    }
                    for remark in complaint.remarks.all()
                ],
                "history": [
                    {
                        "from": event.from_status,
                        "to": event.to_status,
                        "actor": event.actor_name,
                        "note": event.note,
                        "at": event.created_at.isoformat(),
                    }
                    for event in complaint.history.all()
                ],
            }
        )

    body = json.dumps(payload, indent=2, ensure_ascii=False)
    response = HttpResponse(body, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = (
        'attachment; filename="campuscomplaints-export.json"'
    )
    return response


def error_400(request, exception):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
