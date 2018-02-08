import csv, datetime, six
import json

from django.shortcuts import get_object_or_404, render
from django.template import RequestContext
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.contrib.auth.decorators import permission_required, login_required
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Q
from django import forms
from django.forms.models import inlineformset_factory, modelformset_factory
import django_tables2 as tables

from karaage.common import is_admin, log, add_comment
from karaage.common.decorators import admin_required
from karaage.projects.models import Project, ProjectQuota
from karaage.institutes.models import Institute
from karaage.machines.models import MachineCategory


from .forms import StartProjectApplicationForm, ProjectApplicationPartBForm, ProjectApplicationPartCForm
from .forms import ProjectApplicationMemberForm, ProjectApplicationMemberFormSet
from .forms import ProjectApplicationTacForm, ProjectApplicationFacultyForm, ProjectApplicationApproveForm
from .models import ProjectApplication, ProjectApplicationMember
from .models import ProjectApplicationFaculty
from .reports import project_application_to_pdf, project_application_to_pdf_doc
from .emails import send_start_email
from .emails import send_submit_receipt, send_notify_admin

from .tables import ProjectApplicationFilter, ProjectApplicationTable

import logging
logger = logging.getLogger('django')

try:
    custom_footer = settings.CUSTOM_FOOTER
except AttributeError:
    custom_footer = ''


def project_application_list(request, queryset=None):

    if not is_admin(request):
            return HttpResponseRedirect(reverse('linkto_project_application'), {'custom_footer': custom_footer})

    if queryset == None:
        queryset = ProjectApplication.objects.all()

    q_filter = ProjectApplicationFilter(request.GET, queryset=queryset)

    # Want to show application ID but link to use secret token
    # so have to remap to 'application_id' here and in tables.py
    app_ids = ProjectApplication.objects.values('id', 'secret_token').order_by()
    token_ids = { item['id'] : item['secret_token'] for item in app_ids }

    proj_ids = Project.objects.values('pid', 'id').order_by()
    proj_to_id = { item['pid'] : item['id'] for item in proj_ids }

    results = list(q_filter.qs.all())    # get a copy
    for item in results:
        if item.id in token_ids:
            # monkey patch 'application_id'
            item.application_id = token_ids[item.id]
        if item.project:
            item.project_id = item.project.id
            item.pid = item.project.pid
        try:
            item.supervisor = ProjectApplicationMember.objects.get(project_application=item.id, is_supervisor=True).__unicode__()
        except ProjectApplicationMemebers.DoesNotExist:
            pass

    table = ProjectApplicationTable(results)
    tables.RequestConfig(request).configure(table)

    spec = []
    for name, value in six.iteritems(q_filter.form.cleaned_data):
        if value is not None and value != "":
            name = name.replace('_', ' ').capitalize()
            spec.append((name, value))

    return render(
        request,
        'project_application/admin_project_application_list.html',
        {
            'table': table,
            'filter': q_filter,
            'spec': spec,
            'title': "Project Application list",
            'custom_footer': custom_footer,
        },
        )


def project_application_info(request):
    return render(request, 'project_application/project_application_info.html',
                    {
                        'help_email': settings.ACCOUNTS_EMAIL,
                        'custom_footer': custom_footer,
                    },
        )


def full_project_application(request):

    try:
        days_valid = settings.PROJECT_LINK_DAYS_VALID 
    except AttributeError:
        days_valid = 30

    today = datetime.date.today()
    expiry = today + datetime.timedelta(days_valid)
    expiry = datetime.datetime.combine(expiry, datetime.time(23,59,59))

    if request.method == 'POST':
        form = StartProjectApplicationForm(request.POST)
        if form.is_valid():
            created_by = form.clean_email()
            # always create new application, even if they have one open
            project_application = ProjectApplication(created_by=created_by, expires=expiry)
            project_application.save()

            member, c = ProjectApplicationMember.objects.get_or_create(project_application=project_application, email=created_by)
            member.is_applicant=True
            member.is_supervisor=True
            member.is_leader=True
            member.save()
#            link = '%s/apply/%s/' % (
#                       settings.REGISTRATION_BASE_URL,
#                       project_application.secret_token)
##TODO make this more portable
#            link = 'https://%s%s%s/' % (
            link = 'http://%s%s%s/' % (
                       settings.HTTP_HOST,
                       reverse('linkto_project_application'),
                       project_application.secret_token)
            send_start_email(project_application, link)
            return render(request, 'project_application/start_project_application_sent.html',
                    {'email': created_by, 'help_email': settings.ACCOUNTS_EMAIL, 'expiry':expiry},
                    )
    else:
        form = StartProjectApplicationForm()

    return render(request, 'project_application/start_project_application_form.html', {'form': form, 'help_email': settings.ACCOUNTS_EMAIL, 'expiry':expiry},)


def project_application_pdf(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )
    return project_application_to_pdf(project_application)


def submit_project_application(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.NEW, ProjectApplication.OPEN,
                                            ProjectApplication.WAITING_FOR_ADMIN],
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )

        if project_application.state == ProjectApplication.WAITING_FOR_ADMIN:
            return HttpResponseRedirect(reverse('view_project_application', args=[project_application.secret_token]))

        if project_application.state != ProjectApplication.OPEN:
            project_application.state = ProjectApplication.OPEN
            project_application.save()

    # completeness tests
    def partaOK(project_application):
#        ppl = project_application.project_application_project_application_member_set.select_related()
        ppl = ProjectApplicationMember.objects.filter(project_application=project_application)
        has_all = True
        has_supervisor = False
        has_leader = False
        for prs in ppl:
            if not (prs.email and prs.title and
                    prs.first_name and prs.last_name and
                    prs.institute and prs.faculty and prs.department and
                    prs.telephone and
                    prs.level and prs.role
                    ):
                has_all = False
            has_supervisor |= prs.is_supervisor
            has_leader |= prs.is_leader
        return (has_all and has_supervisor and has_leader)

    def partbOK(project_application):
        if not (project_application.title and project_application.summary and
                project_application.FOR):
                return False
        return True

    def partcOK(project_application):
        return True

    complete = {
            'a': partaOK(project_application),
            'b': partbOK(project_application),
            'c': partcOK(project_application),
            }

    complete_all = complete['a'] and complete['b'] and complete['c']

    if request.method == 'POST':
        form = ProjectApplicationTacForm(request.POST, instance=project_application, prefix='tac')

        if form.is_valid():
            form.save()
            if complete_all and project_application.tac:
                # if user or admin, change state
                if 'action' in request.POST or 'adminsubmit' in request.POST:
                    project_application.state = ProjectApplication.WAITING_FOR_ADMIN
                    project_application.submitted_date = datetime.datetime.now()
                    project_application.save()
                    messages.info(request, 'Application marked as submitted')
                elif 'adminunsubmit' in request.POST:
                    project_application.state = ProjectApplication.OPEN
                    project_application.save()
                    messages.info(request, 'Application has been unsubmitted (marked as open)')
                # notifications only if submitted by user
                if 'action' in request.POST:
                    pdf = project_application_to_pdf_doc(project_application)
                    send_submit_receipt(project_application, pdf)
                    #TODO: WRONG need to derive url, not hardcode!
                    link = '%s/apply/%s/' % (
                       settings.REGISTRATION_BASE_URL,
                       project_application.secret_token)
                    send_notify_admin(project_application, link)
                    #NOTE: could go to waiting for review?
                    project_application.state = ProjectApplication.WAITING_FOR_ADMIN
                    project_application.save()
                    return HttpResponseRedirect(reverse('project_application_done', args=[project_application.secret_token]))
    else:
        form = ProjectApplicationTacForm(instance=project_application, prefix='tac')

    return render(request, 'project_application/submit_project_application_form.html', 
                              {'help_email': settings.ACCOUNTS_EMAIL,
                               'project_application': project_application,
                               'form': form,
                               'complete': complete,
                               'complete_all': complete_all,
                              }, 
                              )


def project_application_view(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.WAITING_FOR_ADMIN],
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )

    members = ProjectApplicationMember.objects.filter(project_application=project_application)
    supervisor = members.get(is_supervisor=True)

    return render(request, 'project_application/project_application_view.html', {'project_application': project_application,
            'members': members, 'supervisor':supervisor,},
        )


def project_application_done(request, token):
    try:
        project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.WAITING_FOR_ADMIN],
                                    expires__gte=datetime.datetime.now())
    except ProjectApplication.DoesNotExist:
        return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )

    email = project_application.created_by

    return render(request, 'project_application/project_application_done.html', {'project_application': project_application, 'email': email, 'help_email': settings.ACCOUNTS_EMAIL, },)


def project_application_parta(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.NEW, ProjectApplication.OPEN],
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )


    queryset = ProjectApplicationMember.objects.filter(project_application=project_application)

    # use Selects for Institute, Faculty, Department
    # collect all known inst/fac/sch and any saved in application

    inst_choice = sorted(set([('','Type here or select from list')] +
        list(Institute.objects.values_list('name', 'name')) +
        list(queryset.exclude(institute__isnull=True).values_list('institute', 'institute'))))

    fac_choice = sorted(set([('','Type here or select from list')] +
        list(ProjectApplicationFaculty.objects.exclude(faculty__isnull=True).values_list('faculty', 'faculty')) +
        list(queryset.exclude(faculty__isnull=True).values_list('faculty', 'faculty'))))

    sch_choice = sorted(set([('','Type here or select from list')] +
        list(ProjectApplicationFaculty.objects.exclude(school__isnull=True).values_list('school', 'school')) +
        list(queryset.exclude(department__isnull=True).values_list('department', 'department'))))

    MemberInLineFormSet = inlineformset_factory(ProjectApplication, ProjectApplicationMember,
            formset=ProjectApplicationMemberFormSet, form=ProjectApplicationMemberForm,
            widgets={'institute':forms.Select(choices=inst_choice),
                    'faculty':forms.Select(choices=fac_choice),
                    'department':forms.Select(choices=sch_choice),
                    },
            can_order=True)

    # pass list to javascript
    inst_fac_sch = ProjectApplicationFaculty.objects.exclude(institute__isnull=True)
    all_choices = {}
    for item in inst_fac_sch:
        all_choices.setdefault(item.institute.name,
                        {}).setdefault(item.faculty or '', []).append(item.school or '')
    # Add data entered from members
    for memb in queryset:
        inst = memb.institute or '';
        fac = memb.faculty or '';
        sch = memb.department or '';
        if ((inst not in all_choices) or (fac not in all_choices[inst]) or
                (sch not in all_choices[inst][fac])):
            all_choices.setdefault(inst,
                        {}).setdefault(fac, []).append(sch)
    all_choices = json.dumps(all_choices)

    if request.method == 'POST':
        # is_supervisor are shown as one radio select group
        # need to convert back to checkbox POST format
        # Process: POST data needs renaming so member forset can
        # validate/clean/save.  Form clean enforces change of state
        # Form validation prevents deleting selected item, so one must always
        # be selected (test for this?)
        post = request.POST.copy()
        if 'is_supervisor' in post.keys():
            selected = post['is_supervisor']
            post[selected + '-is_supervisor'] = u'on'

        member_formset = MemberInLineFormSet(post, instance=project_application,
            queryset=queryset)

        if member_formset.is_valid():
            member_formset.save()

            # catch case where no one selected
            if not queryset.filter(is_supervisor=True).exists():
                queryset.filter(email__iexact=project_application.created_by).update(is_supervisor = True)

            messages.info(request, 'Personnel: Saved')
            if 'menu' in request.POST:
                return HttpResponseRedirect(reverse('project_application_submit', args=[project_application.secret_token]))
            if 'parta' in request.POST:
                return HttpResponseRedirect(reverse('project_application_parta', args=[project_application.secret_token]))
            if 'partb' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partb', args=[project_application.secret_token]))
            if 'partc' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partc', args=[project_application.secret_token]))
    else:
        member_formset = MemberInLineFormSet(instance=project_application,
            queryset=queryset)


    return render(request, 'project_application/project_application_parta_form.html',
        {'project_application': project_application, 'member_formset': member_formset,
                'all_choices':all_choices,
                'help_email': settings.ACCOUNTS_EMAIL,},
        )


def project_application_partb(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.NEW, ProjectApplication.OPEN],
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )

    if request.method == 'POST':
        form = ProjectApplicationPartBForm(request.POST, instance=project_application, request=request)
        if form.is_valid():
            project_application = form.save()

            messages.info(request, 'Project Overview: Saved')
            if 'menu' in request.POST:
                return HttpResponseRedirect(reverse('project_application_submit', args=[project_application.secret_token]))
            if 'parta' in request.POST:
                return HttpResponseRedirect(reverse('project_application_parta', args=[project_application.secret_token]))
            if 'partb' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partb', args=[project_application.secret_token]))
            if 'lookup' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partb', args=[project_application.secret_token]))
            if 'partc' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partc', args=[project_application.secret_token]))
    else:
        form = ProjectApplicationPartBForm(instance=project_application, request=request)

    return render(request, 'project_application/project_application_partb_form.html', 
                              {'form': form, 'project_application': project_application, 'help_email': settings.ACCOUNTS_EMAIL}, 
                              )


def project_application_partc(request, token):
    if is_admin(request):
        try:
            project_application = get_object_or_404(ProjectApplication, id=token)
        except ValueError:
            project_application = get_object_or_404(ProjectApplication, secret_token=token)
    else:
        try:
            project_application = ProjectApplication.objects.get(
                                    secret_token=token, 
                                    state__in=[ProjectApplication.NEW, ProjectApplication.OPEN],
                                    expires__gte=datetime.datetime.now())
        except ProjectApplication.DoesNotExist:
            return render(request, 'project_application/old_userapplication.html',
                                    {'help_email': settings.ACCOUNTS_EMAIL,},
                                    )

    if request.method == 'POST':
        form = ProjectApplicationPartCForm(request.POST, instance=project_application)

        if form.is_valid():
            project_application = form.save()
            messages.info(request, 'Resources: Saved')
            if 'menu' in request.POST:
                return HttpResponseRedirect(reverse('project_application_submit', args=[project_application.secret_token]))
            if 'parta' in request.POST:
                return HttpResponseRedirect(reverse('project_application_parta', args=[project_application.secret_token]))
            if 'partb' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partb', args=[project_application.secret_token]))
            if 'partc' in request.POST:
                return HttpResponseRedirect(reverse('project_application_partc', args=[project_application.secret_token]))
    else:
        form = ProjectApplicationPartCForm(instance=project_application)

    return render(request, 'project_application/project_application_partc_form.html',
                    {'form': form, 'project_application': project_application,},
                )


@admin_required
def project_application_faculty(request):
    FacultyFormSet = modelformset_factory(ProjectApplicationFaculty, can_delete=True,
                                    form=ProjectApplicationFacultyForm, extra=1)

    inst_fac_sch = ProjectApplicationFaculty.objects.exclude(institute__isnull=True)
    all_choices = {}
    for item in inst_fac_sch:
        all_choices.setdefault(item.institute.id or '',
                        {}).setdefault(item.faculty or '', []).append(item.school or '')
    all_choices = json.dumps(all_choices)

    if request.method == 'POST':
        formset = FacultyFormSet(request.POST, prefix='faculty')

        if formset.is_valid():
            formset.save()
            messages.info(request, 'Institute, Faculty, School: Saved')
            return HttpResponseRedirect(reverse('project_application_faculty',))
    else:
        formset = FacultyFormSet(prefix='faculty')

    return render(request, 'project_application/faculty_school_form.html',
                {'formset': formset, 'all_choices': all_choices},
                )


@admin_required
def project_application_approve(request, token):
    """
    Must manually set fairshare, disk and e-mail user.
    """
    project_application = get_object_or_404(ProjectApplication, secret_token=token)

    if project_application.state in [ProjectApplication.COMPLETE, ProjectApplication.ARCHIVED]:
        messages.error(request, "This application has already been approved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    if project_application.state == ProjectApplication.DECLINED:
        messages.error(request, "This application was delined")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    if project_application.state != ProjectApplication.WAITING_FOR_ADMIN:
        messages.error(request, "Only submitted applications can be approved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # by default lookup requested associated project, unless admin looks up
    # different project
    associated = None
    if request.method == 'POST':
        post = request.POST.copy()
        if 'proj_try' in post.keys():
            associated = post['proj_try']

    initial = {'proj_try': '', 'proj_title': project_application.title,
                    'proj_desc': project_application.summary, 'host': '',
                    'faculty': None, 'school': None}
    try:
        proj_try = Project.objects.get(pid=associated)
        initial['proj_try'] = proj_try.pid
    except Project.DoesNotExist:
        proj_try = None

    proj_ids = Project.objects.values_list('pid', flat=True)

    queryset = ProjectApplicationMember.objects.filter(project_application=project_application)
    # should only be one of supervisor and applicant
    supervisor = queryset.get(is_supervisor=True)
    applicant = queryset.get(is_applicant=True)
    # any other leaders
    leaders = queryset.filter(project_application=project_application, is_leader=True,
                    is_supervisor=False, is_applicant=False)
    members = [supervisor]
    if applicant != supervisor:
        members.append(applicant)
    for leader in leaders:
        members.append(leader)

    # Institute must exist before Approval
    try:
        host = Institute.objects.get(name__exact=supervisor.institute)
        initial['host'] = host
    except Institute.DoesNotExist:
        messages.error(request, "Fix/Create the host institute before Approving")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    # pass list to javascript
    inst_fac_sch = ProjectApplicationFaculty.objects.all()
    all_choices = {}
    for item in inst_fac_sch:
        all_choices.setdefault(item.institute.id,
                        {}).setdefault(item.faculty, []).append(item.school)

    # Add data entered for supervisor
    inst = Institute.objects.get(name__iexact=supervisor.institute).id
    fac = supervisor.faculty
    sch = supervisor.department
    initial['faculty'] = fac
    initial['school'] = sch
    if ((inst not in all_choices) or (fac not in all_choices[inst]) or
            (sch not in all_choices[inst][fac])):
        all_choices.setdefault(inst,
                    {}).setdefault(fac, []).append(sch)

    all_choices = json.dumps(all_choices)

    if request.method == 'POST':
        form = ProjectApplicationApproveForm(request.POST, initial=initial)
        if form.is_valid() and 'approve' in request:
            data = form.cleaned_data
            
            new_text = u'\nProject Application approved on: %s\n' % datetime.date.today().strftime('%d, %b %Y')
            new_text += u'Approved by %s' % request.user
            new_text += u'Application number: %s (%s)\n' % (
                            project_application.id,
                            request.build_absolute_uri(
                                    reverse('view_project_application', args=[project_application.id])))
            new_text += u'Supervisor: %s\n' % supervisor.get_full_name()
            new_text += u'Host: %s, %s, %s\n' % (data['host'].name,
                            data['faculty'], data['school'])

            proj_try_data = data['proj_try'].upper()
            try:
                project = Project.objects.get(pid=proj_try_data)
                created = False
                ## TODO: need to check institute hasn't changed
                ## Warn, confirm change of host!!!
                prev_leaders = ', '.join([leader.get_full_name() for leader in project.leaders.all()])
                new_text += u'Previous Title: %s\n' % project.name
                new_text += u'Previous Leaders: %s\n' % prev_leaders
                new_text += u'Previous Host: %s\n' % project.institute
                new_text += u'Previous Description: %s\n\n' % project.description
            except (Project.DoesNotExist, Project.IntegrityError):
                project = Project(pid=proj_try_data, institute=data['host'])
                project.save()
                # add approving admin as leader of new project
                project.leaders.add(request.user)
                created = True

            project.additional_req = '%s%s' % (new_text, (project.additional_req or ''))
            project.name = data['proj_title']
            project.description = data['proj_desc']
            project.institute = data['host']
            project.save()
            ProjectQuota.objects.get_or_create(project=project,
                        machine_category=MachineCategory.objects.get_default())
            project.activate(request.user)
            project.save()
            project_application.project = project
            project_application.host_institute = data['host'].name ## save name for archiving
            project_application.host_faculty = data['faculty']
            project_application.host_school = data['school']
            project_application.state = ProjectApplication.COMPLETE
            project_application.save()
            # save faculty and school in case they are new
            ProjectApplicationFaculty.objects.get_or_create(institute=data['host'],
                            faculty=data['faculty'], school=data['school'])
            log.add(project_application, 'Approved by %s' % request.user)
            messages.info(request, "%s approved" % project_application)
            return HttpResponseRedirect(reverse('project_application_list'))
    else:
        form = ProjectApplicationApproveForm(initial=initial)

    return render(request, 'project_application/admin_confirm_approve.html', {'project_application': project_application,
            'proj_try':proj_try, 'host':host, 'faculty': fac, 'school': sch,
            'all_choices':all_choices,
            'members':members, 'proj_ids':proj_ids,
            'form': form}, )


@admin_required
def project_application_add_comment(request, token):
    obj = get_object_or_404(ProjectApplication, secret_token=token)
    breadcrumbs = [
        ("RAS", reverse("project_application_list")),
        (six.text_type(obj.id), reverse("view_project_application", args=[obj.secret_token]))
    ]
    return add_comment(request, breadcrumbs, obj)


@admin_required
def project_application_decline(request, token):
    """
    Current model is to manually notify applicant.
    Decline will archive user and project_application application.
    """
    project_application = get_object_or_404(ProjectApplication, secret_token=token)

    if project_application.state in [ProjectApplication.COMPLETE, ProjectApplication.ARCHIVED]:
        messages.error(request, "This application has already been approved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    if project_application.state == ProjectApplication.DECLINED:
        messages.error(request, "This application was delined")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    if project_application.state != ProjectApplication.WAITING_FOR_ADMIN:
        messages.error(request, "Only submitted applications can be declined")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    members = ProjectApplicationMember.objects.filter(project_application=project_application)
    supervisor = members.get(is_supervisor=True)

    if request.method == 'POST':
        project_application.state = ProjectApplication.DECLINED
        project_application.save()
        log.change(project_application, 'Declined by %s' % request.user)
        messages.info(request, "%s declined successfully." % project_application)
        return HttpResponseRedirect(reverse('project_application_list'))

    return render(request, 'project_application/admin_confirm_decline.html',
                    {'project_application': project_application,
                     'members': members, 'supervisor': supervisor},
                    )


@admin_required
def project_application_delete(request, token):
    project_application = get_object_or_404(ProjectApplication, secret_token=token)

    if project_application.state in [ProjectApplication.COMPLETE, ProjectApplication.ARCHIVED]:
        messages.error(request, "This application has already been approved")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
    if project_application.state == ProjectApplication.DECLINED:
        messages.error(request, "This application was delined")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    members = ProjectApplicationMember.objects.filter(project_application=project_application)
    supervisor = members.get(is_supervisor=True)

    if request.method == 'POST':
        project_application_id = project_application.id
        project_application.delete()
        log.delete(request.user, 'Deleted Resource Application %s' % project_application_id)
        messages.info(request, "%s deleted." % project_application)
        return HttpResponseRedirect(reverse('project_application_list'))

    return render(request, 'project_application/admin_confirm_delete.html',
                    {'project_application': project_application,
                     'members': members, 'supervisor': supervisor},
                    )

