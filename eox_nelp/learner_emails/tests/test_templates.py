"""Tests that the default certificate-ready templates exist (packaged) and translate."""
from django.template.loader import get_template
from django.test import TestCase
from django.utils import translation

PATH = "eox_nelp/edx_ace/certificateready/email/"
CONTEXT = {"full_name": "Sara", "course_name": "Cyber", "certificate_url": "https://t/c/abc", "platform_name": "KSU"}


class CertificateReadyTemplatesTestCase(TestCase):
    """The five files ACE renders are found and the copy follows the language."""

    def test_all_parts_exist(self):
        """A missing part would make ACE drop the mail silently."""
        for name in ("subject.txt", "body.txt", "body.html", "head.html", "from_name.txt"):
            get_template(PATH + name)

    def test_copy_in_each_language(self):
        """Subject and text part render in ar, en and fr with the learner's name and link."""
        expected = {"ar": "مبروك Sara!", "en": "Congratulations Sara!", "fr": "Félicitations Sara !"}
        for language, greeting in expected.items():
            with translation.override(language):
                text = get_template(PATH + "body.txt").render(CONTEXT)
                subject = get_template(PATH + "subject.txt").render(CONTEXT)
            self.assertIn(greeting, text)
            self.assertIn("https://t/c/abc", text)
            self.assertNotIn("{{", text + subject)
        with translation.override("ar"):
            self.assertIn("شهادتك جاهزة", get_template(PATH + "subject.txt").render(CONTEXT))

    def test_greeting_without_a_name(self):
        """A blank name gives the plain greeting in every language (text part; the HTML part is checked in previews)."""
        expected = {"ar": "مبروك!", "en": "Congratulations!", "fr": "Félicitations !"}
        for language, greeting in expected.items():
            with translation.override(language):
                text = get_template(PATH + "body.txt").render({**CONTEXT, "full_name": ""})
                self.assertIn(greeting, text)
                self.assertNotIn("Sara", text)
