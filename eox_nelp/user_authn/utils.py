import random
import string
from django.conf import settings

def password_rules():
    """
    Inspect the validators defined in AUTH_PASSWORD_VALIDATORS and define
    a rule list with the set of available characters and their minimum
    for a specific charset category (alphabetic, digits, uppercase, etc).
    This is based on the validators defined in
    common.djangoapps.util.password_policy_validators and
    django_password_validators.password_character_requirements.password_validation.PasswordCharacterValidator
    """
    password_validators = settings.AUTH_PASSWORD_VALIDATORS
    rules = {
        "alpha": [string.ascii_letters, 0],
        "digit": [string.digits, 0],
        "upper": [string.ascii_uppercase, 0],
        "lower": [string.ascii_lowercase, 0],
        "punctuation": [string.punctuation, 0],
        "symbol": ["£¥€©®™†§¶πμ'±", 0],
        "min_length": ["", 0],
    }
    options_mapping = {
        "min_alphabetic": "alpha",
        "min_length_alpha": "alpha",
        "min_length_digit": "digit",
        "min_length_upper": "upper",
        "min_length_lower": "lower",
        "min_lower": "lower",
        "min_upper": "upper",
        "min_numeric": "digit",
        "min_symbol": "symbol",
        "min_punctuation": "punctuation",
    }

    for validator in password_validators:
        for option, mapping in options_mapping.items():
            if not validator.get("OPTIONS"):
                continue
            rules[mapping][1] = max(
                rules[mapping][1], validator["OPTIONS"].get(option, 0)
            )
        # We handle PasswordCharacterValidator separately because it can define
        # its own set of special characters.
        if (
            validator["NAME"] ==
            "django_password_validators.password_character_requirements.password_validation.PasswordCharacterValidator"
        ):
            min_special = validator["OPTIONS"].get("min_length_special", 0)
            special_chars = validator["OPTIONS"].get(
                "special_characters", "~!@#$%^&*()_+{}\":;'[]"
            )
            rules["special"] = [special_chars, min_special]

    return rules


def generate_password(length=12, chars=string.ascii_letters + string.digits):
    """Generate a valid random password.
    The original `generate_password` doesn't account for extra validators
    This picks the minimum amount of characters for each charset category.
    """
    if length < 8:
        raise ValueError("password must be at least 8 characters")

    password = ""
    password_length = length
    choice = random.SystemRandom().choice
    rules = password_rules()
    min_length = rules.pop("min_length")[1]
    password_length = max(min_length, length)

    for elems in rules.values():
        choices = elems[0]
        needed = elems[1]
        for _ in range(needed):
            next_char = choice(choices)
            password += next_char

    # fill the password to reach password_length
    if len(password) < password_length:
        password += "".join(
            [choice(chars) for _ in range(password_length - len(password))]
        )

    password_list = list(password)
    random.shuffle(password_list)

    password = "".join(password_list)
    return password
