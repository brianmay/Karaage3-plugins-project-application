from django.conf.urls import url, include

from . import views

urlpatterns = [
    url(r'^list/$', views.project_application_list, name='project_application_list'),
    url(r'^institute/$', views.project_application_faculty, name='project_application_faculty'),
    url(r'^start/$', views.full_project_application, name='start_project_application'),

    url(r'^(?P<token>.+)/done/$', views.project_application_done, name='project_application_done'),
    url(r'^(?P<token>.+)/parta/$', views.project_application_parta, name='project_application_parta'),
    url(r'^(?P<token>.+)/partb/$', views.project_application_partb, name='project_application_partb'),
    url(r'^(?P<token>.+)/partc/$', views.project_application_partc, name='project_application_partc'),
    url(r'^(?P<token>.+)/pdf/$', views.project_application_pdf, name='project_application_pdf'),
    url(r'^(?P<token>.+)/view/$', views.project_application_view, name='view_project_application'),
    url(r'^(?P<token>.+)/approve/$', views.project_application_approve, name='approve_project_application'),
    url(r'^(?P<token>.+)/decline/$', views.project_application_decline, name='decline_project_application'),
    url(r'^(?P<token>.+)/delete/$', views.project_application_delete, name='delete_project_application'),
    url(r'^(?P<token>.+)/add_comment/$',
                views.project_application_add_comment, name='project_application_add_comment'),
    url(r'^(?P<token>.+)/$', views.submit_project_application, name='project_application_submit'),

    url(r'^$', views.project_application_info, name='linkto_project_application'),
]

urlpatterns = [
    url(r'^apply/', include(urlpatterns)),
]
