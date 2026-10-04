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

    class Meta:
        db_table = 'ocris_users'

    def __str__(self):
        return f'{self.get_full_name()} ({self.role})'

    @property
    def is_teacher(self):
        return self.role == self.TEACHER

    def class_scope(self):
        """Grade/section filter a teacher is limited to; empty for OIC and Admin."""
        if not self.is_teacher:
            return {}
        return {
            'grade_level': self.assigned_grade or '',
            'section': self.assigned_section or '',
        }
