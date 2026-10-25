"""Create the first Officer in Charge account on a new server, with a temporary password."""
import secrets
import string

from django.core.management.base import BaseCommand, CommandError

from api import db
from api.models import OCRISUser
from api.serializers import CreateUserSerializer, UserSerializer
from api.services import accounts

# No 0/O or 1/l/I, so the password can be read out or copied by hand without mistakes
ALPHABET = ''.join(c for c in string.ascii_letters + string.digits if c not in '0O1lI')


def temporary_password(user, length=14):
    """A random password that passes the password rules for this user."""
    while True:
        password = ''.join(secrets.choice(ALPHABET) for _ in range(length))
        if not accounts.password_problems(password, user):
            return password


class Command(BaseCommand):
    help = ('Create an Officer in Charge account with a temporary password, to be changed at the first '
            'sign-in. Meant for a new server (seed.py makes demo accounts); the OIC then creates the other '
            'accounts in the app.')

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--first-name', required=True)
        parser.add_argument('--last-name', required=True)
        parser.add_argument('--employee-id', default=None)
        parser.add_argument('--email', default='')

    def handle(self, *args, username, first_name, last_name, employee_id, email, **options):
        data = {'username': username, 'first_name': first_name, 'last_name': last_name, 'email': email,
                'role': OCRISUser.OIC, 'employee_id': employee_id or None}
        data['password'] = temporary_password(OCRISUser(username=username, first_name=first_name, last_name=last_name))
        s = CreateUserSerializer(data=data)
        if not s.is_valid():
            raise CommandError(' '.join(f'{field}: {" ".join(map(str, problems))}' for field, problems in s.errors.items()))
        user = s.save()
        db.log_action('CREATE_USER', '(manage.py)', {'new_user': user.username, 'role': user.role})
        db.upsert_user_in_mongo(UserSerializer(user).data)
        self.stdout.write(f'Created {user.username} (Officer in Charge).')
        self.stdout.write(f'Temporary password: {data["password"]}')
        self.stdout.write('It is shown only now. It must be changed at the first sign-in.')
