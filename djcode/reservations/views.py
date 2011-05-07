from datetime import datetime, date, time, timedelta
import simplejson as json
from view_utils import get_places, is_reservation_on_date

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.utils.translation import ugettext_lazy as _

from djcode.reservations.forms import Patient_form, Patient_detail_form
from djcode.reservations.models import Day_status, Medical_office, Patient, Visit_reservation
from djcode.reservations.models import get_hexdigest

def front_page(request):
	if request.user.is_authenticated():
		place = Medical_office.objects.order_by("pk")[0]
	else:
		place = Medical_office.objects.filter(public=True).order_by("pk")[0]
	return HttpResponseRedirect("/place/%d/" % place.id)

class DateInPast(Exception):
	pass

class BadStatus(Exception):
	pass

def place_page(request, place_id):
	place = get_object_or_404(Medical_office, pk=place_id)

	if not request.user.is_authenticated() and not place.public: # forbidden place
		return HttpResponseRedirect("/")

	message = None
	actual_date = date.today() + timedelta(1)
	end_date = actual_date + timedelta(settings.MEDOBS_GEN_DAYS-1)

	while not is_reservation_on_date(actual_date, place):
		actual_date += timedelta(1)
		if actual_date == end_date:
			break

	datetime_limit = datetime.combine(actual_date, time(0, 0))
	reservation_id = 0

	if request.method == 'POST':
		form = Patient_form(request.POST)
		if form.is_valid():
			try:
				reservation = form.cleaned_data["reservation"]
				actual_date = reservation.starting_time.date()
				reservation_id = reservation.id

				if request.user.is_authenticated():
					if reservation.status not in (2, 4):
						raise BadStatus()
				else:
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
				if not patient_created:
					patient.first_name = form.cleaned_data["first_name"]
					patient.last_name = form.cleaned_data["last_name"]
					patient.phone_number = form.cleaned_data["phone_number"]
					patient.email = form.cleaned_data["email"]
					patient.save()

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

	place_data = {
		"id": place.id,
		"name": place.name,
		"reservations": place.reservations(actual_date),
		"disabled_days": place.disabled_days(actual_date, end_date)
	}

	return render_to_response(
		"index.html",
		{
			"places": get_places(request.user),
			"place": place_data,
			"form": form,
			"message": message,
			"actual_date": actual_date,
			"end_date": end_date,
			"reservation_id": reservation_id,
		},
		context_instance=RequestContext(request)
	)

def date_reservations(request, for_date, place_id):
	place = get_object_or_404(Medical_office, pk=place_id)
	for_date = datetime.strptime(for_date, "%Y-%m-%d").date()

	if request.user.is_authenticated():
		response_data = [{
			"id": r.id,
			"time": r.starting_time.time().strftime("%H:%M"),
			"status": r.status,
			"patient": r.patient.full_name if r.patient else "",
		} for r in place.reservations(for_date)]
	else:
		response_data = [{
			"id": r.id,
			"time": r.starting_time.time().strftime("%H:%M"),
			"disabled": True if r.status != 2 else False,
		} for r in place.reservations(for_date)]

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def patient_details(request):
	response_data = {
		"first_name": "",
		"last_name": "",
		"phone_number": "",
		"email": "",
	}

	if request.method == 'POST':
		form = Patient_detail_form(request.POST)
		if form.is_valid():
			hexdigest = get_hexdigest(form.cleaned_data["ident_hash"])
			try:
				patient = Patient.objects.get(ident_hash=hexdigest)
				response_data = {
					"first_name": patient.first_name,
					"last_name": patient.last_name,
					"phone_number": patient.phone_number,
					"email": patient.email,
				}
			except Patient.DoesNotExist:
				pass
	return HttpResponse(json.dumps(response_data), "application/json")

@login_required
def hold_reservation(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	if reservation.status == 2:
		reservation.status = 4
		reservation.save()
		response_data = {"status_ok": True}
	else:
		response_data = {"status_ok": False}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def unhold_reservation(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	if reservation.status == 4:
		reservation.status = 2
		reservation.save()
		response_data = {"status_ok": True}
	else:
		response_data = {"status_ok": False}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def unbook_reservation(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	if reservation.status == 3:
		reservation.status = 2
		reservation.patient = None
		reservation.exam_kind = None
		reservation.booked_at = None
		reservation.save()
		response_data = {"status_ok": True}
	else:
		response_data = {"status_ok": False}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def disable_reservation(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	if reservation.status in (2, 4) and request.user.is_staff:
		reservation.status = 1
		reservation.save()
		response_data = {"status_ok": True}
	else:
		response_data = {"status_ok": False}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def enable_reservation(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	if reservation.status == 1 and request.user.is_staff:
		reservation.status = 2
		reservation.save()
		response_data = {"status_ok": True}
	else:
		response_data = {"status_ok": False}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response

@login_required
def list_reservations(request, for_date, place_id):
	for_date = datetime.strptime(for_date, "%Y-%m-%d").date()
	place = get_object_or_404(Medical_office, pk=place_id)

	reservations = place.reservations(for_date)

	return render_to_response(
		"list_reservations.html",
		{
			"for_date": for_date,
			"place": place,
			"reservations": reservations,
		},
		context_instance=RequestContext(request)
	)

@login_required
def reservation_details(request, r_id):
	reservation = get_object_or_404(Visit_reservation, pk=r_id)
	response_data = {
		"first_name": reservation.patient.first_name,
		"last_name": reservation.patient.last_name,
		"phone_number": reservation.patient.phone_number,
		"email": reservation.patient.email,
		"exam_kind": reservation.exam_kind_id,
	}

	response = HttpResponse(json.dumps(response_data), "application/json")
	response["Cache-Control"] = "no-cache"
	return response
