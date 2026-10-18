"""Check that the audit file has not been changed: its hash chain, and that it agrees with the database."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from api import db
from api.services import audit_chain

SHOWN = 10   # entries listed for each kind of difference


def _describe(entry):
    return f"{entry.get('timestamp')}  {entry.get('action')}  by {entry.get('user')}"


class Command(BaseCommand):
    help = ('Check the audit file (AUDIT_LOG_FILE): that no line was changed, added, moved or removed, and that '
            'it holds every entry the database holds. Fails (exit code 1) when it finds a change.')

    def handle(self, *args, **options):
        path = settings.AUDIT_LOG_FILE
        report = audit_chain.verify(path, db.audit_hashes())
        out = self.stdout
        out.write(f'Audit file: {path}')
        checked = f"{report['entries']} entr{'y' if report['entries'] == 1 else 'ies'} checked"
        if report['unchained']:
            checked += f"; {report['unchained']} older line(s) from before the check was added were not checked"
        out.write(f'  {checked}.')

        for number, problem in report['problems']:
            out.write(f'  Line {number} {problem}.')
        for number in report['cut_off']:
            out.write(f'  Note: line {number} was left half-written, as when the server stops while writing it; '
                      'the entry was not saved.')
        if report['missing']:
            many = len(report['missing']) != 1
            out.write(f"  {len(report['missing'])} {'entries' if many else 'entry'} in the database {'are' if many else 'is'} "
                      'not in the file: the end of the file was cut off or the file was replaced (or this database '
                      'was restored on a server with another audit file).')
            for entry in db.audit_entries_with_hashes(report['missing'][:SHOWN]):
                out.write(f'    {_describe(entry)}')
        if report['extra']:
            out.write(f"  Note: {len(report['extra'])} entr{'y is' if len(report['extra']) == 1 else 'ies are'} in the file "
                      'but not in the database: deleted from the database, or the database was restored from an older backup.')
            for entry in report['extra'][:SHOWN]:
                out.write(f"    line {entry['line']}: {_describe(entry)}")

        failures = len(report['problems']) + len(report['missing'])
        if failures:
            raise CommandError(f'The audit file failed the check ({failures} finding(s) above).')
        out.write(self.style.SUCCESS('  No changes found.'))
