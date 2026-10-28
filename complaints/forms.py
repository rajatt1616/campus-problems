from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import RegexValidator

from .models import Complaint, User

INPUT_CLASS = (
    "h-10 w-full rounded-md border border-border px-3 text-base text-ink "
    "placeholder:text-muted focus:border-primary focus:outline-none "
    "focus:ring-2 focus:ring-primary/30"
)
SELECT_CLASS = (
    "h-10 w-full rounded-md border border-border bg-card px-3 text-base text-ink "
    "focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
)
TEXTAREA_CLASS = (
    "w-full rounded-md border border-border px-3 py-2 text-base text-ink "
    "placeholder:text-muted focus:border-primary focus:outline-none "
    "focus:ring-2 focus:ring-primary/30"
)

TITLE_VALIDATOR = RegexValidator(
    regex=r"^\s*[A-Za-z0-9][A-Za-z0-9\s\-',.()&/?!:;]*\s*$",
    message=(
        "Title can contain letters, numbers, spaces and basic punctuation "
        "(- ' , . ( ) & / ? ! : ;) only."
    ),
)


class ComplaintForm(forms.ModelForm):
    title = forms.CharField(
        max_length=120,
        min_length=8,
        validators=[TITLE_VALIDATOR],
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Short summary of the issue",
                "autofocus": True,
                "data-counter-target": "title-count",
            }
        ),
        error_messages={
            "min_length": "Title must be at least 8 characters.",
            "max_length": "Title must be at most 120 characters.",
        },
    )
    description = forms.CharField(
        min_length=20,
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASS,
                "rows": 5,
                "placeholder": "What happened, where, and when",
                "data-counter-target": "description-count",
            }
        ),
        error_messages={
            "min_length": "Description must be at least 20 characters.",
        },
    )

    class Meta:
        model = Complaint
        fields = ["title", "description", "category", "priority"]
        widgets = {
            "category": forms.Select(attrs={"class": SELECT_CLASS}),
            "priority": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def clean_title(self):
        title = " ".join(self.cleaned_data["title"].split())
        if len(title) < 8:
            raise forms.ValidationError("Title must be at least 8 characters.")
        return title

    def clean_description(self):
        description = self.cleaned_data["description"].strip()
        if len(description) < 20:
            raise forms.ValidationError(
                "Description must be at least 20 characters."
            )
        return description


class DepartmentChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, user):
        return f"{user.department} — {user.name}"


class AssignForm(forms.Form):
    department = DepartmentChoiceField(
        queryset=User.objects.none(),
        label="Department",
        empty_label="Select a department",
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = User.objects.filter(
            role=User.Role.DEPARTMENT
        ).order_by("department", "name")


class RemarkForm(forms.Form):
    text = forms.CharField(
        max_length=500,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Add a remark…",
            }
        ),
    )

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if not text:
            raise forms.ValidationError("Remark cannot be empty.")
        return text


class ResolutionForm(forms.Form):
    remark = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": TEXTAREA_CLASS,
                "rows": 3,
                "placeholder": "Resolution note (optional)",
            }
        ),
    )


class RejectForm(forms.Form):
    reason = forms.CharField(
        min_length=5,
        max_length=300,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "Reason for rejecting",
            }
        ),
        error_messages={
            "min_length": "Please give a reason of at least 5 characters.",
        },
    )


class SearchForm(forms.Form):
    keyword = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "ID, title or description",
            }
        ),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Any status")] + list(Complaint.Status.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    category = forms.ChoiceField(
        required=False,
        choices=[("", "Any category")] + list(Complaint.Category.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="College email",
        widget=forms.EmailInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "you@srmist.edu",
                "autofocus": True,
                "autocomplete": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": INPUT_CLASS,
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )
    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }
