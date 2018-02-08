from django import forms
from django.db import models
from django.core.validators import MaxLengthValidator
from django.utils.translation import ugettext_lazy as _


# custom text area for word limits
# model field
class TextLengthField(models.TextField):

    description = _("Text (up to %(max_length)s characters)")

    widget_attrs = {
        'cols': '120',
        'rows': '20',
    }

    # can pass max_length and widget_attrs to TextField
    def __init__(self, *args, **kwargs):
        if kwargs and 'widget_attrs' in kwargs:
            self.widget_attrs.update(kwargs.pop('widget_attrs'))

        super(TextLengthField, self).__init__(*args, **kwargs)
        if self.max_length:
            self.validators.append(MaxLengthValidator(self.max_length))

    def formfield(self, **kwargs):
        defaults = {
            'max_length': self.max_length,
            'widget': forms.Textarea(attrs=self.widget_attrs),
        }
        defaults.update(kwargs)
        return super(TextLengthField, self).formfield(**defaults)


# for south datamigration, need to tell south about new model field
try:
    from south.modelsinspector import add_introspection_rules
    add_introspection_rules([], ["^project_application\.project_application\.fields\.TextLengthField"])
except ImportError:
    pass
