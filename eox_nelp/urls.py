"""eox_nelp URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.urls import include, path

from eox_nelp import views

app_name = 'eox_nelp'  # pylint: disable=invalid-name

urlpatterns = [
    path('eox-info/', views.info_view, name='eox-info'),
    path('courses/', include('eox_nelp.course_api.urls', namespace='nelp-course-api')),
    path('api/mfe_config/', include('eox_nelp.mfe_config_api.urls', namespace='mfe-config-api')),
    path('api/experience/', include('eox_nelp.course_experience.api.urls', namespace='course-experience-api')),
    path(
        'frontend/experience/',
        include('eox_nelp.course_experience.frontend.urls', namespace='course-experience-frontend'),
    ),
    path('api/stats/', include('eox_nelp.stats.api.urls', namespace='stats-api')),
    path('stats/', include('eox_nelp.stats.urls', namespace='stats')),
    path('payment-notifications/', include('eox_nelp.payment_notifications.urls', namespace='payment-notifications')),
    path('api/user-profile/', include('eox_nelp.user_profile.api.urls', namespace='user-profile-api')),
    path('api/one-time-password/', include('eox_nelp.one_time_password.api.urls', namespace='one-time-password-api')),
    path(
        'api/external-certificates/',
        include('eox_nelp.external_certificates.api.urls', namespace='external-certificates-api'),
    ),
    path('api/users/', include('eox_nelp.users.urls', namespace='users')),
]
