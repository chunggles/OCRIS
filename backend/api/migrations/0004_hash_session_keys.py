import hashlib

from django.db import migrations


def hash_keys(apps, schema_editor):
    """Store the SHA-256 of each sign-in cookie instead of the cookie itself; nobody is signed out."""
    LoginSession = apps.get_model('api', 'LoginSession')
    for key in list(LoginSession.objects.values_list('key', flat=True)):
        LoginSession.objects.filter(key=key).update(key=hashlib.sha256(key.encode('utf-8')).hexdigest())


def sign_everyone_out(apps, schema_editor):
    """A hash cannot be turned back into its cookie, so going back ends every session."""
    apps.get_model('api', 'LoginSession').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_session_last_active'),
    ]

    operations = [
        migrations.RunPython(hash_keys, sign_everyone_out),
    ]
