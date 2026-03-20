import json
import random
import os
from datetime import timedelta, datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from .models import VideoWatchHistory
from .youtube_service import get_youtube_videos
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings as django_settings
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count, Avg, Sum
import requests
import uuid
import hmac
import hashlib
import base64

from .models import (
	PatientMCQResult, Appointment, Notification,
	TherapistAvailability, TherapistDayOff, SessionReport, Message,
	Resource, GuidedExercise, ActivityLog, TherapistRating,
	VideoWatchHistory, SearchHistory, TherapySession, SessionMessage,
	ChatSession, ChatMessage,
)

load_dotenv()
HF_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
HF_MODEL_URL = "https://api-inference.huggingface.co/models/ShenLab/MentalChat16K"

headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}


User = get_user_model()

MOOD_SCORE_MAP = {
	"great": 5,
	"good": 4,
	"okay": 3,
	"low": 2,
	"struggling": 1,
}

TASK_SUGGESTIONS_BY_CATEGORY = {
	"anxiety": [
		"Do 5 minutes of deep breathing exercises",
		"Write down 3 things you're grateful for",
		"Take a 10-minute walk without your phone",
		"Practice 5-4-3-2-1 grounding for 3 minutes",
		"Stretch your shoulders and jaw for 5 minutes",
	],
	"depression": [
		"Open the curtains and let sunlight in",
		"Send a message to someone you care about",
		"Do one small productive task (make bed, wash dishes)",
		"Play one uplifting song and listen mindfully",
		"Write one kind sentence to yourself",
	],
	"stress": [
		"Write your top 3 priorities for today",
		"Take a 15-minute break without screens",
		"Say 'no' to one non-essential request",
		"Do a 4-4-6 breathing cycle five times",
		"Declutter one small area for 10 minutes",
	],
	"ptsd": [
		"Practice your safe space visualization for 5 min",
		"Ground yourself: feel your feet on the floor",
		"Write in your journal for 10 minutes",
		"Name 3 safe people you can reach out to",
		"Hold a calming object and focus on your senses",
	],
	"general": [
		"Drink 8 glasses of water today",
		"Get at least 7 hours of sleep tonight",
		"Do something that makes you smile",
		"Spend 10 minutes away from social media",
		"Take a short walk after a meal",
	],
}

CHALLENGE_SUGGESTIONS_BY_CATEGORY = {
	"anxiety": [
		{"emoji": "🧘", "title": "Complete a 10-min meditation without checking your phone", "points": 50, "label": "Calm Points"},
		{"emoji": "🌿", "title": "Spend 20 minutes in nature today", "points": 30, "label": "Peace Points"},
		{"emoji": "📝", "title": "Write down 5 anxious thoughts and reframe them", "points": 40, "label": "Resilience Points"},
	],
	"depression": [
		{"emoji": "🎨", "title": "Create something today - draw, write, or craft", "points": 50, "label": "Joy Points"},
		{"emoji": "🤝", "title": "Have a real conversation with someone face-to-face", "points": 40, "label": "Connection Points"},
		{"emoji": "🌅", "title": "Watch sunrise or sunset without distractions", "points": 35, "label": "Hope Points"},
	],
	"stress": [
		{"emoji": "📵", "title": "Go 1 hour without checking work emails", "points": 40, "label": "Balance Points"},
		{"emoji": "😂", "title": "Watch something funny and laugh out loud", "points": 30, "label": "Relief Points"},
		{"emoji": "🧩", "title": "Do a 15-minute offline hobby", "points": 35, "label": "Reset Points"},
	],
	"ptsd": [
		{"emoji": "🎧", "title": "Listen to calming music for 15 minutes", "points": 40, "label": "Serenity Points"},
		{"emoji": "✍️", "title": "Write a letter to your future self", "points": 50, "label": "Hope Points"},
		{"emoji": "🕯️", "title": "Create a comfort ritual for bedtime", "points": 35, "label": "Safety Points"},
	],
	"general": [
		{"emoji": "🏃", "title": "Get moving - 20 min of any physical activity", "points": 40, "label": "Energy Points"},
		{"emoji": "📚", "title": "Read for 15 minutes before bed", "points": 30, "label": "Wellness Points"},
		{"emoji": "🍲", "title": "Prepare one nourishing meal today", "points": 35, "label": "Care Points"},
	],
}

DURATION_PRICING = {
	30: 100,
	60: 200,
	90: 300,
}


def _session_fee(duration_minutes):
	return DURATION_PRICING.get(duration_minutes, 200)


def _daily_rotation(items, count, seed_value):
	if not items:
		return []
	if len(items) <= count:
		return items[:]
	start = seed_value % len(items)
	rotated = items[start:] + items[:start]
	return rotated[:count]


def _build_mood_trend_data(user):
	today = date.today()
	mood_logs = ActivityLog.objects.filter(
		user=user,
		activity_type="mood",
	).order_by("date", "created_at")

	latest_mood_by_day = {}
	for entry in mood_logs:
		latest_mood_by_day[entry.date] = entry.mood

	weekly_labels = []
	weekly_scores = []
	for offset in range(6, -1, -1):
		d = today - timedelta(days=offset)
		weekly_labels.append(d.strftime("%a"))
		mood_key = latest_mood_by_day.get(d)
		weekly_scores.append(MOOD_SCORE_MAP.get(mood_key) if mood_key else None)

	monthly_labels = []
	monthly_scores = []
	for offset in range(29, -1, -1):
		d = today - timedelta(days=offset)
		monthly_labels.append(d.strftime("%d %b"))
		mood_key = latest_mood_by_day.get(d)
		monthly_scores.append(MOOD_SCORE_MAP.get(mood_key) if mood_key else None)

	improvement_labels = []
	improvement_scores = []
	current_week_start = today - timedelta(days=today.weekday())
	for week_index in range(11, -1, -1):
		week_start = current_week_start - timedelta(weeks=week_index)
		week_values = []
		for day_offset in range(7):
			week_day = week_start + timedelta(days=day_offset)
			mood_key = latest_mood_by_day.get(week_day)
			if mood_key:
				week_values.append(MOOD_SCORE_MAP.get(mood_key, 0))
		improvement_labels.append(week_start.strftime("%d %b"))
		if week_values:
			improvement_scores.append(round(sum(week_values) / len(week_values), 2))
		else:
			improvement_scores.append(None)

	return {
		"weekly_labels": weekly_labels,
		"weekly_scores": weekly_scores,
		"monthly_labels": monthly_labels,
		"monthly_scores": monthly_scores,
		"improvement_labels": improvement_labels,
		"improvement_scores": improvement_scores,
		"mood_days_logged": sum(1 for value in monthly_scores if value is not None),
	}


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


def contact_us(request):
	if request.method == "POST":
		name = request.POST.get("name", "").strip()
		email = request.POST.get("email", "").strip()
		subject_choice = request.POST.get("subject", "General Inquiry").strip()
		message_body = request.POST.get("message", "").strip()

		if not name or not email or not message_body:
			return JsonResponse({"ok": False, "error": "Please fill in all required fields."}, status=400)

		try:
			validate_email(email)
		except ValidationError:
			return JsonResponse({"ok": False, "error": "Please enter a valid email address."}, status=400)

		email_subject = f"[ReNova Contact] {subject_choice} — from {name}"
		email_body = (
			f"New contact message from the ReNova website.\n\n"
			f"Name:    {name}\n"
			f"Email:   {email}\n"
			f"Subject: {subject_choice}\n\n"
			f"Message:\n{message_body}\n"
		)

		try:
			msg = EmailMessage(
				subject=email_subject,
				body=email_body,
				from_email=django_settings.DEFAULT_FROM_EMAIL,
				to=[django_settings.CONTACT_EMAIL],
				reply_to=[f"{name} <{email}>"],
			)
			msg.send(fail_silently=False)
		except Exception:
			return JsonResponse({"ok": False, "error": "Failed to send message. Please try again later."}, status=500)

		return JsonResponse({"ok": True})

	return redirect("accounts:home")


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
				user.backend = 'django.contrib.auth.backends.ModelBackend'
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
	today_activities = ActivityLog.objects.filter(user=request.user, date=today, completed=True)
	today_tasks = list(today_activities.filter(activity_type="task").values_list("title", flat=True))
	today_challenges = list(today_activities.filter(activity_type="challenge").values_list("title", flat=True))
	today_mood = today_activities.filter(activity_type="mood").order_by("-created_at").first()
	today_mood_value = today_mood.mood if today_mood else ""

	# Build daily activity sets that refresh on the next day rather than immediately.
	task_pool = TASK_SUGGESTIONS_BY_CATEGORY.get(mcq.category, TASK_SUGGESTIONS_BY_CATEGORY["general"])
	challenge_pool = CHALLENGE_SUGGESTIONS_BY_CATEGORY.get(mcq.category, CHALLENGE_SUGGESTIONS_BY_CATEGORY["general"])
	rotation_seed = today.toordinal() + sum(ord(ch) for ch in mcq.category)
	active_tasks = _daily_rotation(task_pool, 3, rotation_seed)
	active_challenges = _daily_rotation(challenge_pool, 2, rotation_seed + 7)

	remaining_task = next((task for task in active_tasks if task not in today_tasks), None)
	remaining_challenge = next((challenge["title"] for challenge in active_challenges if challenge["title"] not in today_challenges), None)
	today_activity_text = remaining_task or remaining_challenge or "Today's activities are complete. New suggestions will appear tomorrow."

	quick_resources = Resource.objects.filter(
		Q(category=mcq.category) | Q(category="general")
	).order_by("order", "-is_featured", "-created_at")[:3]
	
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
		"today_activity_text": today_activity_text,
		"task_pool": json.dumps(task_pool),
		"active_tasks": json.dumps(active_tasks),
		"challenge_pool": json.dumps(challenge_pool),
		"active_challenges": json.dumps(active_challenges),
		"today_tasks": json.dumps(today_tasks),
		"today_challenges": json.dumps(today_challenges),
		"today_mood": today_mood_value,
		"quick_resources": quick_resources,
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
		"session_pricing": DURATION_PRICING,
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
		if duration not in {30, 60, 90}:
			duration = 60
		patient_notes = request.POST.get("patient_notes", "")
		session_type = request.POST.get("session_type", "text_chat")
		valid_types = {"text_chat", "audio_call", "video_call"}
		if session_type not in valid_types:
			session_type = "text_chat"

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
			session_type=session_type,
			fee_amount=_session_fee(duration),
			payment_status="pending",
			refund_status="none",
		)
		messages.info(request, "Appointment slot reserved. Please complete eSewa payment to send your request to the therapist.")
		return redirect("accounts:esewa_payment", appointment_id=apt.pk)

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
		"session_pricing": DURATION_PRICING,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/book_appointment.html", context)


@login_required
def esewa_payment(request, appointment_id):
	"""Simple eSewa checkout simulation page for an appointment."""
	apt = get_object_or_404(Appointment, pk=appointment_id, patient=request.user)
	if apt.status not in ["requested", "confirmed"]:
		messages.error(request, "This appointment can no longer be paid.")
		return redirect("accounts:patient_appointments")

	if apt.payment_status == "paid":
		messages.info(request, "Payment already completed for this appointment.")
		return redirect("accounts:patient_appointments")

	context = {
		"appointment": apt,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/esewa_payment.html", context)


@login_required
def esewa_payment_success(request, appointment_id):
	"""Marks appointment payment as paid and sends request to therapist."""
	apt = get_object_or_404(Appointment, pk=appointment_id, patient=request.user)
	if apt.payment_status == "paid":
		messages.info(request, "Payment already completed.")
		return redirect("accounts:patient_appointments")

	if apt.status not in ["requested", "confirmed"]:
		messages.error(request, "This appointment is no longer payable.")
		return redirect("accounts:patient_appointments")

	apt.payment_status = "paid"
	apt.paid_at = timezone.now()
	apt.payment_method = "esewa"
	apt.payment_reference = f"ESEWA-{apt.pk}-{int(timezone.now().timestamp())}"
	apt.save(update_fields=["payment_status", "paid_at", "payment_method", "payment_reference", "updated_at"])

	_notify(
		apt.therapist, "appointment_requested",
		"New Paid Appointment Request",
		f"{request.user.full_name} paid NPR {apt.fee_amount} via eSewa and requested an appointment on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')}.",
		apt,
		"/dashboard/therapist/appointments/"
	)
	messages.success(request, "Payment successful. Your request is now waiting for therapist approval.")
	return redirect("accounts:patient_appointments")


@login_required
def esewa_payment_failed(request, appointment_id):
	"""Handles failed or cancelled eSewa checkout attempt."""
	apt = get_object_or_404(Appointment, pk=appointment_id, patient=request.user)
	messages.warning(request, "Payment was not completed. You can retry eSewa payment from your appointments page.")
	return redirect("accounts:patient_appointments")


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

		# Refund policy:
		# - Patient cancellation > 24h before session: refund.
		# - Patient cancellation within 24h / no-show: no refund.
		# - Therapist-side cancellation: refund paid amount.
		if apt.payment_status == "paid":
			now = timezone.now()
			hours_left = (apt.date_time - now).total_seconds() / 3600
			if request.user == apt.therapist:
				apt.payment_status = "refunded"
				apt.refund_status = "refunded"
				apt.refunded_at = now
			elif hours_left > 24:
				apt.payment_status = "refunded"
				apt.refund_status = "refunded"
				apt.refunded_at = now
			else:
				apt.refund_status = "not_eligible"
		elif apt.payment_status == "pending":
			apt.refund_status = "none"

		apt.save()
		# Notify the other party
		other = apt.therapist if request.user == apt.patient else apt.patient
		redirect_path = "/dashboard/patient/appointments/" if other.role == "patient" else "/dashboard/therapist/appointments/"
		refund_text = ""
		if apt.refund_status == "refunded":
			refund_text = f" Payment refund of NPR {apt.fee_amount} has been initiated."
		elif apt.refund_status == "not_eligible":
			refund_text = " Refund is not eligible because cancellation happened within 24 hours of the appointment time."
		_notify(
			other, "appointment_cancelled",
			"Appointment Cancelled",
			f"Your appointment on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')} has been cancelled by {request.user.full_name}. Reason: {reason or 'Not specified'}.{refund_text}",
			apt,
			redirect_path
		)
		if apt.refund_status == "refunded":
			messages.success(request, f"Appointment cancelled. Refund of NPR {apt.fee_amount} has been processed.")
		elif apt.refund_status == "not_eligible":
			messages.warning(request, "Appointment cancelled. Refund not allowed for cancellations within 24 hours.")
		else:
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
RESOURCE_SECTION_CONFIG = [
	{
		"slug": "recommended",
		"label": "Recommended",
		"icon": "🎯",
		"title": "Recommended For You",
		"description": "YouTube videos matched to your current wellness focus.",
		"tag": "Recommended",
		"gradient": "linear-gradient(135deg,#f0f4ff 0%,#e0ebff 100%)",
		"border": "rgba(74,144,226,0.15)",
		"accent": "#4a90e2",
		"query_template": "{category} mental wellness tips",
	},
	{
		"slug": "positive",
		"label": "Positive & Motivational",
		"icon": "✨",
		"title": "Positive & Motivational",
		"description": "Uplifting YouTube content to boost mood and confidence.",
		"tag": "Motivation",
		"gradient": "linear-gradient(135deg,#fff8f0 0%,#ffecdb 100%)",
		"border": "rgba(230,126,34,0.15)",
		"accent": "#e67e22",
		"query_template": "positive motivation mental health",
	},
	{
		"slug": "meditation",
		"label": "Meditation",
		"icon": "🧘",
		"title": "Guided Meditation",
		"description": "Mindfulness and calming meditation videos from YouTube.",
		"tag": "Meditation",
		"gradient": "linear-gradient(135deg,#e8f8f5 0%,#d4f3ea 100%)",
		"border": "rgba(39,174,96,0.12)",
		"accent": "#27ae60",
		"query_template": "guided meditation for {category}",
	},
	{
		"slug": "meditation_tutorial",
		"label": "Meditation Tutorial",
		"icon": "🎓",
		"title": "Learn Meditation",
		"description": "Beginner-friendly meditation tutorials and foundations.",
		"tag": "Tutorial",
		"gradient": "linear-gradient(135deg,#f8f9ff 0%,#e6edff 100%)",
		"border": "rgba(74,144,226,0.12)",
		"accent": "#5b7cfa",
		"query_template": "how to meditate for beginners",
	},
	{
		"slug": "yoga",
		"label": "Yoga",
		"icon": "🧘‍♂️",
		"title": "Yoga & Movement",
		"description": "Gentle yoga flows and body-based grounding practices.",
		"tag": "Yoga",
		"gradient": "linear-gradient(135deg,#fef7f0 0%,#fde8d7 100%)",
		"border": "rgba(233,30,99,0.12)",
		"accent": "#e91e63",
		"query_template": "yoga for mental health beginners",
	},
	{
		"slug": "yoga_tutorial",
		"label": "Yoga Tutorial",
		"icon": "🎯",
		"title": "Learn Yoga Fundamentals",
		"description": "Foundational yoga videos focused on technique and safe form.",
		"tag": "Tutorial",
		"gradient": "linear-gradient(135deg,#fff8f0 0%,#ffe8d0 100%)",
		"border": "rgba(233,30,99,0.12)",
		"accent": "#f39c12",
		"query_template": "yoga basics tutorial",
	},
	{
		"slug": "breathing",
		"label": "Breathing",
		"icon": "🌬️",
		"title": "Breathing Exercises",
		"description": "Quick breathing techniques for calm and stress reduction.",
		"tag": "Breathing",
		"gradient": "linear-gradient(135deg,#e3f2fd 0%,#bbdefb 100%)",
		"border": "rgba(33,150,243,0.15)",
		"accent": "#2196f3",
		"query_template": "breathing exercises for anxiety",
	},
	{
		"slug": "sleep",
		"label": "Sleep",
		"icon": "🌙",
		"title": "Sleep & Relaxation",
		"description": "Sleep meditations and calming wind-down sessions.",
		"tag": "Sleep",
		"gradient": "linear-gradient(135deg,#f3e5f5 0%,#e1bee7 100%)",
		"border": "rgba(156,39,176,0.15)",
		"accent": "#9c27b0",
		"query_template": "sleep meditation relaxing",
	},
	{
		"slug": "mindfulness",
		"label": "Mindfulness",
		"icon": "🌱",
		"title": "Mindfulness Practice",
		"description": "Daily awareness and grounding videos to stay present.",
		"tag": "Mindfulness",
		"gradient": "linear-gradient(135deg,#f0fdf4 0%,#dcfce7 100%)",
		"border": "rgba(34,197,94,0.15)",
		"accent": "#22c55e",
		"query_template": "mindfulness meditation practice",
	},
	{
		"slug": "stress_relief",
		"label": "Stress Relief",
		"icon": "🛡️",
		"title": "Stress Relief",
		"description": "Evidence-based techniques to lower pressure and reset.",
		"tag": "Stress Relief",
		"gradient": "linear-gradient(135deg,#fef3f2 0%,#fecaca 100%)",
		"border": "rgba(239,68,68,0.15)",
		"accent": "#ef4444",
		"query_template": "stress relief techniques",
	},
	{
		"slug": "anxiety_help",
		"label": "Anxiety Help",
		"icon": "🤝",
		"title": "Anxiety Support",
		"description": "Practical videos for understanding and reducing anxiety.",
		"tag": "Anxiety Help",
		"gradient": "linear-gradient(135deg,#f0f4ff 0%,#e0e7ff 100%)",
		"border": "rgba(99,102,241,0.15)",
		"accent": "#6366f1",
		"query_template": "how to reduce anxiety",
	},
	{
		"slug": "self_care",
		"label": "Self Care",
		"icon": "💝",
		"title": "Self-Care Essentials",
		"description": "Gentle, practical self-care resources for daily wellbeing.",
		"tag": "Self Care",
		"gradient": "linear-gradient(135deg,#fdf2f8 0%,#fbcfe8 100%)",
		"border": "rgba(236,72,153,0.15)",
		"accent": "#ec4899",
		"query_template": "self care for mental health",
	},
]


@login_required
def patient_resources(request):
	active_type = request.GET.get("type", "all")
	section_map = {section["slug"]: section for section in RESOURCE_SECTION_CONFIG}
	valid_types = set(section_map) | {"all"}
	if active_type not in valid_types:
		active_type = "all"

	mcq = PatientMCQResult.objects.filter(user=request.user).first()
	patient_category = mcq.category if mcq else "general"
	category_display = mcq.get_category_display() if mcq else "General Wellness"

	def build_query(section):
		category_text = category_display.lower()
		return section["query_template"].format(category=category_text)

	sections_to_fetch = RESOURCE_SECTION_CONFIG if active_type == "all" else [section_map[active_type]]
	videos_by_type = {section["slug"]: [] for section in RESOURCE_SECTION_CONFIG}

	max_workers = min(6, len(sections_to_fetch)) or 1
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		future_map = {
			executor.submit(get_youtube_videos, build_query(section)): section["slug"]
			for section in sections_to_fetch
		}
		for future in as_completed(future_map):
			slug = future_map[future]
			try:
				videos_by_type[slug] = future.result() or []
			except Exception:
				videos_by_type[slug] = []

	personalized_videos = []
	watch_history = VideoWatchHistory.objects.filter(user=request.user).order_by("-watched_at")[:1]
	if watch_history:
		last_category = (watch_history[0].category or patient_category).replace("_", " ")
		personalized_videos = get_youtube_videos(f"{last_category} mental health support")

	resource_sections = []
	for section in RESOURCE_SECTION_CONFIG:
		if active_type != "all" and section["slug"] != active_type:
			continue
		videos = videos_by_type.get(section["slug"], [])
		if not videos:
			continue
		resource_sections.append({
			**section,
			"videos": videos,
		})

	show_personalized = active_type in {"all", "recommended"} and bool(personalized_videos)
	has_visible_resources = bool(resource_sections) or show_personalized

	filter_options = [{"slug": "all", "label": "All", "icon": "📋"}] + [
		{
			"slug": section["slug"],
			"label": section["label"],
			"icon": section["icon"],
		}
		for section in RESOURCE_SECTION_CONFIG
	]

	context = {
		"active_type": active_type,
		"category_display": category_display,
		"filter_options": filter_options,
		"resource_sections": resource_sections,
		"personalized_videos": personalized_videos,
		"show_personalized": show_personalized,
		"has_visible_resources": has_visible_resources,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "patient/resources.html", context)

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@login_required
@csrf_exempt
def track_video_watch(request):

    if request.method == "POST":

        data = json.loads(request.body)

        VideoWatchHistory.objects.create(
            user=request.user,
            video_id=data.get("video_id"),
            video_title=data.get("video_title"),
            category=data.get("category"),
            video_source=data.get("video_source")
        )

        return JsonResponse({"status": "success"})


@login_required
def chatbot_page(request, session_id=None):
    if session_id:
        chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        chat_messages = chat_session.messages.all()
    else:
        chat_session = ChatSession.objects.create(user=request.user)
        chat_messages = []

    past_sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    unread_notifications = 0  # Replace with your notifications logic

    return render(request, "patient/ai_chatbot.html", {
        "chat_session": chat_session,
        "chat_messages": chat_messages,
        "past_sessions": past_sessions,
        "unread_notifications": unread_notifications,
    })

@csrf_exempt
@login_required
def chatbot_send(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    data = json.loads(request.body)
    session_id = data.get("session_id")
    message_text = data.get("message", "").strip()

    if not message_text:
        return JsonResponse({"error": "Message cannot be empty"}, status=400)

    chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    ChatMessage.objects.create(session=chat_session, role="user", content=message_text)

    payload = {"inputs": f"{message_text}"}
    response = requests.post(HF_MODEL_URL, headers=headers, json=payload)
    
    if response.status_code == 200:
        hf_data = response.json()
        reply = hf_data.get("generated_text") or "Sorry, I couldn't generate a response."
    else:
        reply = "Sorry, something went wrong with the AI service."

    ChatMessage.objects.create(session=chat_session, role="assistant", content=reply)
    return JsonResponse({"reply": reply, "session_id": chat_session.id})

@csrf_exempt
@login_required
def chatbot_new_session(request):
    chat_session = ChatSession.objects.create(user=request.user)
    return JsonResponse({"session_id": chat_session.id})


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
	mood_trends = _build_mood_trend_data(request.user)
	
	context = {
		"mcq_results": mcq_results,
		"latest_mcq": latest_mcq,
		"completed_sessions": completed_sessions,
		"upcoming_sessions": upcoming_sessions,
		"session_reports": session_reports,
		"patient_reports": session_reports,
		"appointment_history": appointment_history,
		"therapists_worked_with": therapists_worked_with,
		"mood_data": mood_data,
		"progress_data": progress_data,
		"avg_mood": round(avg_mood, 1) if avg_mood else None,
		"avg_progress": round(avg_progress, 1) if avg_progress else None,
		"weekly_labels": json.dumps(mood_trends["weekly_labels"]),
		"weekly_scores": json.dumps(mood_trends["weekly_scores"]),
		"monthly_labels": json.dumps(mood_trends["monthly_labels"]),
		"monthly_scores": json.dumps(mood_trends["monthly_scores"]),
		"improvement_labels": json.dumps(mood_trends["improvement_labels"]),
		"improvement_scores": json.dumps(mood_trends["improvement_scores"]),
		"mood_days_logged": mood_trends["mood_days_logged"],
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
		data = json.loads(request.body or "{}")
		activity_type = data.get("activity_type")
		title = data.get("title", "").strip()
		description = data.get("description", "")
		mood = data.get("mood", "").strip()
		points = int(data.get("points", 0) or 0)
		
		if activity_type not in ["task", "challenge", "mood"]:
			return JsonResponse({"error": "Invalid activity type"}, status=400)

		today = timezone.localdate()
		if activity_type == "mood":
			if mood not in MOOD_SCORE_MAP:
				return JsonResponse({"error": "Invalid mood"}, status=400)

			activity, created = ActivityLog.objects.update_or_create(
				user=request.user,
				activity_type="mood",
				date=today,
				defaults={
					"title": "Mood check-in",
					"description": description or "Daily mood tracking",
					"mood": mood,
					"points": max(points, 10),
					"completed": True,
				},
			)
		else:
			if not title:
				return JsonResponse({"error": "Title is required"}, status=400)

			activity, created = ActivityLog.objects.get_or_create(
				user=request.user,
				activity_type=activity_type,
				title=title,
				date=today,
				defaults={
					"description": description,
					"mood": "",
					"points": max(points, 0),
					"completed": True,
				},
			)

			if not created:
				changed = False
				if not activity.completed:
					activity.completed = True
					changed = True
				if points > activity.points:
					activity.points = points
					changed = True
				if changed:
					activity.save(update_fields=["completed", "points"])
		
		return JsonResponse({
			"success": True,
			"activity_id": activity.id,
			"created": created,
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

	month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
	if month_start.month == 12:
		next_month_start = month_start.replace(year=month_start.year + 1, month=1)
	else:
		next_month_start = month_start.replace(month=month_start.month + 1)

	month_eligible = all_apts.filter(
		status="completed",
		payment_status="paid",
		date_time__gte=month_start,
		date_time__lt=next_month_start,
	)
	month_earnings = month_eligible.aggregate(total=Sum("fee_amount"))["total"] or 0
	month_paid_out = all_apts.filter(
		therapist_payout_status="paid",
		therapist_paid_out_at__gte=month_start,
		therapist_paid_out_at__lt=next_month_start,
	).aggregate(total=Sum("fee_amount"))["total"] or 0
	pending_payout_amount = all_apts.filter(
		status="completed",
		payment_status="paid",
		therapist_payout_status="pending",
	).aggregate(total=Sum("fee_amount"))["total"] or 0

	context = {
		"unread_notifications": _unread(request.user),
		"unread_messages": _unread_msgs(request.user),
		"today_appointments": today_apts,
		"upcoming_appointments": upcoming_apts,
		"pending_requests": pending_requests,
		"total_patients": total_patients,
		"completed_sessions": completed_sessions,
		"reports_count": reports_count,
		"month_earnings": month_earnings,
		"month_paid_out": month_paid_out,
		"pending_payout_amount": pending_payout_amount,
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
	current_month_completed_paid = all_apts.filter(
		status="completed",
		payment_status="paid",
		date_time__year=now.year,
		date_time__month=now.month,
	).aggregate(total=Sum("fee_amount"))["total"] or 0
	pending_payout = all_apts.filter(
		status="completed",
		payment_status="paid",
		therapist_payout_status="pending",
	).aggregate(total=Sum("fee_amount"))["total"] or 0

	context = {
		"upcoming_appointments": upcoming,
		"past_appointments": past,
		"missed_appointments": missed,
		"requested_appointments": requested,
		"cancelled_appointments": cancelled,
		"current_month_completed_paid": current_month_completed_paid,
		"pending_payout": pending_payout,
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
	if apt.payment_status != "paid":
		messages.error(request, "This request cannot be approved until payment is completed.")
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
	if apt.payment_status == "paid":
		apt.payment_status = "refunded"
		apt.refund_status = "refunded"
		apt.refunded_at = timezone.now()
	apt.save()
	refund_line = f" A refund of NPR {apt.fee_amount} has been initiated via eSewa." if apt.refund_status == "refunded" else ""
	_notify(
		apt.patient, "appointment_rejected",
		"Appointment Request Declined",
		f"Your appointment request with {request.user.full_name} on {apt.date_time.strftime('%b %d, %Y at %I:%M %p')} was declined. {('Reason: ' + reason) if reason else 'Please try another time.'}{refund_line}",
		apt,
		"/dashboard/patient/appointments/"
	)
	if apt.refund_status == "refunded":
		messages.success(request, "Appointment request declined and payment refunded.")
	else:
		messages.success(request, "Appointment request declined.")
	return redirect("accounts:therapist_appointments")


@login_required
def complete_appointment(request, appointment_id):
	"""Therapist marks appointment as completed."""
	apt = get_object_or_404(Appointment, pk=appointment_id, therapist=request.user)
	if apt.payment_status != "paid":
		messages.error(request, "Only paid appointments can be marked as completed.")
		return redirect("accounts:therapist_appointments")
	apt.status = "completed"
	apt.therapist_payout_status = "pending"
	apt.save()
	messages.success(request, "Session marked as completed.")
	return redirect("accounts:therapist_appointments")


@login_required
def process_monthly_payout(request):
	"""Marks eligible completed sessions as paid out to therapist."""
	if not request.user.groups.filter(name="doctor").exists():
		return redirect("accounts:patient_dashboard")

	if request.method != "POST":
		return redirect("accounts:doctor_dashboard")

	now = timezone.now()
	paid_count = 0
	paid_total = 0
	eligible_qs = Appointment.objects.filter(
		therapist=request.user,
		status="completed",
		payment_status="paid",
		therapist_payout_status="pending",
	)
	for apt in eligible_qs:
		apt.therapist_payout_status = "paid"
		apt.therapist_paid_out_at = now
		apt.save(update_fields=["therapist_payout_status", "therapist_paid_out_at", "updated_at"])
		paid_count += 1
		paid_total += apt.fee_amount

	if paid_count:
		messages.success(request, f"Payout processed for {paid_count} session(s). Total NPR {paid_total}.")
	else:
		messages.info(request, "No eligible completed paid sessions for payout right now.")

	return redirect("accounts:doctor_dashboard")


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
@login_required
def track_video_watch(request):
	"""Track video watch for personalized recommendations."""
	if request.method == 'POST':
		try:
			data = json.loads(request.body)
			video_id = data.get('video_id')
			video_title = data.get('video_title', '')
			category = data.get('category', 'general')
			video_source = data.get('video_source', 'youtube')
			
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


# ─── online therapy session ─────────────────────────────────────────────────
@login_required
def session_room(request, appointment_id):
	"""Join or start an online therapy session room."""
	apt = get_object_or_404(Appointment, pk=appointment_id)

	if request.user not in (apt.patient, apt.therapist):
		messages.error(request, "You are not authorised to join this session.")
		return redirect("accounts:dashboard_redirect")

	if apt.status != "confirmed":
		messages.error(request, "Session is only available for confirmed appointments.")
		return redirect("accounts:dashboard_redirect")

	# Get or create the session room
	session, created = TherapySession.objects.get_or_create(
		appointment=apt,
		defaults={"is_active": True, "started_at": timezone.now()},
	)
	if not created and not session.is_active:
		session.is_active = True
		if not session.started_at:
			session.started_at = timezone.now()
		session.save(update_fields=["is_active", "started_at"])

	# Load last 100 chat messages
	previous_messages = SessionMessage.objects.filter(
		session=session
	).select_related("sender").order_by("created_at")[:100]

	other_user = apt.therapist if request.user == apt.patient else apt.patient

	context = {
		"appointment": apt,
		"session": session,
		"previous_messages": previous_messages,
		"room_code": str(session.room_code),
		"is_therapist": request.user.role == "therapist",
		"other_user": other_user,
		"current_user_id": request.user.id,
		"unread_notifications": _unread(request.user),
	}
	return render(request, "session/session_room.html", context)


@login_required
def end_session(request, appointment_id):
	"""End an active therapy session."""
	apt = get_object_or_404(Appointment, pk=appointment_id)

	if request.user not in (apt.patient, apt.therapist):
		messages.error(request, "Unauthorised.")
		return redirect("accounts:dashboard_redirect")

	try:
		session = apt.therapy_session
		session.is_active = False
		session.ended_at = timezone.now()
		session.save(update_fields=["is_active", "ended_at"])
	except TherapySession.DoesNotExist:
		pass

	if request.user.role == "therapist":
		return redirect("accounts:therapist_appointments")
	return redirect("accounts:patient_appointments")