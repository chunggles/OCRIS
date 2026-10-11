from django.contrib.auth.models import AbstractUser
from django.db import models


class OCRISUser(AbstractUser):
    OIC = 'OIC'
    ADMIN = 'ADMIN'
    TEACHER = 'TEACHER'
    ROLE_CHOICES = [
        (OIC, 'Officer in Charge'),
        (ADMIN, 'Admin Staff'),
        (TEACHER, 'Teacher'),
    ]

    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=TEACHER)
    employee_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    assigned_grade = models.CharField(max_length=20, blank=True, null=True)
    assigned_section = models.CharField(max_length=50, blank=True, null=True)
    # Set when the OIC creates the account or sets a new password: the temporary password must be
    # replaced at the next sign-in before anything else can be done.
    must_change_password = models.BooleanField(default=False)
    # Set when the user asked for a reset from the login screen; cleared when the OIC sets a new password.
    password_reset_requested_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'ocris_users'

    def __str__(self):
        return f'{self.get_full_name()} ({self.role})'

    @property
    def is_teacher(self):
        return self.role == self.TEACHER

    @property
    def missing_class(self):
        """A teacher with no grade or section assigned; they may not see any class data."""
        return self.is_teacher and not (self.assigned_grade and self.assigned_section)

    def class_scope(self):
        """Grade/section filter a teacher is limited to; empty for OIC and Admin."""
        if not self.is_teacher:
            return {}
        return {
            'grade_level': self.assigned_grade or '',
            'section': self.assigned_section or '',
        }

    def can_access(self, doc):
        """Whether a record or scan belongs to a class this user may see."""
        if not self.is_teacher:
            return True
        if self.missing_class:
            return False
        return (doc.get('grade_level') == self.assigned_grade
                and (doc.get('section') or '').casefold() == self.assigned_section.casefold())


class LoginSession(models.Model):
    """
    One sign-in on one device. A user may have several at once; signing out ends only the one
    used. The key travels in an HttpOnly cookie, so scripts on the page cannot read it.
    """
    key = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(OCRISUser, on_delete=models.CASCADE, related_name='login_sessions')
    created = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'ocris_login_sessions'


class AuthAttempt(models.Model):
    """A failed sign-in or a password-reset request, kept to limit how often they can be made."""
    LOGIN = 'login'
    RESET = 'reset'

    kind = models.CharField(max_length=10)
    username = models.CharField(max_length=150, blank=True, default='')
    ip = models.CharField(max_length=45, blank=True, default='')
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'ocris_auth_attempts'
        indexes = [models.Index(fields=['kind', 'username', 'at']), models.Index(fields=['kind', 'ip', 'at'])]
