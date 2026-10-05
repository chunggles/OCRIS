"""Create the default OCRIS accounts and sections. Run with: python seed.py"""
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ocris_backend.settings')
django.setup()

from api import db  # noqa: E402  (needs django.setup() first)
from api.models import OCRISUser  # noqa: E402

# Set SEED_PASSWORD in backend/.env (loaded by settings.py).
DEFAULT_PASSWORD = os.environ.get('SEED_PASSWORD')

# username, first name, last name, role, assigned grade, assigned section, employee ID
USERS = [
    ('k.saquing',  'K.',     'Saquing',   OCRISUser.OIC,     None,      None,         'BCS-OIC-001'),
    ('j.aquino',   'J.',     'Aquino',    OCRISUser.ADMIN,   None,      None,         'BCS-ADM-001'),
    ('g.ramos',    'Gloria', 'Ramos',     OCRISUser.TEACHER, 'Grade 6', 'Sampaguita', 'BCS-TCH-001'),
    ('m.delacruz', 'M.',     'Dela Cruz', OCRISUser.TEACHER, 'Grade 5', 'Orchid',     'BCS-TCH-002'),
    ('r.santos',   'R.',     'Santos',    OCRISUser.TEACHER, 'Grade 4', 'Rosal',      'BCS-TCH-003'),
]


def seed_sections():
    """Add the classes of the teachers above to the section tree, so they can pick them when uploading."""
    print('Seeding sections...')
    for _, _, _, _, grade, section, _ in USERS:
        if not (grade and section):
            continue
        if db.find_section(section, grade):
            print(f'  Already exists: {grade} — {section}')
        else:
            db.create_section(section, grade)
            print(f'  Created: {grade} — {section}')


def main():
    if not DEFAULT_PASSWORD:
        raise SystemExit('SEED_PASSWORD is not set. Add it to backend/.env.')
    seed_sections()
    print('Seeding OCRIS users...')
    for username, first, last, role, grade, section, employee_id in USERS:
        if OCRISUser.objects.filter(username=username).exists():
            print(f'  Already exists: {username}')
            continue
        OCRISUser.objects.create_user(
            username=username, password=DEFAULT_PASSWORD, first_name=first, last_name=last,
            role=role, employee_id=employee_id, assigned_grade=grade, assigned_section=section,
        )
        print(f'  Created: {username} ({role})')
    print('\nDone. Log in as k.saquing with SEED_PASSWORD.')


if __name__ == '__main__':
    main()
