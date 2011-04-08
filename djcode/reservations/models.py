from django.conf import settings
from django.db import models
from django.utils.hashcompat import sha_constructor
from django.utils.translation import ugettext_lazy as _

def get_hexdigest(user_input):
	return sha_constructor(settings.SECRET_KEY + user_input).hexdigest()

class Patient(models.Model):
	first_name = models.CharField(_("first name"), max_length=100)
	last_name = models.CharField(_("last name"), max_length=100)
	ident_hash = models.CharField(_("identify hash"), max_length=128, unique=True)
	phone_number = models.CharField(_("phone number"), max_length=100)
	email = models.EmailField(_("e-mail address"), blank=True)

	class Meta:
		verbose_name = _("patient")
		verbose_name_plural = _("patients")

	def __unicode__(self):
		return self.full_name
		
	def _get_full_name(self):
		"Returns the person's full name. Last name first."
		return "%s %s" % (self.last_name, self.first_name)
	full_name = property(_get_full_name)

	def save(self, *args, **kwargs):
		if not self.id:
			self.ident_hash = get_hexdigest(self.ident_hash)
		super(Patient, self).save(*args, **kwargs)

class Medical_office(models.Model):
	name = models.CharField(_("name"), max_length=100)
	street = models.TextField(_("street"))
	zip_code = models.CharField(_("zip code"), max_length=20)
	city = models.CharField(_("city"), max_length=100)
	email = models.EmailField(_("e-mail address"), blank=True)

	class Meta:
		verbose_name = _("medical office")
		verbose_name_plural = _("medical offices")

	def __unicode__(self):
		return self.name

class Office_phone(models.Model):
	number = models.CharField(_("number"), max_length=50)
	office = models.ForeignKey(Medical_office, verbose_name=_("medical office"),
			related_name="phone_numbers")

	class Meta:
		verbose_name = _("office phone")
		verbose_name_plural = _("office phones")

	def __unicode__(self):
		return self.number

class Visit_template(models.Model):
	DAYS = (
		(0, _("Sunday")),
		(1, _("Monday")),
		(2, _("Tuesday")),
		(3, _("Wednesday")),
		(4, _("Thursday")),
		(5, _("Friday")),
		(6, _("Saturday")),
	)
	day = models.PositiveSmallIntegerField(_("day"), choices=DAYS)
	starting_time = models.TimeField(_("starting time"))
	valid_since = models.DateField(_("valid since"),
			help_text=_("This date is included into interval."))
	valid_until = models.DateField(_("valid until"), null=True, blank=True,
			help_text=_("This date is not included into interval."))

	class Meta:
		verbose_name = _("visit template")
		verbose_name_plural = _("visit templates")

	def __unicode__(self):
		return _("%s at %s") % (self.get_day_display(), self.starting_time)
