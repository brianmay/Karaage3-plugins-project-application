from django import forms
from django.conf import settings
from django.contrib import messages

from captcha.fields import CaptchaField

import datetime

from django.core.exceptions import NON_FIELD_ERRORS

from karaage.projects.models import Project
from karaage.institutes.models import Institute

from .models import ProjectApplication, ProjectApplicationMember, ProjectApplicationFaculty

class ProjectApplicationForm(forms.ModelForm):
    class Meta:
        model = ProjectApplication
        fields = ['tac', 'title', 'summary', 'purpose', 'compute_note', 'hardware_request', 'FOR']

    def __init__(self, *args, **kwargs):
        super(ProjectApplicationForm, self).__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].widget.attrs['class'] = 'form-control'


class StartProjectApplicationForm(ProjectApplicationForm):
    email = forms.EmailField(help_text='Please enter your institutional e-mail address')
    captcha = CaptchaField(label=u'CAPTCHA', help_text=u"Please enter the text displayed in the image above. Case insensitive.")

    class Meta(ProjectApplicationForm.Meta):
        fields = ('email',)

    def clean_email(self):
        data = self.cleaned_data
        email = data['email'].lower().strip()
        domain = email.split('@')[1]
        domain_parts = set(domain.split('.'))
        ## XXX List of excluded domains.  Could use better regex method
        bad_domains = set(['gmail', 'yahoo', 'hotmail', 'live', 'icloud'])
        if set(domain_parts) & bad_domains:
            raise forms.ValidationError("You must use your institutional e-mail address")
        return email


class ProjectApplicationTacForm(ProjectApplicationForm):
    class Meta(ProjectApplicationForm.Meta):
        fields = ('tac',)


class ProjectApplicationPartBForm(ProjectApplicationForm):

    class Meta(ProjectApplicationForm.Meta):
        fields = ['title', 'FOR', 'summary', 'purpose',]

    def __init__(self, *args, **kwargs):
        # need to base clean on REQUEST
        self.request = kwargs.pop('request', None)

        super(ProjectApplicationPartBForm, self).__init__(*args, **kwargs)
        self.fields['title'].widget.attrs['class'] += ' show-required'
        self.fields['FOR'].widget.attrs['class'] += ' show-required'
        self.fields['summary'].widget.attrs['class'] += ' show-required'


class ProjectApplicationPartCForm(ProjectApplicationForm):

    class Meta(ProjectApplicationForm.Meta):
        fields = ['compute_note', 'hardware_request',]


class ProjectApplicationMemberForm(forms.ModelForm):

    class Meta:
        model = ProjectApplicationMember
        fields = ['email', 'title', 'first_name', 'last_name',
                        'institute', 'faculty',  'department',
                        'telephone',
                        'role', 'level',
                        'is_supervisor', 'is_leader',
                        'disp_order']
        readonly_fields = ['is_applicant']
        error_messages = {
            NON_FIELD_ERRORS: {
                'unique_together': "Each e-mail must be unique (and can't be swapped)",
            }
        } 


    def __init__(self, *args, **kwargs):
        super(ProjectApplicationMemberForm, self).__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].widget.attrs['class'] = 'form-control'
        if kwargs.get('instance'):
            if self.fields.get('email'):
                self.fields['email'].widget.attrs['class'] += ' show-required'
            if self.fields.get('title'):
                self.fields['title'].widget.attrs['class'] += ' show-required'
            if self.fields.get('first_name'):
                self.fields['first_name'].widget.attrs['class'] += ' show-required'
            if self.fields.get('last_name'):
                self.fields['last_name'].widget.attrs['class'] += ' show-required'
            if self.fields.get('institute'):
                self.fields['institute'].widget.attrs['class'] += ' show-required'
            if self.fields.get('faculty'):
                self.fields['faculty'].widget.attrs['class'] += ' show-required'
            if self.fields.get('department'):
                self.fields['department'].widget.attrs['class'] += ' show-required'
            if self.fields.get('telephone'):
                self.fields['telephone'].widget.attrs['class'] += ' show-required'
            if self.fields.get('role'):
                self.fields['role'].widget.attrs['class'] += ' show-required'
            if self.fields.get('level'):
                self.fields['level'].widget.attrs['class'] += ' show-required'


    def unique_error_message(self, model_class, unique_check):
        if model_class == type(self) and unique_check == ('email', 'project_application'):
            return "Each e-mail must be unique (and can't be swapped)"
        else:
            return super(ProjectApplicationMemberForm, self).unique_error_message(model_class, unique_check)

    def clean(self):
        data = self.cleaned_data
        if data['level'] == 'S' and (data['is_supervisor'] == True or data['is_leader'] == True):
            msg = "Students can not be the Project Supervisor or Manager."
            self._errors[forms.forms.NON_FIELD_ERRORS] = self.error_class([msg])

        # Supervisor must have institute e-mail
        email = data['email'].lower().strip()
        if data['is_supervisor'] == True:
            domain = email.split('@')[1]
            domain_parts = set(domain.split('.'))
            ## XXX List of excluded domains
            bad_domains = set(['gmail', 'yahoo', 'hotmail', 'live', 'icloud'])
            if set(domain_parts) & bad_domains:
                msg = "The Project Supervisor's institutional e-mail must be provided."
                self._errors['email'] = self.error_class([msg])

        return super(ProjectApplicationMemberForm, self).clean()


class ProjectApplicationMemberFormSet(forms.models.BaseInlineFormSet):
    '''
        Users tend to try to rearrange items by changing e-mails
        Need to test for all sorts of cases and let them know what is wrong
    '''
    def clean(self):
        if any(self.errors):
            # Don't bother validating the formset unless each form is valid on its own
            return
        num_forms = self.total_form_count()

        # don't delete is_supervisor
        for i in range(num_forms):
            form = self.forms[i]
            data = form.cleaned_data
            # if all entries blank, delete
            no_data = True
            for key in data.keys():
                if key in ['id', 'is_supervisor', 'is_leader', 'DELETE', 'project_application', 'ORDER', 'display_order',]:
                    continue
                if data[key] == None or data[key] == "" or data[key] == False:
                    continue
                no_data = False

            if no_data:
                if data.get('is_supervisor') or data.get('is_leader'):
                    msg = "Please enter details for the Project Supervisor and Manager."
                    form._errors[forms.forms.NON_FIELD_ERRORS] = self.error_class([msg])
                else:
                    data['DELETE'] = True

            if data.get('is_supervisor'):
                if data.get('DELETE'):
                    msg = "Can't delete Project Supervisor, please make someone else is the Project Supervisor."
                    form._errors[forms.forms.NON_FIELD_ERRORS] = self.error_class([msg])
                    del data['DELETE']
#                    raise forms.ValidationError('')


        in_emails = []
        out_emails = []
        # collect all emails, before and after POST
        for i in range(num_forms):
            form = self.forms[i]
            init = form.initial
            data = form.cleaned_data
            # mark fields that will be deleted as None
            if data.get('DELETE'):
                in_emails.append(None)
                out_emails.append(None)
                continue
            in_email = None
            if init.get('email'):
                in_email = form.initial['email'].lower()
            out_email = None
            if data.get('email'):
                out_email = form.cleaned_data['email'].lower()
                # while where here, also add missing order if none given
                order = form.cleaned_data['disp_order']
                if order == None or order == "":
                    form.instance.disp_order = i
            in_emails.append(in_email)
            out_emails.append(out_email)

        return super(ProjectApplicationMemberFormSet, self).clean()


class ProjectApplicationFacultyForm(forms.ModelForm):
    class Meta:
        model = ProjectApplicationFaculty
        fields = ['institute', 'faculty', 'school',]

    def __init__(self, *args, **kwargs):
        super(ProjectApplicationFacultyForm, self).__init__(*args, **kwargs)
        self.fields['institute'] = forms.ModelChoiceField(queryset=Institute.objects.all(), empty_label="Select Institute", required=True)
        # need tuple set to get distinct values and add to empty message
        fac_choice = (('','Select/Add Faculty'),) + \
                      tuple(set(ProjectApplicationFaculty.objects.values_list('faculty', 'faculty')))
        self.fields['faculty'] = forms.CharField(required=False,
                        widget=forms.Select(choices=fac_choice))
        sch_choice = (('','Select/Add School'),) + \
                      tuple(set(ProjectApplicationFaculty.objects.values_list('school', 'school')))
        self.fields['school'] = forms.CharField(required=False,
                        widget=forms.Select(choices=sch_choice))


class ProjectApplicationApproveForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super(ProjectApplicationApproveForm, self).__init__(*args, **kwargs)
        """
        Use local fields that can be used to create or pre-populate data
        View will take care of create/edit
        """
        faculty = []
        department = []
        if 'initial' in kwargs:
            initial = kwargs['initial']
            if 'faculty' in initial:
                faculty = [(initial['faculty'], initial['faculty']),]
            if 'school' in initial:
                school = [(initial['school'], initial['school']),]

        # list all previous projects and allow adding a new one
        proj_choice = (('','Select/Add Project'),) + \
                      tuple((inst.pid, inst.pid + " - " + inst.name) for inst in Project.objects.all())
        self.fields['proj_try'] = forms.CharField(required=True,
                        widget=forms.Select(choices=proj_choice, attrs={
                                'class':'form-control',}))
        self.fields['proj_title'] = forms.CharField(max_length=200, required=True,
                widget=forms.TextInput(
                attrs={'placeholder': 'Please enter the requested title',
                        'class':'form-control show-required'}))
        self.fields['proj_desc'] = forms.CharField(required=True,
                widget=forms.Textarea(
                attrs={'placeholder': 'Please enter the requested summary', 
                        'class':'form-control show-required'}))
        self.fields['host'] = forms.ModelChoiceField(required=True, empty_label='Select Host Institute',
                queryset=Institute.objects.all())
        # nees tuple set to get distinct values and add to empty message
        fac_choice = sorted(set([('','Select/Add Faculty')] +
            list(ProjectApplicationFaculty.objects.values_list('faculty', 'faculty')) +
            faculty
            ))
        sch_choice = sorted(set([('','Select/Add Department')] +
            list(ProjectApplicationFaculty.objects.values_list('school', 'school')) +
            school
            ))
        self.fields['faculty'] = forms.CharField(required=False,
                        widget=forms.Select(choices=fac_choice))
        self.fields['school'] = forms.CharField(required=False,
                        widget=forms.Select(choices=sch_choice))
