"""Course discovery (/courses catalog) with the eox-nelp listing rule.

edx-search's stock `course_discovery_search` lists a course only until its enrollment end. FutureX lists a
course until the course itself ends. `eox_nelp.init_pipeline.take_over_course_discovery_route` points
edx-search's `course_discovery` route at `views.course_discovery`, and `make_course_end_filterable` adds
`end` to the Meilisearch filterable attributes of the course_info index.
"""
