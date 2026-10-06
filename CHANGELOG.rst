Change Log
==========

..
   All enhancements and patches to eox_nelp will be documented
   in this file.  It adheres to the structure of http://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (http://semver.org/).
.. There should always be an "Unreleased" section for changes pending release.
Unreleased
----------

Added
~~~~~
* ``eox_nelp.mail.backends.PooledSMTPEmailBackend``: an SMTP email backend that keeps one authenticated
  session open per process and thread, instead of reconnecting for every message.

[1.0.0] - 2022-10-18
---------------------

Added
~~~~~
* Maple compatibility.
Removed
~~~~~
* Koa compatibility

[0.2.1] - 2022-09-19
---------------------

Added
~~~~~
* Add image url functionality to courses endpoint.


[0.2.0] - 2022-08-23
---------------------

Added
~~~~~
* User search button to add user in course creator model admin.

[0.1.0] - 2022-08-22
---------------------

Added
~~~~~
* Admin `course_creator` model to studio.


Changed
~~~~~~~
* **BREAKING CHANGE**: Remove unnecessary files from `eox-core` ancestors
* **BREAKING CHANGE**: Changed plugin settings to the requirement of nelp.
* **BREAKING CHANGE**: Copy from edx-platform and Keep only course_api to customize the courses endpoint.

[0.0.0] - 2022-03-30
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Added
~~~~~
* Hello world for the plugin. Starting in Koa.
