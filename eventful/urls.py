from django.conf.urls import url
from django.views.generic.edit import CreateView
from . import views
from django.contrib.auth.decorators import login_required

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^register/', views.register.as_view(), name='register'), 
    url(r'^create/', views.create, name='create'), 
    url(r'^add/', views.add, name='add'),
    url(r'^manage/', views.manage, name='manage'),
    url(r'^inbound/', views.sms, name='sms'),
    url(r'^logout/', views.logout_view, name='logout'),
    url(r'^end/', views.end, name='end'),
    url(r'^settings/', views.event_settings, name='settings'),
    url(r'^volunteers/', views.volunteers, name='volunteers')
]