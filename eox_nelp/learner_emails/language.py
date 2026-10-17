"""Language an e-mail is written in."""

# Languages the e-mails (and their catalogues) exist in. `fr` works through the fr_CA -> fr alias.
SUPPORTED_LANGUAGES = ("ar", "en", "fr")
DEFAULT_LANGUAGE = "en"


def _supported(code):
    """Return the supported language for a code like "ar", "fr_CA" or "en-us", else None."""
    primary = (code or "").replace("_", "-").split("-")[0].lower()

    return primary if primary in SUPPORTED_LANGUAGES else None


def resolve_language(course_language, user_language):
    """Pick the e-mail language: course language, then the learner's saved one, then English.

    A code with no e-mail catalogue (say "ur") is skipped, not translated into something else:
    the next source in the chain is tried, and English is the documented end of the chain.
    """
    return _supported(course_language) or _supported(user_language) or DEFAULT_LANGUAGE
