import re

from django.core.exceptions import ValidationError


class LetterAndDigitValidator:
    """A password needs at least one letter and one digit."""

    def validate(self, password, user=None):
        if not (re.search(r'[A-Za-z]', password) and re.search(r'\d', password)):
            raise ValidationError('The password must contain both letters and numbers.', code='letter_and_digit')

    def get_help_text(self):
        return 'Your password must contain both letters and numbers.'
