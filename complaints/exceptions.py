class CampusComplaintError(Exception):
    """Base class for expected domain errors."""


class WorkflowError(CampusComplaintError):
    """Raised when a complaint status transition is not allowed."""


class AccessDenied(CampusComplaintError):
    """Raised when a user attempts an action they are not allowed to perform."""
