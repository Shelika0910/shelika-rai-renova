from datetime import timedelta, datetime, date
import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum

from .models import (
	PatientMCQResult, Appointment, Notification,
	TherapistAvailability, TherapistDayOff, SessionReport, Message,
	Resource, GuidedExercise, ActivityLog, TherapistRating,
)
from .youtube_service import get_youtube_videos
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


User = get_user_model()


# ─── helpers ────────────────────────────────────────────────────────────────
def _unread(user):
	return Notification.objects.filter(user=user, is_read=False).count()

def _unread_msgs(user):
	return Message.objects.filter(receiver=user, is_read=False).count()

def _notify(user, ntype, title, msg, appointment=None, redirect_url=""):
	Notification.objects.create(
		user=user, type=ntype, title=title, message=msg,
		related_appointment=appointment, redirect_url=redirect_url,
	)


# ─── auth ───────────────────────────────────────────────────────────────────
def home(request):
	return render(request, "base.html")


def login_view(request):
	if request.user.is_authenticated:
		return redirect("accounts:dashboard_redirect")

	if request.method == "POST":
		email = request.POST.get("email", "").strip().lower()
		password = request.POST.get("password", "")

		user = authenticate(request, username=email, password=password)
		if user is None:
			messages.error(request, "Invalid email or password.")
		else:
			login(request, user)
			return redirect("accounts:dashboard_redirect")

	return render(request, "auth/login.html")


def register_view(request):
	if request.user.is_authenticated:
		return redirect("accounts:dashboard_redirect")

	if request.method == "POST":
		full_name = request.POST.get("full_name", "").strip()
		email = request.POST.get("email", "").strip().lower()
		password1 = request.POST.get("password1", "")
		password2 = request.POST.get("password2", "")
		role = request.POST.get("role", "patient").strip().lower()
		account_role = "therapist" if role == "doctor" else "patient"
		has_error = False

		if not full_name:
			messages.error(request, "Full name is required.")
			has_error = True
		elif role not in {"patient", "doctor"}:
			messages.error(request, "Please select a valid role.")
			has_error = True
		elif password1 != password2:
			messages.error(request, "Passwords do not match.")
			has_error = True
		elif len(password1) < 8:
			messages.error(request, "Password must be at least 8 characters.")
			has_error = True
		elif not email:
			messages.error(request, "Email is required.")
			has_error = True
		elif Group.objects.filter(name=role).exists() is False:
			Group.objects.create(name=role)

		if not has_error:
			if User.objects.filter(email=email).exists():
				messages.error(request, "An account with this email already exists.")
			else:
				specialization = ""
				if role == "doctor":
					specialization = request.POST.get("specialization", "").strip()
				user = User.objects.create_user(
					email=email,
					full_name=full_name,
					role=account_role,
					specialization=specialization,
					password=password1,
				)
				user.groups.add(Group.objects.get(name=role))
				login(request, user)
				messages.success(request, "Account created successfully.")
				return redirect("accounts:dashboard_redirect")

	return render(request, "auth/register.html")


def logout_view(request):
	logout(request)
	messages.success(request, "You have been logged out.")
	return redirect("accounts:home")


@login_required
def dashboard_redirect(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	if not PatientMCQResult.objects.filter(user=request.user).exists():
		return redirect("accounts:patient_mcq")
	return redirect("accounts:patient_dashboard")


# ─── patient MCQ ────────────────────────────────────────────────────────────
@login_required
def patient_mcq(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	if PatientMCQResult.objects.filter(user=request.user).exists():
		return redirect("accounts:patient_dashboard")

	if request.method == "POST":
		answers = {}
		for i in range(1, 11):
			val = request.POST.get(f"q{i}")
			answers[f"q{i}"] = int(val) if val is not None else 0

		total = sum(answers.values())
		anxiety_score = answers.get("q1", 0) + answers.get("q6", 0)
		depression_score = answers.get("q3", 0) + answers.get("q7", 0)
		stress_score = answers.get("q5", 0) + answers.get("q2", 0)
		ptsd_score = answers.get("q4", 0) + answers.get("q9", 0)

		scores = {
			"anxiety": anxiety_score,
			"depression": depression_score,
			"stress": stress_score,
			"ptsd": ptsd_score,
		}
		category = max(scores, key=scores.get)
		if total <= 5:
			category = "general"

		PatientMCQResult.objects.create(
			user=request.user, answers=answers, category=category, score=total,
		)
		messages.success(request, "Assessment complete! Welcome to your dashboard.")
		return redirect("accounts:patient_dashboard")

	return render(request, "patient/mcq_assessment.html")


# ─── patient dashboard ──────────────────────────────────────────────────────
@login_required
def patient_dashboard(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	if not PatientMCQResult.objects.filter(user=request.user).exists():
		return redirect("accounts:patient_mcq")

	mcq = PatientMCQResult.objects.get(user=request.user)
	recommended_therapists = User.objects.filter(
		role="therapist", specialization=mcq.category, is_active=True
	)
	all_therapists = User.objects.filter(role="therapist", is_active=True)
	
	# Daily supportive quotes based on MCQ category
	import random
	from datetime import date
	
	quotes_by_category = {
		"anxiety": [
			{"text": "You don't have to control your thoughts. You just have to stop letting them control you.", "author": "Dan Millman"},
			{"text": "Nothing diminishes anxiety faster than action.", "author": "Walter Anderson"},
			{"text": "Breathe. Let go. And remind yourself that this very moment is the only one you know you have for sure.", "author": "Oprah Winfrey"},
			{"text": "You are stronger than your anxiety. Every breath you take is proof of your resilience.", "author": "Unknown"},
			{"text": "Courage is not the absence of fear, but rather the judgment that something else is more important than fear.", "author": "Ambrose Redmoon"},
			{"text": "The way to develop self-confidence is to do the thing you fear.", "author": "William Jennings Bryan"},
			{"text": "Peace is the result of retraining your mind to process life as it is, rather than as you think it should be.", "author": "Wayne Dyer"},
		],
		"depression": [
			{"text": "Even the darkest night will end and the sun will rise.", "author": "Victor Hugo"},
			{"text": "You are not your illness. You have an individual story to tell.", "author": "Julian Seifter"},
			{"text": "There is hope, even when your brain tells you there isn't.", "author": "John Green"},
			{"text": "Your present circumstances don't determine where you can go; they merely determine where you start.", "author": "Nido Qubein"},
			{"text": "Start where you are. Use what you have. Do what you can.", "author": "Arthur Ashe"},
			{"text": "You are loved just for being who you are, just for existing.", "author": "Ram Dass"},
			{"text": "Every day is a new beginning. Take a deep breath and start again.", "author": "Unknown"},
		],
		"stress": [
			{"text": "It's not stress that kills us, it is our reaction to it.", "author": "Hans Selye"},
			{"text": "The greatest weapon against stress is our ability to choose one thought over another.", "author": "William James"},
			{"text": "Almost everything will work again if you unplug it for a few minutes, including you.", "author": "Anne Lamott"},
			{"text": "In the middle of difficulty lies opportunity.", "author": "Albert Einstein"},
			{"text": "Take rest; a field that has rested gives a bountiful crop.", "author": "Ovid"},
			{"text": "Don't let yesterday take up too much of today.", "author": "Will Rogers"},
			{"text": "Within you, there is a stillness and sanctuary to which you can retreat and be yourself.", "author": "Hermann Hesse"},
		],
		"ptsd": [
			{"text": "Healing takes courage, and we all have courage, even if we have to dig a little to find it.", "author": "Tori Amos"},
			{"text": "You have been assigned this mountain to show others it can be moved.", "author": "Mel Robbins"},
			{"text": "Trauma creates change you don't choose. Healing is about creating change you do choose.", "author": "Michelle Rosenthal"},
			{"text": "The wound is the place where the Light enters you.", "author": "Rumi"},
			{"text": "You survived. You're going to survive the recovery too.", "author": "Unknown"},
			{"text": "Recovery is not a race. You don't have to feel guilty if it takes you longer than you thought.", "author": "Unknown"},
			{"text": "Your trauma is valid. Your healing is valid. Your pace is valid.", "author": "Unknown"},
		],
	}
	
	general_quotes = [
		{"text": "You are enough just as you are. Each emotion you feel, everything you do, you're doing the best you can.", "author": "Unknown"},
		{"text": "Self-care is not selfish. You cannot serve from an empty vessel.", "author": "Eleanor Brown"},
		{"text": "Be gentle with yourself. You're doing the best you can.", "author": "Unknown"},
		{"text": "Mental health is not a destination, but a process. It's about how you drive, not where you're going.", "author": "Noam Shpancer"},
		{"text": "Every day may not be good, but there is something good in every day.", "author": "Alice Morse Earle"},
		{"text": "Taking care of yourself is productive.", "author": "Unknown"},
		{"text": "You don't have to be positive all the time. It's okay to feel your feelings.", "author": "Lori Deschene"},
	]
	
	# Get quote based on category or use general quotes
	category_quotes = quotes_by_category.get(mcq.category, general_quotes)
	
	# Use date as seed for consistent daily quote
	today = date.today()
	random.seed(today.toordinal())
	daily_quote = random.choice(category_quotes)
	
	# Get upcoming appointments
	upcoming_appointments = Appointment.objects.filter(
		patient=request.user,
		date_time__gt=timezone.now(),
		status="confirmed"
	).order_by("date_time")[:3]
	
	# Get session stats
	completed_sessions = Appointment.objects.filter(patient=request.user, status="completed").count()
	total_appointments = Appointment.objects.filter(patient=request.user).count()
	
	# Get today's activities (tasks, challenges, mood)
	today_activities = ActivityLog.objects.filter(user=request.user, date=today)
	today_tasks = list(today_activities.filter(activity_type="task").values_list("title", flat=True))
	today_challenges = list(today_activities.filter(activity_type="challenge").values_list("title", flat=True))
	today_mood = today_activities.filter(activity_type="mood").first()
	today_mood_value = today_mood.mood if today_mood else ""
	
	# Wellness tips based on category
	wellness_tips = {
		"anxiety": [
			{"icon": "🧘", "tip": "Try 5-4-3-2-1 grounding: Notice 5 things you see, 4 you touch, 3 you hear, 2 you smell, 1 you taste"},
			{"icon": "🌿", "tip": "Practice box breathing: Inhale 4 sec, hold 4 sec, exhale 4 sec, hold 4 sec"},
			{"icon": "📝", "tip": "Write down your worries to externalize them from your mind"},
		],
		"depression": [
			{"icon": "☀️", "tip": "Get 15 minutes of sunlight today - it boosts serotonin naturally"},
			{"icon": "🚶", "tip": "A 10-minute walk can improve your mood for 2 hours"},
			{"icon": "📱", "tip": "Reach out to one person today - connection heals"},
		],
		"stress": [
			{"icon": "🎵", "tip": "Listen to calming music for 10 minutes to lower cortisol"},
			{"icon": "💤", "tip": "Prioritize 7-8 hours of sleep for stress resilience"},
			{"icon": "⏰", "tip": "Take short breaks every 90 minutes to reset your mind"},
		],
		"ptsd": [
			{"icon": "🏠", "tip": "Create a safe space at home with comforting items"},
			{"icon": "📰", "tip": "Limit news and social media exposure when feeling vulnerable"},
			{"icon": "🧡", "tip": "Practice self-compassion - you're doing incredibly well"},
		],
	}
	
	category_tips = wellness_tips.get(mcq.category, [
		{"icon": "🌟", "tip": "Start your day with 3 things you're grateful for"},
		{"icon": "💧", "tip": "Stay hydrated - drink at least 8 glasses of water today"},
		{"icon": "🤗", "tip": "Be kind to yourself - you're making progress every day"},
	])

	context = {
		"mcq": mcq,
		"recommended_therapists": recommended_therapists,
		"all_therapists": all_therapists,
		"category_display": dict(PatientMCQResult.CATEGORY_CHOICES).get(mcq.category, "General Wellness"),
		"unread_notifications": _unread(request.user),
		"unread_messages": _unread_msgs(request.user),
		"daily_quote": daily_quote,
		"upcoming_appointments": upcoming_appointments,
		"completed_sessions": completed_sessions,
		"total_appointments": total_appointments,
		"wellness_tips": category_tips,
		"today_tasks": json.dumps(today_tasks),
		"today_challenges": json.dumps(today_challenges),
		"today_mood": today_mood_value,
	}
	return render(request, "patient/patient_dashboard.html", context)


@login_required
def find_therapist(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	therapists = User.objects.filter(role="therapist", is_active=True)

	# Get patient's MCQ result for recommendations
	mcq = PatientMCQResult.objects.filter(user=request.user).first()
	recommended_therapists = []
	if mcq:
		# Map MCQ category to therapist specialization
		category_to_spec = {
			"anxiety": "anxiety",
			"depression": "depression",
			"stress": "stress",
			"ptsd": "ptsd",
		}
		matched_spec = category_to_spec.get(mcq.category)
		if matched_spec:
			recommended_therapists = list(therapists.filter(specialization=matched_spec))

	# Optional search / filter
	q = request.GET.get("q", "").strip()
	spec = request.GET.get("specialization", "").strip()
	if q:
		therapists = therapists.filter(
			Q(full_name__icontains=q) | Q(bio__icontains=q)
		)
	if spec:
		therapists = therapists.filter(specialization=spec)

	# Attach availability info and ratings to each therapist
	for t in therapists:
		t.avail_slots = TherapistAvailability.objects.filter(therapist=t, is_active=True)
		t.is_recommended = t in recommended_therapists
		ratings = TherapistRating.objects.filter(therapist=t)
		t.avg_rating = ratings.aggregate(Avg("rating"))["rating__avg"]
		t.rating_count = ratings.count()
	
	# Also attach avail slots and ratings to recommended therapists
	for t in recommended_therapists:
		t.avail_slots = TherapistAvailability.objects.filter(therapist=t, is_active=True)
		ratings = TherapistRating.objects.filter(therapist=t)
		t.avg_rating = ratings.aggregate(Avg("rating"))["rating__avg"]
		t.rating_count = ratings.count()

	context = {
		"therapists": therapists,
		"recommended_therapists": recommended_therapists,
		"mcq": mcq,
		"search_query": q,
		"selected_specialization": spec,
		"specialization_choices": User.SPECIALIZATION_CHOICES,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/find_therapist.html", context)


@login_required
def view_therapist_profile(request, therapist_id):
	"""Patient-facing therapist profile with availability, booked times, and booking link."""
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	therapist = get_object_or_404(User, pk=therapist_id, role="therapist", is_active=True)
	slots = TherapistAvailability.objects.filter(therapist=therapist, is_active=True)

	from collections import defaultdict
	grouped = defaultdict(list)
	for s in slots:
		grouped[s.day_of_week].append(s)

	# Count completed appointments
	completed_count = Appointment.objects.filter(therapist=therapist, status="completed").count()

	# Get upcoming booked appointments for this therapist (next 14 days)
	future_cutoff = timezone.now() + timedelta(days=14)
	booked_appointments = Appointment.objects.filter(
		therapist=therapist,
		date_time__gte=timezone.now(),
		date_time__lte=future_cutoff,
		status__in=["requested", "confirmed"],
	).order_by("date_time")

	# Group booked by date for display
	booked_by_date = defaultdict(list)
	for apt in booked_appointments:
		booked_by_date[apt.date_time.date()].append(apt)

	# Get days off for this therapist
	days_off = TherapistDayOff.objects.filter(therapist=therapist, date__gte=date.today())

	context = {
		"therapist": therapist,
		"slots": slots,
		"grouped_slots": dict(grouped),
		"day_choices": TherapistAvailability.DAY_CHOICES,
		"completed_count": completed_count,
		"booked_by_date": dict(booked_by_date),
		"days_off": days_off,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/view_therapist_profile.html", context)


# ─── appointment booking (patient) ─────────────────────────────────────────
@login_required
def patient_appointments(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	now = timezone.now()
	upcoming = Appointment.objects.filter(
		patient=request.user, date_time__gt=now, status="confirmed"
	).order_by("date_time")
	past = Appointment.objects.filter(
		patient=request.user, status="completed"
	).order_by("-date_time")
	missed = Appointment.objects.filter(
		patient=request.user, date_time__lt=now, status__in=["requested", "confirmed"]
	).order_by("-date_time")
	requested = Appointment.objects.filter(
		patient=request.user, status="requested"
	).order_by("-created_at")
	cancelled = Appointment.objects.filter(
		patient=request.user, status__in=["cancelled", "rescheduled"]
	).order_by("-updated_at")

	context = {
		"upcoming_appointments": upcoming,
		"past_appointments": past,
		"missed_appointments": missed,
		"requested_appointments": requested,
		"cancelled_appointments": cancelled,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/patient_appointments.html", context)


@login_required
def book_appointment(request):
	"""Calendar-based appointment booking for patients."""
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	therapists = User.objects.filter(role="therapist", is_active=True)

	if request.method == "POST":
		therapist_id = request.POST.get("therapist_id")
		date_str = request.POST.get("appointment_date")
		time_str = request.POST.get("appointment_time")
		duration = int(request.POST.get("duration", 60))
		patient_notes = request.POST.get("patient_notes", "")

		if not all([therapist_id, date_str, time_str]):
			messages.error(request, "Please fill in all required fields.")
			return redirect("accounts:book_appointment")

		therapist = get_object_or_404(User, pk=therapist_id, role="therapist")
		dt = timezone.make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))

		if dt <= timezone.now():
			messages.error(request, "Cannot book appointments in the past.")
			return redirect("accounts:book_appointment")

		# Check for conflicting appointments
		conflict = Appointment.objects.filter(
			therapist=therapist, date_time=dt, status__in=["requested", "confirmed"]
		).exists()
		if conflict:
			messages.error(request, "This time slot is not available. Please choose another.")
			return redirect("accounts:book_appointment")

		apt = Appointment.objects.create(
			patient=request.user,
			therapist=therapist,
			date_time=dt,
			duration_minutes=duration,
			patient_notes=patient_notes,
		)
		_notify(
			therapist, "appointment_requested",
			"New Appointment Request",
			f"{request.user.full_name} has requested an appointment on {dt.strftime('%b %d, %Y at %I:%M %p')}.",
			apt,
			"/dashboard/therapist/appointments/"
		)
		messages.success(request, "Appointment request submitted successfully!")
		return redirect("accounts:patient_appointments")

	# Build availability + booked data for every therapist, keyed by therapist pk
	allAvail = {}  # {therapist_id: {day_of_week: [{start, end}]}}
	for t in therapists:
		slots_qs = TherapistAvailability.objects.filter(therapist=t, is_active=True)
		day_map = {}
		for s in slots_qs:
			day_map.setdefault(s.day_of_week, []).append({
				"start": s.start_time.strftime("%H:%M"),
				"end": s.end_time.strftime("%H:%M"),
				"display_start": s.start_time.strftime("%I:%M %p"),
				"display_end": s.end_time.strftime("%I:%M %p"),
			})
		allAvail[str(t.pk)] = day_map

	# Booked times per therapist for the next 90 days
	future_cutoff = timezone.now() + timedelta(days=90)
	booked_qs = Appointment.objects.filter(
		therapist__in=therapists,
		date_time__gte=timezone.now(),
		date_time__lte=future_cutoff,
		status__in=["requested", "confirmed"],
	).values_list("therapist_id", "date_time")
	allBooked = {}  # {therapist_id: {date_str: [time_str]}}
	for tid, dt_val in booked_qs:
		allBooked.setdefault(str(tid), {}).setdefault(
			dt_val.strftime("%Y-%m-%d"), []
		).append(dt_val.strftime("%H:%M"))

	# Check for pre-selected therapist (from Find Therapist / profile page)
	preselected = request.GET.get("therapist", "")

	context = {
		"therapists": therapists,
		"all_avail_json": json.dumps(allAvail),
		"all_booked_json": json.dumps(allBooked),
		"preselected_therapist_id": preselected,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/book_appointment.html", context)


@login_required
def cancel_appointment(request, appointment_id):
	"""Cancel an appointment."""
	apt = get_object_or_404(Appointment, pk=appointment_id)
	if request.user not in (apt.patient, apt.therapist):
		messages.error(request, "Unauthorized.")
		return redirect("accounts:dashboard_redirect")

	if request.method == "POST":
		reason = request.POST.get("cancellation_reason", "")
		apt.status = "cancelled"
		apt.cancellation_reason = reason
		apt.save()
		# Notify the other party
		other = apt.therapist if request.user == apt.patient else apt.patient
		redirect_path = "/dashboard/patient/appointments/" if other.role == "patient" else "/dashboard/therapist/appointments/"
		_notify(
			other, "appointment_cancelled",
			"Appointment Cancelled",
			f"Your appointment on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')} has been cancelled by {request.user.full_name}. Reason: {reason or 'Not specified'}",
			apt,
			redirect_path
		)
		messages.success(request, "Appointment cancelled.")
		return redirect("accounts:patient_appointments" if request.user == apt.patient else "accounts:therapist_appointments")

	return render(request, "appointments/cancel_appointment.html", {
		"appointment": apt,
		"unread_notifications": _unread(request.user),
	})


@login_required
def reschedule_appointment(request, appointment_id):
	"""Reschedule an appointment by creating a new one and marking old as rescheduled."""
	old_apt = get_object_or_404(Appointment, pk=appointment_id)
	if request.user not in (old_apt.patient, old_apt.therapist):
		messages.error(request, "Unauthorized.")
		return redirect("accounts:dashboard_redirect")

	if request.method == "POST":
		date_str = request.POST.get("appointment_date")
		time_str = request.POST.get("appointment_time")
		if not all([date_str, time_str]):
			messages.error(request, "Please select a new date and time.")
			return redirect("accounts:reschedule_appointment", appointment_id=appointment_id)

		dt = timezone.make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
		if dt <= timezone.now():
			messages.error(request, "Cannot reschedule to a past time.")
			return redirect("accounts:reschedule_appointment", appointment_id=appointment_id)

		old_apt.status = "rescheduled"
		old_apt.save()

		new_apt = Appointment.objects.create(
			patient=old_apt.patient,
			therapist=old_apt.therapist,
			date_time=dt,
			duration_minutes=old_apt.duration_minutes,
			status="requested",
			rescheduled_from=old_apt,
		)
		other = old_apt.therapist if request.user == old_apt.patient else old_apt.patient
		redirect_path = "/dashboard/patient/appointments/" if other.role == "patient" else "/dashboard/therapist/appointments/"
		_notify(
			other, "appointment_rescheduled",
			"Appointment Rescheduled",
			f"Appointment on {old_apt.date_time.strftime('%b %d, %Y at %I:%M %p')} has been rescheduled to {dt.strftime('%b %d, %Y at %I:%M %p')} by {request.user.full_name}.",
			new_apt,
			redirect_path
		)
		messages.success(request, "Appointment rescheduled successfully!")
		return redirect("accounts:patient_appointments" if request.user == old_apt.patient else "accounts:therapist_appointments")

	# Embed therapist availability + booked data
	slots_qs = TherapistAvailability.objects.filter(therapist=old_apt.therapist, is_active=True)
	day_map = {}
	for s in slots_qs:
		day_map.setdefault(s.day_of_week, []).append({
			"start": s.start_time.strftime("%H:%M"),
			"end": s.end_time.strftime("%H:%M"),
			"display_start": s.start_time.strftime("%I:%M %p"),
			"display_end": s.end_time.strftime("%I:%M %p"),
		})

	future_cutoff = timezone.now() + timedelta(days=90)
	booked_qs = Appointment.objects.filter(
		therapist=old_apt.therapist,
		date_time__gte=timezone.now(),
		date_time__lte=future_cutoff,
		status__in=["requested", "confirmed"],
	).values_list("date_time", flat=True)
	booked_map = {}
	for dt_val in booked_qs:
		booked_map.setdefault(dt_val.strftime("%Y-%m-%d"), []).append(dt_val.strftime("%H:%M"))

	context = {
		"appointment": old_apt,
		"avail_json": json.dumps(day_map),
		"booked_json": json.dumps(booked_map),
		"unread_notifications": _unread(request.user),
	}
	return render(request, "appointments/reschedule_appointment.html", context)


# ─── patient resources ───────────────────────────────────────────────────────
@login_required
def patient_resources(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	# Get patient MCQ category for personalization
	mcq = PatientMCQResult.objects.filter(user=request.user).first()
	patient_category = mcq.category if mcq else "general"
	category_display = dict(PatientMCQResult.CATEGORY_CHOICES).get(patient_category, "General Wellness")

	# Personalized recommendations
	personalized_recommendations = []
	
	# Get personalized recommendations based on watch history
	from .models import VideoWatchHistory, SearchHistory
	recent_watches = VideoWatchHistory.objects.filter(user=request.user).order_by('-watched_at')[:10]
	recent_searches = SearchHistory.objects.filter(user=request.user).order_by('-searched_at')[:5]
	
	# Build personalized query from history
	watch_categories = list(set([watch.category for watch in recent_watches if watch.category]))
	search_terms = [search.query for search in recent_searches if search.query]
	
	if watch_categories or search_terms:
		# Create personalized query combining watch history and search history
		personal_query_parts = []
		if watch_categories:
			personal_query_parts.extend(watch_categories[:3])  # Top 3 categories
		if search_terms:
			personal_query_parts.extend(search_terms[:2])  # Top 2 search terms
		
		personal_query = " ".join(personal_query_parts)
		personalized_recommendations = get_youtube_videos(query=personal_query, max_results=15)

	# Filter by type tab (default: all)
	active_type = request.GET.get("type", "all")
	active_category = request.GET.get("cat", "recommended")

	# Build resource querysets
	if active_category == "recommended":
		resources_qs = Resource.objects.filter(category=patient_category)
	elif active_category == "all":
		resources_qs = Resource.objects.all()
	else:
		resources_qs = Resource.objects.filter(category=active_category)

	# All resources are now videos, no type filtering needed

	# Featured resources (always from patient's category or general)
	featured = Resource.objects.filter(
		is_featured=True, category__in=[patient_category, "general"]
	)[:4]

	# Guided exercises - personalized
	if active_category == "recommended":
		exercises_qs = GuidedExercise.objects.filter(category=patient_category)
	elif active_category == "all":
		exercises_qs = GuidedExercise.objects.all()
	else:
		exercises_qs = GuidedExercise.objects.filter(category=active_category)

	# All resources are now YouTube videos
	videos = resources_qs

	# Fetch YouTube videos - multiple categories
	youtube_queries = {
		"anxiety": "anxiety relief guided meditation calm",
		"depression": "depression recovery motivation hope",
		"stress": "stress relief relaxation techniques",
		"ptsd": "ptsd healing trauma recovery guided",
		"general": "mental health wellness positive mindset",
	}
	
	# Determine which category to search for YouTube
	if active_category == "recommended":
		yt_category = patient_category
	elif active_category == "all":
		yt_category = patient_category
	else:
		yt_category = active_category
	
	# Fetch different video sections - only fetch what's needed based on active_type
	# "Recommended for You" is MCQ-based; all other sections use randomized generic queries
	yt_query = youtube_queries.get(yt_category, youtube_queries["general"])
	
	# Varied query pools per section so each load shows different videos
	import random
	query_pools = {
		"positive": [
			"positive thinking motivation inspirational self improvement",
			"motivational speeches uplifting energy positive vibes",
			"daily motivation confidence boost happy mindset",
			"inspiring stories success mindset positivity",
			"self improvement tips personal growth motivation",
		],
		"meditation": [
			"guided meditation mindfulness breathing relaxation",
			"deep meditation calming music inner peace",
			"morning meditation guided visualization calm",
			"body scan meditation progressive relaxation",
			"meditation for focus clarity concentration",
		],
		"yoga": [
			"yoga for beginners hatha vinyasa yin restorative",
			"gentle yoga flow stretching flexibility",
			"morning yoga routine energy boost",
			"yoga for relaxation evening wind down",
			"power yoga strength building practice",
		],
		"breathing": [
			"breathing exercises pranayama deep breathing anxiety",
			"box breathing technique calm nervous system",
			"4 7 8 breathing method relaxation",
			"diaphragmatic breathing stress relief exercises",
			"breathing techniques for sleep relaxation",
		],
		"sleep": [
			"sleep meditation bedtime stories deep sleep music",
			"relaxing music for sleep insomnia relief",
			"guided sleep meditation deep rest",
			"sleep hypnosis calming bedtime relaxation",
			"nature sounds rain sleep relaxation",
		],
		"meditation_tutorial": [
			"how to meditate for beginners meditation tutorial",
			"meditation basics step by step guide",
			"learn meditation techniques beginner friendly",
			"meditation posture breathing tutorial basics",
			"starting meditation practice tips for beginners",
		],
		"yoga_tutorial": [
			"yoga tutorial basic poses beginner instructions",
			"learn yoga fundamentals alignment tips",
			"yoga basics sun salutation tutorial",
			"beginner yoga poses proper form guide",
			"yoga foundations flexibility strength tutorial",
		],
		"mindfulness": [
			"mindfulness exercises daily mindfulness practice",
			"mindful living present moment awareness",
			"mindfulness meditation body awareness grounding",
			"daily mindfulness routine stress reduction",
			"mindful breathing awareness exercises practice",
		],
		"stress_relief": [
			"stress relief techniques stress management",
			"instant stress relief calming exercises",
			"stress reduction methods coping strategies",
			"relaxation techniques tension release calm",
			"managing stress daily life wellness tips",
		],
		"anxiety_help": [
			"anxiety relief techniques coping with anxiety",
			"overcoming anxiety calming strategies help",
			"anxiety management grounding techniques",
			"reduce anxiety naturally relaxation methods",
			"anxiety coping skills therapy techniques",
		],
		"self_care": [
			"self care routines mental health self care",
			"daily self care habits wellness routine",
			"self love practices emotional wellbeing",
			"self care ideas for mental health",
			"nurturing yourself self care tips wellness",
		],
	}
	
	youtube_recommended = []
	youtube_positive = []
	youtube_meditation = []
	youtube_yoga = []
	youtube_breathing = []
	youtube_sleep = []
	youtube_meditation_tutorial = []
	youtube_yoga_tutorial = []
	youtube_mindfulness = []
	youtube_stress_relief = []
	youtube_anxiety_help = []
	youtube_self_care = []
	
	def _random_query(section_key):
		return random.choice(query_pools[section_key])
	
	if active_type == "all":
		# Fetch all sections in PARALLEL so the page loads fast
		from concurrent.futures import ThreadPoolExecutor, as_completed
		tasks = {
			"recommended": (yt_query, 6, False),
			"positive": (_random_query("positive"), 6, True),
			"meditation": (_random_query("meditation"), 6, True),
			"yoga": (_random_query("yoga"), 6, True),
			"breathing": (_random_query("breathing"), 6, True),
			"sleep": (_random_query("sleep"), 6, True),
			"meditation_tutorial": (_random_query("meditation_tutorial"), 6, True),
			"yoga_tutorial": (_random_query("yoga_tutorial"), 6, True),
			"mindfulness": (_random_query("mindfulness"), 6, True),
			"stress_relief": (_random_query("stress_relief"), 6, True),
			"anxiety_help": (_random_query("anxiety_help"), 6, True),
			"self_care": (_random_query("self_care"), 6, True),
		}
		results = {}
		with ThreadPoolExecutor(max_workers=6) as executor:
			future_map = {
				executor.submit(get_youtube_videos, query=q, max_results=n, randomize=r): key
				for key, (q, n, r) in tasks.items()
			}
			for future in as_completed(future_map):
				key = future_map[future]
				try:
					results[key] = future.result()
				except Exception:
					results[key] = []
		youtube_recommended = results.get("recommended", [])
		youtube_positive = results.get("positive", [])
		youtube_meditation = results.get("meditation", [])
		youtube_yoga = results.get("yoga", [])
		youtube_breathing = results.get("breathing", [])
		youtube_sleep = results.get("sleep", [])
		youtube_meditation_tutorial = results.get("meditation_tutorial", [])
		youtube_yoga_tutorial = results.get("yoga_tutorial", [])
		youtube_mindfulness = results.get("mindfulness", [])
		youtube_stress_relief = results.get("stress_relief", [])
		youtube_anxiety_help = results.get("anxiety_help", [])
		youtube_self_care = results.get("self_care", [])
	elif active_type == "positive":
		youtube_positive = get_youtube_videos(query=_random_query("positive"), max_results=30, randomize=True)
	elif active_type == "meditation":
		youtube_meditation = get_youtube_videos(query=_random_query("meditation"), max_results=30, randomize=True)
	elif active_type == "yoga":
		youtube_yoga = get_youtube_videos(query=_random_query("yoga"), max_results=30, randomize=True)
	elif active_type == "breathing":
		youtube_breathing = get_youtube_videos(query=_random_query("breathing"), max_results=30, randomize=True)
	elif active_type == "sleep":
		youtube_sleep = get_youtube_videos(query=_random_query("sleep"), max_results=30, randomize=True)
	elif active_type == "meditation_tutorial":
		youtube_meditation_tutorial = get_youtube_videos(query=_random_query("meditation_tutorial"), max_results=30, randomize=True)
	elif active_type == "yoga_tutorial":
		youtube_yoga_tutorial = get_youtube_videos(query=_random_query("yoga_tutorial"), max_results=30, randomize=True)
	elif active_type == "mindfulness":
		youtube_mindfulness = get_youtube_videos(query=_random_query("mindfulness"), max_results=30, randomize=True)
	elif active_type == "stress_relief":
		youtube_stress_relief = get_youtube_videos(query=_random_query("stress_relief"), max_results=30, randomize=True)
	elif active_type == "anxiety_help":
		youtube_anxiety_help = get_youtube_videos(query=_random_query("anxiety_help"), max_results=30, randomize=True)
	elif active_type == "self_care":
		youtube_self_care = get_youtube_videos(query=_random_query("self_care"), max_results=30, randomize=True)

	context = {
		"patient_category": patient_category,
		"category_display": category_display,
		"active_type": active_type,
		"active_category": active_category,
		"featured": featured,
		"videos": videos,
		"exercises": exercises_qs,
		"resources": resources_qs,
		"youtube_recommended": youtube_recommended,
		"youtube_positive": youtube_positive,
		"youtube_meditation": youtube_meditation,
		"youtube_yoga": youtube_yoga,
		"youtube_breathing": youtube_breathing,
		"youtube_sleep": youtube_sleep,
		"youtube_meditation_tutorial": youtube_meditation_tutorial,
		"youtube_yoga_tutorial": youtube_yoga_tutorial,
		"youtube_mindfulness": youtube_mindfulness,
		"youtube_stress_relief": youtube_stress_relief,
		"youtube_anxiety_help": youtube_anxiety_help,
		"youtube_self_care": youtube_self_care,
		"personalized_recommendations": personalized_recommendations,
		"categories": PatientMCQResult.CATEGORY_CHOICES,
		# All resources are videos now
		"unread_notifications": _unread(request.user),
		"unread_messages": _unread_msgs(request.user),
	}
	return render(request, "patient/resources.html", context)


@login_required
def exercise_detail(request, exercise_id):
	"""View a single guided exercise with step-by-step instructions."""
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")

	exercise = get_object_or_404(GuidedExercise, id=exercise_id)
	mcq = PatientMCQResult.objects.filter(user=request.user).first()
	patient_category = mcq.category if mcq else "general"

	# Related exercises in the same category
	related = GuidedExercise.objects.filter(category=exercise.category).exclude(id=exercise.id)[:4]

	context = {
		"exercise": exercise,
		"related_exercises": related,
		"patient_category": patient_category,
		"unread_notifications": _unread(request.user),
		"unread_messages": _unread_msgs(request.user),
	}
	return render(request, "patient/exercise_detail.html", context)


@login_required
def ai_chatbot(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	return render(request, "patient/patient_page.html", {
		"page_title": "AI-Chatbot",
		"page_text": "Chat with your AI assistant for emotional support and guidance.",
	})


@login_required
def patient_profile(request):
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	
	# Handle profile update
	if request.method == "POST":
		user = request.user
		user.full_name = request.POST.get("full_name", user.full_name).strip()
		user.phone = request.POST.get("phone", user.phone).strip()
		user.bio = request.POST.get("bio", user.bio).strip()
		if request.FILES.get("profile_image"):
			user.profile_image = request.FILES["profile_image"]
		user.save()
		messages.success(request, "Profile updated successfully!")
		return redirect("accounts:patient_profile")
	
	# Get all MCQ results for assessment history
	mcq_results = PatientMCQResult.objects.filter(user=request.user).order_by("-completed_at")
	latest_mcq = mcq_results.first()
	
	# Get appointment statistics
	all_apts = Appointment.objects.filter(patient=request.user)
	completed_sessions = all_apts.filter(status="completed").count()
	upcoming_sessions = all_apts.filter(status="confirmed", date_time__gt=timezone.now()).count()
	
	# Get session reports for this patient (from completed appointments)
	session_reports = SessionReport.objects.filter(
		appointment__patient=request.user
	).select_related("appointment", "therapist").order_by("-created_at")
	
	# Get appointment history
	appointment_history = all_apts.order_by("-date_time")[:10]
	
	# Get unique therapists worked with
	therapist_ids = all_apts.filter(status="completed").values_list("therapist", flat=True).distinct()
	therapists_worked_with = User.objects.filter(pk__in=therapist_ids)
	
	# Calculate progress data for charts (mood and progress ratings over time)
	mood_data = list(session_reports.values_list("mood_rating", flat=True).order_by("created_at"))
	progress_data = list(session_reports.values_list("progress_rating", flat=True).order_by("created_at"))
	
	# Average ratings
	from django.db.models import Avg
	avg_mood = session_reports.aggregate(Avg("mood_rating"))["mood_rating__avg"]
	avg_progress = session_reports.aggregate(Avg("progress_rating"))["progress_rating__avg"]
	
	context = {
		"mcq_results": mcq_results,
		"latest_mcq": latest_mcq,
		"completed_sessions": completed_sessions,
		"upcoming_sessions": upcoming_sessions,
		"session_reports": session_reports,
		"appointment_history": appointment_history,
		"therapists_worked_with": therapists_worked_with,
		"mood_data": mood_data,
		"progress_data": progress_data,
		"avg_mood": round(avg_mood, 1) if avg_mood else None,
		"avg_progress": round(avg_progress, 1) if avg_progress else None,
		"unread_notifications": _unread(request.user),
	}
	
	# Get activity logs for profile
	all_activities = ActivityLog.objects.filter(user=request.user)
	tasks_completed = all_activities.filter(activity_type="task").count()
	challenges_accepted = all_activities.filter(activity_type="challenge").count()
	mood_checkins = all_activities.filter(activity_type="mood")
	total_points = all_activities.aggregate(total=Sum("points"))["total"] or 0
	activity_logs = all_activities.order_by("-created_at")[:50]
	
	context["activity_logs"] = activity_logs
	context["tasks_completed"] = tasks_completed
	context["challenges_accepted"] = challenges_accepted
	context["mood_checkins"] = mood_checkins
	context["total_points"] = total_points
	
	return render(request, "patient/patient_profile.html", context)


@login_required
def log_activity(request):
	"""AJAX endpoint to log patient activities (tasks, challenges, mood)."""
	import json
	from django.http import JsonResponse
	from .models import ActivityLog
	
	if request.method != "POST":
		return JsonResponse({"error": "POST required"}, status=405)
	
	if request.user.groups.filter(name="doctor").exists():
		return JsonResponse({"error": "Not authorized"}, status=403)
	
	try:
		data = json.loads(request.body)
		activity_type = data.get("activity_type")
		title = data.get("title", "")
		description = data.get("description", "")
		mood = data.get("mood", "")
		points = data.get("points", 0)
		
		if activity_type not in ["task", "challenge", "mood"]:
			return JsonResponse({"error": "Invalid activity type"}, status=400)
		
		activity = ActivityLog.objects.create(
			user=request.user,
			activity_type=activity_type,
			title=title,
			description=description,
			mood=mood,
			points=points,
		)
		
		return JsonResponse({
			"success": True,
			"activity_id": activity.id,
			"message": "Activity logged successfully"
		})
	except json.JSONDecodeError:
		return JsonResponse({"error": "Invalid JSON"}, status=400)
	except Exception as e:
		return JsonResponse({"error": str(e)}, status=500)


# ─── therapist dashboard ───────────────────────────────────────────────────
@login_required
def doctor_dashboard(request):
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	now = timezone.now()
	today_start = now.replace(hour=0, minute=0, second=0)
	today_end = now.replace(hour=23, minute=59, second=59)

	all_apts = Appointment.objects.filter(therapist=request.user)
	today_apts = all_apts.filter(date_time__range=[today_start, today_end], status="confirmed")
	upcoming_apts = all_apts.filter(date_time__gt=now, status="confirmed").order_by("date_time")[:5]
	pending_requests = all_apts.filter(status="requested").count()
	total_patients = all_apts.values("patient").distinct().count()
	completed_sessions = all_apts.filter(status="completed").count()
	reports_count = SessionReport.objects.filter(therapist=request.user).count()

	context = {
		"unread_notifications": _unread(request.user),
		"unread_messages": _unread_msgs(request.user),
		"today_appointments": today_apts,
		"upcoming_appointments": upcoming_apts,
		"pending_requests": pending_requests,
		"total_patients": total_patients,
		"completed_sessions": completed_sessions,
		"reports_count": reports_count,
	}
	return render(request, "therapist/therapist_dashboard.html", context)


@login_required
def therapist_appointments(request):
	"""Therapist appointment management."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	now = timezone.now()
	all_apts = Appointment.objects.filter(therapist=request.user)

	upcoming = all_apts.filter(date_time__gt=now, status="confirmed").order_by("date_time")
	past = all_apts.filter(status="completed").order_by("-date_time")
	missed = all_apts.filter(date_time__lt=now, status__in=["requested", "confirmed"]).order_by("-date_time")
	requested = all_apts.filter(status="requested").order_by("-created_at")
	cancelled = all_apts.filter(status__in=["cancelled", "rescheduled"]).order_by("-updated_at")

	context = {
		"upcoming_appointments": upcoming,
		"past_appointments": past,
		"missed_appointments": missed,
		"requested_appointments": requested,
		"cancelled_appointments": cancelled,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/therapist_appointments.html", context)


@login_required
def confirm_appointment(request, appointment_id):
	"""Therapist confirms a requested appointment."""
	apt = get_object_or_404(Appointment, pk=appointment_id, therapist=request.user)
	if apt.status != "requested":
		messages.error(request, "This appointment cannot be confirmed.")
		return redirect("accounts:therapist_appointments")

	apt.status = "confirmed"
	apt.save()
	_notify(
		apt.patient, "appointment_confirmed",
		"Appointment Confirmed",
		f"Your appointment with {request.user.full_name} on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')} has been confirmed!",
		apt,
		"/dashboard/patient/appointments/"
	)
	messages.success(request, "Appointment confirmed.")
	return redirect("accounts:therapist_appointments")


@login_required
def reject_appointment(request, appointment_id):
	"""Therapist rejects a requested appointment."""
	apt = get_object_or_404(Appointment, pk=appointment_id, therapist=request.user)
	if apt.status != "requested":
		messages.error(request, "This appointment cannot be rejected.")
		return redirect("accounts:therapist_appointments")

	reason = request.POST.get("rejection_reason", "") if request.method == "POST" else ""
	apt.status = "rejected"
	apt.cancellation_reason = reason
	apt.save()
	_notify(
		apt.patient, "appointment_rejected",
		"Appointment Request Declined",
		f"Your appointment request with {request.user.full_name} on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')} was declined. {('Reason: ' + reason) if reason else 'Please try another time.'}",
		apt,
		"/dashboard/patient/appointments/"
	)
	messages.success(request, "Appointment request declined.")
	return redirect("accounts:therapist_appointments")


@login_required
def complete_appointment(request, appointment_id):
	"""Therapist marks appointment as completed."""
	apt = get_object_or_404(Appointment, pk=appointment_id, therapist=request.user)
	apt.status = "completed"
	apt.save()
	messages.success(request, "Session marked as completed.")
	return redirect("accounts:therapist_appointments")


# ─── session reports ────────────────────────────────────────────────────────
@login_required
def session_reports(request):
	"""Therapist views all session reports."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	reports = SessionReport.objects.filter(therapist=request.user).select_related("appointment__patient")
	context = {
		"reports": reports,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/session_reports.html", context)


@login_required
def create_session_report(request, appointment_id):
	"""Therapist creates / uploads a session report."""
	apt = get_object_or_404(Appointment, pk=appointment_id, therapist=request.user)
	if hasattr(apt, "report"):
		messages.info(request, "Report already exists for this session. Editing…")
		return redirect("accounts:edit_session_report", report_id=apt.report.pk)

	if request.method == "POST":
		report = SessionReport.objects.create(
			appointment=apt,
			therapist=request.user,
			summary=request.POST.get("summary", ""),
			diagnosis_notes=request.POST.get("diagnosis_notes", ""),
			treatment_plan=request.POST.get("treatment_plan", ""),
			mood_rating=int(request.POST.get("mood_rating", 5)),
			progress_rating=int(request.POST.get("progress_rating", 5)),
			homework=request.POST.get("homework", ""),
			private_notes=request.POST.get("private_notes", ""),
		)
		if request.FILES.get("attachment"):
			report.attachment = request.FILES["attachment"]
			report.save()

		_notify(
			apt.patient, "report_uploaded",
			"Session Report Available",
			f"A session report for your appointment on {apt.date_time.strftime('%b %d, %Y')} is now available.",
			apt,
			"/dashboard/patient/profile/"
		)
		messages.success(request, "Session report created.")
		return redirect("accounts:session_reports")

	context = {
		"appointment": apt,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/create_report.html", context)


@login_required
def edit_session_report(request, report_id):
	report = get_object_or_404(SessionReport, pk=report_id, therapist=request.user)

	if request.method == "POST":
		report.summary = request.POST.get("summary", report.summary)
		report.diagnosis_notes = request.POST.get("diagnosis_notes", report.diagnosis_notes)
		report.treatment_plan = request.POST.get("treatment_plan", report.treatment_plan)
		report.mood_rating = int(request.POST.get("mood_rating", report.mood_rating))
		report.progress_rating = int(request.POST.get("progress_rating", report.progress_rating))
		report.homework = request.POST.get("homework", report.homework)
		report.private_notes = request.POST.get("private_notes", report.private_notes)
		if request.FILES.get("attachment"):
			report.attachment = request.FILES["attachment"]
		report.save()
		messages.success(request, "Report updated.")
		return redirect("accounts:session_reports")

	context = {
		"report": report,
		"appointment": report.appointment,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/create_report.html", context)


@login_required
def view_session_report(request, report_id):
	"""Both patient and therapist can view a report."""
	report = get_object_or_404(SessionReport, pk=report_id)
	apt = report.appointment
	if request.user not in (apt.patient, apt.therapist):
		messages.error(request, "Unauthorized.")
		return redirect("accounts:dashboard_redirect")

	context = {
		"report": report,
		"appointment": apt,
		"is_therapist": request.user == apt.therapist,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/view_report.html", context)


# ─── client profiles & progress (therapist) ────────────────────────────────
@login_required
def client_list(request):
	"""Therapist views all their clients."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	client_ids = Appointment.objects.filter(
		therapist=request.user,
		status__in=["confirmed", "completed"]
	).values_list("patient", flat=True).distinct()
	clients = User.objects.filter(pk__in=client_ids)

	client_data = []
	for client in clients:
		apts = Appointment.objects.filter(patient=client, therapist=request.user)
		completed = apts.filter(status="completed").count()
		upcoming = apts.filter(date_time__gt=timezone.now(), status="confirmed").count()
		reports = SessionReport.objects.filter(appointment__patient=client, therapist=request.user)
		avg_mood = reports.aggregate(Avg("mood_rating"))["mood_rating__avg"]
		avg_progress = reports.aggregate(Avg("progress_rating"))["progress_rating__avg"]
		mcq = PatientMCQResult.objects.filter(user=client).first()

		client_data.append({
			"user": client,
			"completed_sessions": completed,
			"upcoming_sessions": upcoming,
			"total_sessions": apts.count(),
			"avg_mood": round(avg_mood, 1) if avg_mood else "N/A",
			"avg_progress": round(avg_progress, 1) if avg_progress else "N/A",
			"category": mcq.get_category_display() if mcq else "Not assessed",
		})

	context = {
		"clients": client_data,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/client_list.html", context)


@login_required
def client_profile(request, client_id):
	"""Therapist views a specific client's profile & progress."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	client = get_object_or_404(User, pk=client_id)
	apts = Appointment.objects.filter(patient=client, therapist=request.user).order_by("-date_time")
	reports = SessionReport.objects.filter(
		appointment__patient=client, therapist=request.user
	).order_by("-created_at")
	mcq = PatientMCQResult.objects.filter(user=client).first()

	mood_data = list(reports.values_list("mood_rating", flat=True))
	progress_data = list(reports.values_list("progress_rating", flat=True))

	context = {
		"client": client,
		"appointments": apts,
		"reports": reports,
		"mcq": mcq,
		"mood_data": json.dumps(mood_data[::-1]),
		"progress_data": json.dumps(progress_data[::-1]),
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/client_profile.html", context)


# ─── secure messaging ──────────────────────────────────────────────────────
@login_required
def inbox(request):
	"""Show conversations — grouped by the other party."""
	user = request.user
	all_msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user))
	partner_ids = set()
	partner_ids.update(all_msgs.values_list("sender", flat=True))
	partner_ids.update(all_msgs.values_list("receiver", flat=True))
	partner_ids.discard(user.pk)

	conversations = []
	for pid in partner_ids:
		partner = User.objects.get(pk=pid)
		last_msg = all_msgs.filter(
			Q(sender=partner, receiver=user) | Q(sender=user, receiver=partner)
		).order_by("-created_at").first()
		unread = Message.objects.filter(sender=partner, receiver=user, is_read=False).count()
		conversations.append({
			"partner": partner,
			"last_message": last_msg,
			"unread": unread,
		})
	conversations.sort(key=lambda c: c["last_message"].created_at if c["last_message"] else timezone.now(), reverse=True)

	context = {
		"conversations": conversations,
		"unread_notifications": _unread(user),
	}
	return render(request, "messaging/inbox.html", context)


@login_required
def conversation(request, partner_id):
	"""Chat thread between two users."""
	partner = get_object_or_404(User, pk=partner_id)
	user = request.user

	if request.method == "POST":
		content = request.POST.get("content", "").strip()
		if content:
			msg = Message.objects.create(sender=user, receiver=partner, content=content)
			if request.FILES.get("attachment"):
				msg.attachment = request.FILES["attachment"]
				msg.save()
			_notify(
				partner, "message",
				f"New message from {user.full_name}",
				content[:100],
				None,
				f"/messages/{user.pk}/"
			)
		return redirect("accounts:conversation", partner_id=partner_id)

	msgs = Message.objects.filter(
		Q(sender=user, receiver=partner) | Q(sender=partner, receiver=user)
	).order_by("created_at")
	# Mark received messages as read
	msgs.filter(receiver=user, is_read=False).update(is_read=True)

	context = {
		"partner": partner,
		"messages_list": msgs,
		"unread_notifications": _unread(user),
	}
	return render(request, "messaging/conversation.html", context)


# ─── therapist availability ────────────────────────────────────────────────
@login_required
def manage_availability(request):
	"""Therapist manages their weekly availability — multiple slots per day + days off."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	if request.method == "POST":
		action = request.POST.get("action", "save_slots")

		if action == "save_slots":
			# Clear existing and re-create from dynamic form
			TherapistAvailability.objects.filter(therapist=request.user).delete()

			# Each slot is sent as slot_day_X, slot_start_X, slot_end_X
			slot_index = 0
			while True:
				day = request.POST.get(f"slot_day_{slot_index}")
				start = request.POST.get(f"slot_start_{slot_index}")
				end = request.POST.get(f"slot_end_{slot_index}")
				if day is None:
					break
				if start and end:
					TherapistAvailability.objects.create(
						therapist=request.user,
						day_of_week=int(day),
						start_time=start,
						end_time=end,
					)
				slot_index += 1
			messages.success(request, "Availability updated.")

		elif action == "add_day_off":
			day_off_date = request.POST.get("day_off_date")
			day_off_reason = request.POST.get("day_off_reason", "")
			if day_off_date:
				from datetime import datetime as dt
				date_obj = dt.strptime(day_off_date, "%Y-%m-%d").date()
				TherapistDayOff.objects.get_or_create(
					therapist=request.user, date=date_obj,
					defaults={"reason": day_off_reason}
				)
				messages.success(request, f"Day off added for {date_obj.strftime('%b %d, %Y')}.")

		elif action == "remove_day_off":
			day_off_id = request.POST.get("day_off_id")
			TherapistDayOff.objects.filter(pk=day_off_id, therapist=request.user).delete()
			messages.success(request, "Day off removed.")

		return redirect("accounts:manage_availability")

	slots = TherapistAvailability.objects.filter(therapist=request.user)
	days_off = TherapistDayOff.objects.filter(therapist=request.user, date__gte=date.today())

	# Group slots by day for template display
	from collections import defaultdict
	grouped = defaultdict(list)
	for s in slots:
		grouped[s.day_of_week].append(s)

	context = {
		"slots": slots,
		"grouped_slots": dict(grouped),
		"day_choices": TherapistAvailability.DAY_CHOICES,
		"days_off": days_off,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "therapist/manage_availability.html", context)


# ─── therapist profile ──────────────────────────────────────────────────────
@login_required
def therapist_profile(request):
	"""Therapist profile page — view and edit account details."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	user = request.user

	if request.method == "POST":
		user.full_name = request.POST.get("full_name", user.full_name).strip()
		user.phone = request.POST.get("phone", user.phone).strip()
		user.bio = request.POST.get("bio", user.bio).strip()
		user.specialization = request.POST.get("specialization", user.specialization)
		if request.FILES.get("profile_image"):
			user.profile_image = request.FILES["profile_image"]
		user.save()
		messages.success(request, "Profile updated successfully!")
		return redirect("accounts:therapist_profile")

	context = {
		"unread_notifications": _unread(user),
		"specialization_choices": User.SPECIALIZATION_CHOICES,
	}
	return render(request, "therapist/therapist_profile.html", context)


# ─── notifications ──────────────────────────────────────────────────────────
@login_required
def notifications_view(request):
	notifications = Notification.objects.filter(user=request.user)
	unread_count = notifications.filter(is_read=False).count()
	
	# Auto-mark all notifications as read when page is viewed
	if unread_count > 0:
		notifications.filter(is_read=False).update(is_read=True)

	context = {
		"notifications": notifications,
		"unread_count": 0,  # Already marked as read
	}
	return render(request, "notifications.html", context)


# ─── therapist rating ──────────────────────────────────────────────────────
@login_required
def rate_therapist(request, appointment_id):
	"""Patient rates therapist after a completed appointment."""
	if request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:doctor_dashboard")
	
	apt = get_object_or_404(Appointment, pk=appointment_id, patient=request.user)
	
	# Check if already rated
	if hasattr(apt, "rating"):
		messages.info(request, "You've already rated this session.")
		return redirect("accounts:patient_appointments")
	
	# Only allow rating completed appointments
	if apt.status != "completed":
		messages.error(request, "You can only rate completed sessions.")
		return redirect("accounts:patient_appointments")
	
	if request.method == "POST":
		rating = int(request.POST.get("rating", 5))
		review = request.POST.get("review", "").strip()
		
		TherapistRating.objects.create(
			patient=request.user,
			therapist=apt.therapist,
			appointment=apt,
			rating=rating,
			review=review,
		)
		messages.success(request, "Thank you for your feedback!")
		return redirect("accounts:patient_appointments")
	
	context = {
		"appointment": apt,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/rate_therapist.html", context)


# ─── video tracking ────────────────────────────────────────────────────────
@login_required
@csrf_exempt
def track_video_watch(request):
	"""Track video watch for personalized recommendations."""
	if request.method == 'POST':
		try:
			data = json.loads(request.body)
			video_id = data.get('video_id')
			video_title = data.get('video_title', '')
			category = data.get('category', 'general')
			video_source = data.get('video_source', 'youtube')
			
			from .models import VideoWatchHistory
			VideoWatchHistory.objects.create(
				user=request.user,
				video_id=video_id,
				video_title=video_title,
				category=category,
				video_source=video_source
			)
			
			return JsonResponse({'status': 'success'})
		except Exception as e:
			return JsonResponse({'status': 'error', 'message': str(e)})
	
	return JsonResponse({'status': 'error', 'message': 'Invalid request method'})