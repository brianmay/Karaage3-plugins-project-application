import six

import django_tables2 as tables
from django_tables2.utils import A
from django_tables2.columns.linkcolumn import BaseLinkColumn
import django_filters

from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse

from .models import ProjectApplication
from karaage.projects.models import Project


class ProjectApplicationFilter(django_filters.FilterSet):
    id = django_filters.NumberFilter()
    ALL_STATES = (('', 'All'),) + ProjectApplication.APPLICATION_STATES
    state = django_filters.ChoiceFilter(choices=ALL_STATES)
    created_by = django_filters.CharFilter(lookup_expr='icontains', label="created_by")
    ### TODO: filter on Project in project OR associated
    ### TODO: filter on person from all fields, created_by, members, supervisor

    class Meta:
        model = ProjectApplication
        fields = ('id', 'state', 'created_by',)


class ProjectApplicationTable(tables.Table):
    #  show application ID number but link to secret token via 'application_id'
    id = tables.LinkColumn(
        'view_project_application', args=[A('application_id')], verbose_name="Application ID")
    pid = tables.LinkColumn(
        'kg_project_detail', args=[A('project_id')], verbose_name="Project")

    class Meta:
        model = ProjectApplication
        fields = ('id', 'created_by', 'supervisor', 'pid', 'state', 'expires',)
        order_by = ('-id')
