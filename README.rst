===================================
Nelp plugin for custom development.
===================================



Features
########

- Courses api endpoint modified. {lms-doamin}/eox-nelp/courses/v1/courses/
- Extra `course_creator` model add option in studio admin.

Installation
############

Open edX devstack
*****************

- Clone this repo in the src folder of your devstack.
- Open a new Lms/Devstack shell.
- Install the plugin as follows: pip install -e /path/to/your/src/folder
- Restart Lms/Studio services.

Usage
#####

Extend `edx-platform` for Nelp requirements without changing base platform code.
