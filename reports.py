from django.http import HttpResponse
from django.template import defaultfilters
from django.conf import settings

import datetime
from io import BytesIO

# this isn't in container so need to install
try:
    from reportlab.platypus import Table
except ImportError:
    import pip
    pip.main(['install', 'reportlab'])

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus.flowables import PageBreak

from .models import ProjectApplicationMember, ProjectApplication

from xml.sax.saxutils import escape

import logging                                                                                                                                                               
logger = logging.getLogger('django')

PAGE_WIDTH = portrait(A4)[0]

def safe_or_none(var):
    if var:
        try:
            return escape(var)
        except AttributeError:
            return var
    else:
        return None


def project_application_to_pdf_doc(project_application):

    now = datetime.datetime.now()

    def footer(canvas, doc):
        canvas.setFont('Times-Roman', 9)
        canvas.drawCentredString(PAGE_WIDTH/2, 30, "%s" % (settings.ACCOUNTS_ORG_NAME))
        canvas.drawString(540, 30, "Page %d" % doc.page)
        canvas.drawString(50, 30, defaultfilters.date(now, "g:i a j, F Y"))

    def myFirstPage(canvas, doc):
        # Header
        canvas.saveState()
        canvas.setTitle("%s Project Application, number %s" % (settings.ACCOUNTS_ORG_NAME, project_application.id))

        canvas.setFont("Helvetica", 20)
        canvas.drawString(50, 800, '%s Project Application, number %s' % (settings.ACCOUNTS_ORG_NAME, project_application.id))

        # Footer
        footer(canvas, doc)

        canvas.restoreState()

    def myLaterPages(canvas, doc):
        canvas.saveState()

        # Footer
        footer(canvas, doc)

        canvas.restoreState()


    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    doc.pagesize = portrait(A4)
    doc.topMargin = 50
    story = []

    # Paragraph
    pstyle = ParagraphStyle(
        name="notesP",
        fontName="Times-Roman",
        fontSize=10,
        textColor=colors.Color(0,0,0),
        spaceBefore=10,
        spaceAfter=2)

    # indent
    istyle = ParagraphStyle(
        name="notesP",
        fontName="Times-Roman",
        fontSize=10,
        leftIndent=20,
        textColor=colors.Color(0,0,0),
        spaceAfter=2)

    # double indent
    iistyle = ParagraphStyle(
        name="notesP",
        fontName="Times-Roman",
        fontSize=10,
        leftIndent=40,
        textColor=colors.Color(0,0,0),
        spaceAfter=2)

    # gray small text
    estyle = ParagraphStyle(
        name="notesP",
        fontName="Times-Roman",
        fontSize=9,
        textColor=colors.gray,
        leftIndent=2,
        spaceAfter=2)

    # Heading
    hstyle = ParagraphStyle(
        name="notesP",
        fontName="Times-Roman",
        fontSize=14,
        textColor=colors.Color(0,0,0),
        spaceBefore=10,
        spaceAfter=15)

    table_style = TableStyle(
        [('INNERGRID', (0, 0), (-1, -1), 0.25, colors.black),
         ('BOX', (0, 0), (-1, -1), 0.25, colors.black),
         ]
    )

    # Project Overview
    story.append(Paragraph('<b>Project Overview</b>', hstyle))
    story.append(Paragraph('<b>Title:</b> %s' % (safe_or_none(project_application.title) or '&lt;incomplete&gt;'), pstyle))

    # TODO supervisor and applicant summary
    sup = ProjectApplicationMember.objects.filter(project_application=project_application, is_supervisor=True)[0] # should always be only one
    app = ProjectApplicationMember.objects.filter(project_application=project_application, is_applicant=True)[0] # should always be only one


    story.append(Paragraph('<b>Host Institute, Faculty and Department:</b> %s, %s, %s' %
           (safe_or_none(sup.institute) or '&lt;incomplete&gt;',
            safe_or_none(sup.faculty) or '&lt;incomplete&gt;',
            safe_or_none(sup.department) or '&lt;incomplete&gt;'), pstyle))
    story.append(Paragraph('The host institute, faculty and department of the Project Supervisor', estyle))

    story.append(Paragraph('<b>Field of Research:</b> %s' % (safe_or_none(project_application.get_FOR_display()) or '&lt;incomplete&gt;'), pstyle))

    if project_application.summary:
        summary = safe_or_none(project_application.summary).replace('\n', '<br/>')
    else:
        summary = '&lt;incomplete&gt;'
    story.append(Paragraph('<b>Summary of Proposal:</b>', pstyle))
    story.append(Paragraph('%s' % summary, istyle))

    if project_application.purpose:
        purpose = safe_or_none(project_application.purpose).replace('\n', '<br/>')
    else:
        purpose = '&lt;incomplete&gt;'
    story.append(Paragraph('<b>Supported Activity:</b>', pstyle))
    story.append(Paragraph('%s' % purpose, istyle))

    story.append(PageBreak())


    # Personnel
    story.append(Paragraph('<b>Personnel</b>', hstyle))

    story.append(Paragraph('<b>Participants</b>', pstyle))
    # build the Participant table
    data_list = ProjectApplicationMember.objects.filter(project_application=project_application).values_list(
            'is_applicant', 'is_supervisor', 'is_leader',
            'email', 'title', 'first_name', 'last_name',
            'institute', 'faculty', 'department', 'telephone', 'level', 'role').order_by('disp_order')
    for ap,sv,mg,em,tl,fn,ln,inst,fac,dept,tel,lvl,rl in data_list:
        flags = []
        story.append(Paragraph('Name: <b>%s %s %s</b>' % (safe_or_none(tl) or '&lt;incomplete&gt;',
                safe_or_none(fn) or '&lt;incomplete&gt;', safe_or_none(ln) or '&lt;incomplete&gt;'), pstyle))
        story.append(Paragraph('e-mail: %s' % (safe_or_none(em) or '&lt;incomplete&gt;'), istyle))
        if ap:
            flags.append('Applicant')
        if sv:
            flags.append('Project Supervisor')
        if mg:
            flags.append('Project Manager')
        if flags:
            story.append(Paragraph('%s' % (', '.join(flags)), istyle))
        story.append(Paragraph('Institute: %s, Faculty: %s, Department: %s' % (safe_or_none(inst) or '&lt;incomplete&gt;',
                safe_or_none(fac) or '&lt;incomplete&gt;', safe_or_none(dept) or '&lt;incomplete&gt;'), istyle))
        story.append(Paragraph('Telephone: %s' % (safe_or_none(tel) or '&lt;incomplete&gt;'), istyle))
        # get long description for 1st match of level and role abbreviation
        if lvl:
            lvl = next(safe_or_none(y) for x,y in ProjectApplicationMember.LEVELS if x == lvl)
        else:
            lvl = '&lt;incomplete&gt;'
        if rl:
            rl = next(safe_or_none(y) for x,y in ProjectApplicationMember.ROLES if x == rl)
        else:
            rl = '&lt;incomplete&gt;'
        story.append(Paragraph('Level: %s, Role: %s' % (lvl, rl), istyle))

    story.append(PageBreak())

    if project_application.hardware_request:
        hardware_request = safe_or_none(project_application.hardware_request).replace('\n', '<br/>')
    else:
        hardware_request = '&lt;left blank&gt;'
    story.append(Paragraph('<b>Sepcial Requirements:</b>', pstyle))
    story.append(Paragraph('%s' % hardware_request, istyle))

    if project_application.compute_note:
        compute_note = safe_or_none(project_application.compute_note).replace('\n', '<br/>')
    else:
        compute_note = '&lt;left blank&gt;'
    story.append(Paragraph('<b>Additional Information:</b>', pstyle))
    story.append(Paragraph('%s' % compute_note, istyle))


    doc.build(story, onFirstPage=myFirstPage, onLaterPages=myLaterPages)

    # Close the PDF object cleanly.
    pdf = buffer.getvalue()
    buffer.close()

    return pdf


def project_application_to_pdf(project_application):

    response = HttpResponse(content_type='application/pdf')

    fname = "%s-Resource-Application-%s.pdf" % (settings.ACCOUNTS_ORG_NAME, project_application.id)
    response['Content-Disposition'] = 'attachment; filename= ' + fname

#    logger.debug(project_application)

    pdf = project_application_to_pdf_doc(project_application)

    # Get the value of the StringIO buffer and write it to the response.
    response.write(pdf)
    return response
