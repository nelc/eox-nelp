"""ACE message types of the learner e-mails.

The template folder of a message is `<APP_LABEL>/edx_ace/<lower-cased class name>/email/`, so
`CertificateReady` lives in `eox_nelp/templates/eox_nelp/edx_ace/certificateready/email/`. A theme
overrides the e-mail by shipping a file with the same path.
"""
from eox_nelp.edxapp_wrapper.learner_emails import BaseMessageType


class CertificateReady(BaseMessageType):
    """The learner's certificate was issued and can be opened."""
    APP_LABEL = "eox_nelp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options["transactional"] = True


class LearningStarts(BaseMessageType):
    """The course the learner enrolled in before its start has started (Message 3)."""
    APP_LABEL = "eox_nelp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options["transactional"] = True


class CompletionReminder(BaseMessageType):
    """The learner is close to completing the course, by progress or by the course end date (Message 5)."""
    APP_LABEL = "eox_nelp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.options["transactional"] = True
