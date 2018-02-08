from django.template.loader import render_to_string
from django.conf import settings

from django.core.mail import EmailMessage
from django.conf import settings

CONTEXT = {
    'org_email': settings.APPROVE_ACCOUNTS_EMAIL,
    'org_name': settings.ACCOUNTS_ORG_NAME,
}

HEADERS = {
    'Precedence': 'bulk',
    'Auto-Submitted': 'auto-replied',
}


def render_email(name, context):
    context.update(CONTEXT)
    subject = render_to_string(
        ['project_application/emails/%s_subject.txt' % name], # can search multiple locations
        context).replace('\n', '')
    body = render_to_string(
        ['project_application/emails/%s_body.txt' % name],
        context)
    return subject, body


def send_start_email(project_application, link):
    """ Sends an email to the applicant with a link to the application"""

    if not project_application.created_by:
        # should raise an error/alert admins?
        return

    context = CONTEXT.copy()
    context['link'] = link
    context['project_application'] = project_application

    to_email = project_application.created_by
    subject, body = render_email('start', context)

    email = EmailMessage(
                subject,
                body,
                settings.APPROVE_ACCOUNTS_EMAIL,
                [to_email],
                headers=HEADERS)
    return email.send(fail_silently=False)


def send_submit_receipt(project_application, pdf):
    context = CONTEXT.copy()

    context['project_application'] = project_application
    context['help'] = settings.ACCOUNTS_EMAIL

    #TODO send to all named members?
    to_email = project_application.created_by
    context['email'] = to_email

    subject, body = render_email('submit_receipt', context)
    
    email = EmailMessage(
                subject,
                body,
                settings.APPROVE_ACCOUNTS_EMAIL,
                [to_email],
                attachments=[
                        ('%s-Project-Application-%s.pdf'%(
                                settings.ACCOUNTS_ORG_NAME, project_application.id),
                                pdf, 'application/pdf')],
                headers=HEADERS)
    return email.send(fail_silently=False)


def send_notify_admin(project_application, link):
    context = CONTEXT.copy()

    context['project_application'] = project_application
    context['link'] = link

    to_email = settings.APPROVE_ACCOUNTS_EMAIL
    subject, body = render_email('notify_admin', context)
    
    email = EmailMessage(
                subject,
                body,
                settings.APPROVE_ACCOUNTS_EMAIL,
                [to_email],
                headers=HEADERS)
    return email.send(fail_silently=False)
