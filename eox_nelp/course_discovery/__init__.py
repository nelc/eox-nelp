"""Course discovery (/courses catalog) with the eox-nelp listing rule.

edx-search's stock `course_discovery_search` lists a course only while enrollment is open. FutureX lists a
course while enrollment is open OR the course has not ended, so nothing the stock rule lists disappears.
`eox_nelp.init_pipeline.take_over_course_discovery_route` points edx-search's `course_discovery` route at
`views.course_discovery`, and `make_course_end_filterable` adds `end` to the Meilisearch filterable attributes
of the course_info index.
"""
