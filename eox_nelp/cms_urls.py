"""eox_nelp CMS URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import path, include
    2. Add a URL to urlpatterns:  path(r'^blog/', include('blog.urls'))
"""
from django.urls import include, path

from eox_nelp import views

app_name = 'eox_nelp'  # pylint: disable=invalid-name

urlpatterns = [
    path('eox-info/', views.info_view, name='eox-info'),
    path('api/', include('eox_nelp.cms.api.urls', namespace='cms-api')),
    path('api/programs/', include('eox_nelp.programs.api.urls', namespace='programs-api')),
]
