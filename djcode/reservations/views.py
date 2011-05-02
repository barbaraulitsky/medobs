from datetime import datetime, date, time, timedelta
import simplejson as json

from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _

from djcode.reservations.forms import Patient_form
from djcode.reservations.models import Medical_office, Patient
from djcode.reservations.models import get_hexdigest

class DateInPast(Exception):
	pass

class BadStatus(Exception):
	pass

def front_page(request):
	message = None
	actual_date = date.today() + timedelta(1)
	datetime_limit = datetime.combine(actual_date, time(0, 0))
	reservation_id = 0

	if request.method == 'POST':
		form = Patient_form(request.POST)
		if form.is_valid():
			try:
				reservation = form.cleaned_data["reservation"]
				actual_date = reservation.starting_time.date()
				reservation_id = reservation.id

				if reservation.status != 2:
					raise BadStatus()

				if reservation.starting_time < datetime_limit:
					raise DateInPast()

				hexdigest = get_hexdigest(form.cleaned_data["ident_hash"])
				patient, patient_created = Patient.objects.get_or_create(ident_hash=hexdigest,
						defaults={
							"first_name": form.cleaned_data["first_name"],
							"last_name": form.cleaned_data["last_name"],
							"ident_hash": form.cleaned_data["ident_hash"],
							"phone_number": form.cleaned_data["phone_number"],
							"email": form.cleaned_data["email"],
						})

				if not patient_created and patient.has_reservation():
					return HttpResponseRedirect("/cancel/%d/" % reservation.place_id)

				reservation.patient = patient
				reservation.exam_kind = form.cleaned_data["exam_kind"]
				reservation.status = 3
				reservation.booked_at = datetime.now()
				reservation.save()

				return HttpResponseRedirect("/booked/%d/" % reservation.place_id)
			except DateInPast:
				message = _("You cannot make reservation for today or date in the past.")
			except BadStatus:
				message = _("The reservation has been already booked. Please try again.")
				reservation_id = 0
	else:
		form = Patient_form()
	
	return render_to_response(
		"index.html",
		{
			"places": get_places(actual_date),
			"form": form,
			"message": message,
			"actual_date": actual_date,
			"reservation_id": reservation_id,
		},
		context_instance=RequestContext(request)
	)

def get_places(actual_date):
	offices = Medical_office.objects.order_by("pk")
	return [{"id": o.id, "name": o.name, "reservations": o.reservations(actual_date)} for o in offices]

def date_reservations(request, for_date):
	for_date = datetime.strptime(for_date, "%Y-%m-%d").date()
	response_data = []

	for place in Medical_office.objects.all():
		if request.user.is_authenticated():
			reservations = [{
				"id": r.id,
				"time": r.starting_time.time().strftime("%H:%M"),
				"status": r.status,
				"patient": r.patient.full_name if r.patient else "",
			} for r in place.reservations(for_date)]
		else:
			reservations = [{
				"id": r.id,
				"time": r.starting_time.time().strftime("%H:%M"),
				"disabled": True if r.status != 2 else False,
			} for r in place.reservations(for_date)]
		response_data.append({
			"place_id": place.id,
			"reservations": reservations
		})

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response
