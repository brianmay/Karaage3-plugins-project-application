from django.db import models
from django.conf import settings

import datetime

from karaage.common import new_random_token
from karaage.institutes.models import Institute
from karaage.projects.models import Project
from karaage.people.models import Person
from .fields import TextLengthField

import project_application.for_choices as for_choices

class ProjectApplication(models.Model):
    NEW = 'N'
    OPEN = 'O'
    WAITING_FOR_REVIEW = 'L'
    WAITING_FOR_ADMIN = 'K'
    COMPLETE = 'C'
    ARCHIVED = 'A'
    DECLINED = 'R'
    APPLICATION_STATES = (
        (NEW, 'Invitiation Sent'),
        (OPEN, 'Open'),
        (WAITING_FOR_REVIEW, 'Waiting for review'),
        (WAITING_FOR_ADMIN, 'Waiting for Karaage admin processing'),
        (COMPLETE, 'Complete'),
        (ARCHIVED, 'Archived'),
        (DECLINED, 'Declined'),
        )

    secret_token = models.CharField(max_length=64, default=new_random_token, editable=False, unique=True)
    expires = models.DateTimeField()
    created_by = models.EmailField(editable=False)
    created_date = models.DateTimeField(auto_now_add=True, editable=False)
    submitted_date = models.DateTimeField(null=True, blank=True)
    complete_date = models.DateTimeField(null=True, blank=True, editable=False)

    state = models.CharField(max_length=1, choices=APPLICATION_STATES, default=NEW)
    project = models.ForeignKey(Project, null=True, blank=True, related_name='project_application')
    host_institute = models.CharField(max_length=200, null=True, blank=True)
    host_faculty = models.CharField(max_length=200, null=True, blank=True)
    host_school = models.CharField(max_length=200, null=True, blank=True)

    tac = models.BooleanField(default=False)

    FOR = models.CharField(max_length=100, choices=for_choices.FOR_CHOICES)

    # Project Information
    title = models.CharField('Project Title', max_length=100, null=True, blank=True)
    summary = TextLengthField('Summary of Project', null=True, blank=True, max_length=2000)
    purpose = TextLengthField('Suported Activity', null=True, blank=True, max_length=2000)

    # Resource Information
    hardware_request = TextLengthField('Hardware Request', null=True, blank=True, max_length=2000)
    compute_note = TextLengthField('Additional Information', null=True, blank=True, max_length=2000)

    class Meta:
        ordering = ['-id']

    def __unicode__(self):
        return "Project Application #%s" % self.id

    @models.permalink
    def get_absolute_url(self):
        return ('view_project_application', [self.secret_token])


class ProjectApplicationMember(models.Model):
    TITLES = (
        ('Mr', 'Mr'),
        ('Mrs', 'Mrs'),
        ('Miss', 'Miss'),
        ('Ms', 'Ms'),
        ('Dr', 'Dr'),
        ('A/Prof', 'A/Prof'),
        ('Prof', 'Prof'),
    )
    LEVELS = (
        ('E', 'Professor or equivalent'),
        ('D', 'Associate Professor or equivalent'),
        ('C', 'Senior Lecturer or equivalent'),
        ('B', 'Lecturer or equivalent'),
        ('A', 'Research Assistant or equivalent'),
        ('S', 'Student or equivalent'),
    )
    ROLES = (
        ('CI', 'Chief Investigator'),
        ('I', 'Investigator'),
        ('S', 'Student'),
    )
    email = models.EmailField(null=True, blank=True)
    title = models.CharField(choices=TITLES, max_length=100, null=True, blank=True)
    first_name = models.CharField(max_length=30, null=True, blank=True)
    last_name = models.CharField(max_length=30, null=True, blank=True)
    institute = models.CharField(max_length=200, null=True, blank=True)
    faculty = models.CharField(max_length=200, null=True, blank=True)
    department = models.CharField(max_length=200, null=True, blank=True)
    telephone = models.CharField("Office Telephone", max_length=200, null=True, blank=True)
    is_applicant = models.BooleanField(default=False, editable=False)
    is_supervisor = models.BooleanField(default=False)
    is_leader = models.BooleanField(default=False)
    level = models.CharField(choices=LEVELS, max_length=1, null=True, blank=True)
    role = models.CharField(choices=ROLES, max_length=2, null=True, blank=True)
    disp_order = models.PositiveIntegerField(null=True, blank=True)

    project_application = models.ForeignKey(ProjectApplication)

    class Meta:
        unique_together = (('email', 'project_application'),)
        ordering = ['disp_order']

    def __unicode__(self):
        if self.first_name and self.last_name:
            return self.get_full_name()
        if self.email:
            return self.email
        return self.pk

    def get_full_name(self):
        return "%s %s" % (self.first_name, self.last_name)


'''
Want to report usage by Institute, Faculty and School
Unfortunately Karaage doesn't have these, so adding here as a short cut
'''
class ProjectApplicationFaculty(models.Model):
    faculty = models.CharField(max_length=100, null=True, blank=True)
    school = models.CharField(max_length=100, null=True, blank=True)
    institute = models.ForeignKey(Institute, null=True, blank=True)

    class Meta:
        unique_together = (('institute', 'faculty', 'school',),)
