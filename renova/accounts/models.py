from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class CustomUserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError("The Email field must be set")
		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, password=None, **extra_fields):
		extra_fields.setdefault("is_staff", True)
		extra_fields.setdefault("is_superuser", True)
		extra_fields.setdefault("is_active", True)
		extra_fields.setdefault("role", "admin")

		if extra_fields.get("is_staff") is not True:
			raise ValueError("Superuser must have is_staff=True.")
		if extra_fields.get("is_superuser") is not True:
			raise ValueError("Superuser must have is_superuser=True.")

		return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
	ROLE_CHOICES = [
		("patient", "Patient"),
		("therapist", "Therapist"),
		("admin", "Admin"),
	]

	SPECIALIZATION_CHOICES = [
		("", "None"),
		("anxiety", "Anxiety Disorders"),
		("depression", "Depression Treatment"),
		("stress", "Stress Management"),
		("ptsd", "Trauma & PTSD"),
		("general", "General Wellness"),
		("addiction", "Addiction Counseling"),
		("family", "Family Therapy"),
	]

	email = models.EmailField(unique=True)
	full_name = models.CharField(max_length=255)
	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="patient")
	specialization = models.CharField(
		max_length=30, choices=SPECIALIZATION_CHOICES, default="", blank=True,
		help_text="Therapist specialization (only for therapists)",
	)
	phone = models.CharField(max_length=20, blank=True, default="")
	bio = models.TextField(blank=True, default="", help_text="Short bio or about me")
	profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)
	terms_accepted = models.BooleanField(default=False)
	is_verified = models.BooleanField(default=False)
	is_approved = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)
	is_staff = models.BooleanField(default=False)
	date_joined = models.DateTimeField(default=timezone.now)

	objects = CustomUserManager()

	USERNAME_FIELD = "email"
	REQUIRED_FIELDS = ["full_name"]

	class Meta:
		verbose_name = "User"
		verbose_name_plural = "Users"

	def __str__(self):
		return self.email


class PatientMCQResult(models.Model):
	"""Stores the one-time MCQ assessment for each patient."""

	CATEGORY_CHOICES = [
		("anxiety", "Anxiety"),
		("depression", "Depression"),
		("stress", "Stress"),
		("ptsd", "Trauma & PTSD"),
		("general", "General Wellness"),
		("addiction", "Addiction"),
		("family", "Family Issues"),
	]

	user = models.OneToOneField(
		CustomUser, on_delete=models.CASCADE, related_name="mcq_result"
	)
	answers = models.JSONField(default=dict, help_text="Raw MCQ answers as JSON")
	category = models.CharField(
		max_length=30, choices=CATEGORY_CHOICES, default="general"
	)
	score = models.PositiveIntegerField(default=0)
	completed_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name = "Patient MCQ Result"

	def __str__(self):
		return f"{self.user.email} — {self.category}"


class TherapistAvailability(models.Model):
	"""Therapist sets their available time slots."""
	DAY_CHOICES = [
		(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
		(3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
	]

	therapist = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="availability_slots")
	day_of_week = models.IntegerField(choices=DAY_CHOICES)
	start_time = models.TimeField()
	end_time = models.TimeField()
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ["day_of_week", "start_time"]
		verbose_name = "Therapist Availability"
		verbose_name_plural = "Therapist Availabilities"

	def __str__(self):
		return f"{self.therapist.full_name} — {self.get_day_of_week_display()} {self.start_time}–{self.end_time}"


class TherapistDayOff(models.Model):
	"""Therapist marks specific dates as unavailable (day off)."""
	therapist = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="days_off")
	date = models.DateField()
	reason = models.CharField(max_length=200, blank=True, default="")

	class Meta:
		ordering = ["date"]
		unique_together = ["therapist", "date"]
		verbose_name = "Therapist Day Off"
		verbose_name_plural = "Therapist Days Off"

	def __str__(self):
		return f"{self.therapist.full_name} — {self.date.strftime('%b %d, %Y')}"


class Appointment(models.Model):
	"""Manages therapy appointments between patients and therapists."""

	STATUS_CHOICES = [
		("requested", "Requested"),
		("confirmed", "Confirmed"),
		("completed", "Completed"),
		("missed", "Missed"),
		("cancelled", "Cancelled"),
		("rescheduled", "Rescheduled"),
		("rejected", "Rejected"),
	]
	PAYMENT_STATUS_CHOICES = [
		("pending", "Pending"),
		("paid", "Paid"),
		("refunded", "Refunded"),
	]
	REFUND_STATUS_CHOICES = [
		("none", "None"),
		("eligible", "Eligible"),
		("not_eligible", "Not Eligible"),
		("refunded", "Refunded"),
	]
	PAYOUT_STATUS_CHOICES = [
		("pending", "Pending"),
		("paid", "Paid"),
	]

	patient = models.ForeignKey(
		CustomUser, on_delete=models.CASCADE, related_name="patient_appointments"
	)
	therapist = models.ForeignKey(
		CustomUser, on_delete=models.CASCADE, related_name="therapist_appointments"
	)
	date_time = models.DateTimeField()
	duration_minutes = models.PositiveIntegerField(default=60)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
	notes = models.TextField(blank=True, help_text="Session notes (visible to therapist)")
	patient_notes = models.TextField(
		blank=True, help_text="Patient's private notes about the session"
	)
	SESSION_TYPE_CHOICES = [
		("text_chat", "Text Chat"),
		("audio_call", "Audio Call"),
		("video_call", "Video Call"),
	]

	session_type = models.CharField(
		max_length=20, choices=SESSION_TYPE_CHOICES, default="text_chat",
		help_text="How the session will be conducted",
	)
	reminder_sent = models.BooleanField(default=False)
	fee_amount = models.PositiveIntegerField(default=0, help_text="Session fee in NPR")
	payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
	payment_method = models.CharField(max_length=20, default="card")
	payment_reference = models.CharField(max_length=100, blank=True)
	paid_at = models.DateTimeField(null=True, blank=True)
	refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default="none")
	refunded_at = models.DateTimeField(null=True, blank=True)
	therapist_payout_status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default="pending")
	therapist_paid_out_at = models.DateTimeField(null=True, blank=True)
	cancellation_reason = models.TextField(blank=True)
	rescheduled_from = models.ForeignKey(
		"self", on_delete=models.SET_NULL, null=True, blank=True, related_name="rescheduled_to"
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-date_time"]
		verbose_name = "Appointment"

	def __str__(self):
		return f"{self.patient.full_name} → {self.therapist.full_name} ({self.date_time.strftime('%b %d, %Y %I:%M %p')})"

	@property
	def is_upcoming(self):
		return self.date_time > timezone.now() and self.status in ["requested", "confirmed"]

	@property
	def is_past(self):
		return self.date_time <= timezone.now() and self.status == "completed"

	@property
	def is_missed(self):
		return self.date_time <= timezone.now() and self.status in ["requested", "confirmed"]

	@property
	def end_time(self):
		from datetime import timedelta
		return self.date_time + timedelta(minutes=self.duration_minutes)

	@property
	def session_fee(self):
		fee_map = {
			30: 1000,
			60: 2000,
			90: 3000,
		}
		return fee_map.get(self.duration_minutes, 200)

	@property
	def is_refund_eligible(self):
		if self.status != "cancelled":
			return False
		remaining = self.date_time - timezone.now()
		return remaining.total_seconds() > 24 * 3600


class TherapySession(models.Model):
	"""Tracks a live online therapy session room."""

	appointment = models.OneToOneField(
		Appointment, on_delete=models.CASCADE, related_name="therapy_session"
	)
	room_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	is_active = models.BooleanField(default=False)
	started_at = models.DateTimeField(null=True, blank=True)
	ended_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"Session: {self.appointment}"


class SessionMessage(models.Model):
	"""Chat messages sent during a live therapy session."""

	MESSAGE_TYPE_CHOICES = [
		("text", "Text"),
		("system", "System"),
	]

	session = models.ForeignKey(
		TherapySession, on_delete=models.CASCADE, related_name="session_messages"
	)
	sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="session_messages")
	content = models.TextField()
	message_type = models.CharField(max_length=10, choices=MESSAGE_TYPE_CHOICES, default="text")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["created_at"]

	def __str__(self):
		return f"{self.sender.full_name}: {self.content[:50]}"


class Payment(Appointment):
	"""Proxy model to manage payments in the Django admin separately."""
	class Meta:
		proxy = True

class SessionReport(models.Model):
	"""Therapist session reports / notes after appointments."""

	appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="report")
	therapist = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="session_reports")
	summary = models.TextField(help_text="Session summary")
	diagnosis_notes = models.TextField(blank=True, help_text="Diagnosis observations")
	treatment_plan = models.TextField(blank=True, help_text="Recommended treatment plan")
	mood_rating = models.PositiveIntegerField(
		default=5, help_text="Patient mood rating 1-10"
	)
	progress_rating = models.PositiveIntegerField(
		default=5, help_text="Progress rating 1-10"
	)
	homework = models.TextField(blank=True, help_text="Homework / exercises for patient")
	private_notes = models.TextField(blank=True, help_text="Private therapist-only notes")
	attachment = models.FileField(upload_to="session_reports/", blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self):
		return f"Report: {self.appointment} — {self.created_at.strftime('%b %d, %Y')}"


class Message(models.Model):
	"""Secure messaging between patient and therapist."""

	sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sent_messages")
	receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="received_messages")
	appointment = models.ForeignKey(
		Appointment, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages"
	)
	content = models.TextField()
	attachment = models.FileField(upload_to="message_attachments/", blank=True, null=True)
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["created_at"]

	def __str__(self):
		return f"{self.sender.full_name} → {self.receiver.full_name} ({self.created_at.strftime('%b %d %I:%M %p')})"


class Notification(models.Model):
	"""System notifications for users."""

	TYPE_CHOICES = [
		("appointment_requested", "Appointment Requested"),
		("appointment_confirmed", "Appointment Confirmed"),
		("appointment_cancelled", "Appointment Cancelled"),
		("appointment_reminder", "Appointment Reminder"),
		("appointment_rescheduled", "Appointment Rescheduled"),
		("appointment_rejected", "Appointment Rejected"),
		("report_uploaded", "Session Report Uploaded"),
		("message", "New Message"),
		("system", "System Notification"),
	]

	user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="notifications")
	type = models.CharField(max_length=30, choices=TYPE_CHOICES)
	title = models.CharField(max_length=255)
	message = models.TextField()
	is_read = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)
	related_appointment = models.ForeignKey(
		Appointment, on_delete=models.CASCADE, null=True, blank=True
	)
	redirect_url = models.CharField(max_length=255, blank=True, default="", help_text="URL to redirect when clicked")
	program_title = models.CharField(max_length=255, blank=True, null=True)
	program_description = models.TextField(blank=True, null=True)
	program_link = models.URLField(blank=True, null=True)
	program_datetime = models.DateTimeField(blank=True, null=True)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "Notification"

	def __str__(self):
		return f"{self.user.full_name}: {self.title}"


class Resource(models.Model):
	"""YouTube videos for therapeutic exercises and wellness content."""

	CATEGORY_CHOICES = [
		("anxiety", "Anxiety"),
		("depression", "Depression"),
		("stress", "Stress"),
		("ptsd", "PTSD"),
		("general", "General Wellness"),
	]

	title = models.CharField(max_length=255)
	description = models.TextField()
	category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="general")
	video_url = models.URLField(
		help_text="YouTube embed URL, e.g. https://www.youtube.com/embed/VIDEO_ID"
	)
	thumbnail = models.URLField(
		blank=True, help_text="Thumbnail image URL (optional; auto-generated for YouTube)"
	)
	duration = models.CharField(max_length=30, blank=True, help_text="e.g. '10 min', '5:30'")
	is_featured = models.BooleanField(default=False)
	order = models.PositiveIntegerField(default=0, help_text="Lower = shown first")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["order", "-created_at"]
		verbose_name = "Resource"

	def __str__(self):
		return f"{self.title} ({self.get_category_display()})"

	@property
	def youtube_thumbnail(self):
		"""Extract YouTube video ID and return thumbnail URL."""
		if "youtube.com/embed/" in self.video_url:
			vid = self.video_url.split("/embed/")[-1].split("?")[0]
			return f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
		return self.thumbnail or ""

	@property
	def youtube_watch_url(self):
		"""Convert embed URL to watch URL for direct YouTube redirect."""
		if "youtube.com/embed/" in self.video_url:
			vid = self.video_url.split("/embed/")[-1].split("?")[0]
			return f"https://www.youtube.com/watch?v={vid}"
		if "youtube.com/watch" in self.video_url:
			return self.video_url
		return self.video_url


class GuidedExercise(models.Model):
	"""Step-by-step guided exercises and relaxation techniques."""

	CATEGORY_CHOICES = [
		("anxiety", "Anxiety"),
		("depression", "Depression"),
		("stress", "Stress"),
		("ptsd", "PTSD"),
		("general", "General Wellness"),
	]

	TYPE_CHOICES = [
		("breathing", "Breathing Exercise"),
		("meditation", "Guided Meditation"),
		("relaxation", "Progressive Relaxation"),
		("journaling", "Journaling Prompt"),
		("grounding", "Grounding Technique"),
		("mindfulness", "Mindfulness Exercise"),
	]

	DIFFICULTY_CHOICES = [
		("beginner", "Beginner"),
		("intermediate", "Intermediate"),
		("advanced", "Advanced"),
	]

	title = models.CharField(max_length=255)
	description = models.TextField()
	category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="general")
	exercise_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="breathing")
	difficulty = models.CharField(max_length=15, choices=DIFFICULTY_CHOICES, default="beginner")
	steps = models.JSONField(default=list, help_text="Ordered list of step strings")
	duration_minutes = models.PositiveIntegerField(default=5)
	icon = models.CharField(max_length=10, default="🧘", help_text="Emoji icon")
	video_url = models.URLField(blank=True, help_text="Optional YouTube embed URL")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["category", "exercise_type"]
		verbose_name = "Guided Exercise"

	def __str__(self):
		return f"{self.title} ({self.get_exercise_type_display()} — {self.get_category_display()})"


class ActivityLog(models.Model):
	"""Tracks patient wellness activities like tasks, challenges, and mood check-ins."""

	ACTIVITY_TYPE_CHOICES = [
		("task", "Daily Task"),
		("challenge", "Fun Challenge"),
		("mood", "Mood Check-in"),
	]

	MOOD_CHOICES = [
		("great", "Great"),
		("good", "Good"),
		("okay", "Okay"),
		("low", "Low"),
		("struggling", "Struggling"),
	]

	user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="activity_logs")
	activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPE_CHOICES)
	title = models.CharField(max_length=255, help_text="Task/Challenge name or mood type")
	description = models.TextField(blank=True)
	mood = models.CharField(max_length=20, choices=MOOD_CHOICES, blank=True)
	points = models.PositiveIntegerField(default=0)
	completed = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	date = models.DateField(default=timezone.now)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "Activity Log"

	def __str__(self):
		return f"{self.user.full_name} — {self.get_activity_type_display()}: {self.title}"


class EmailOTP(models.Model):
	"""Stores one-time verification codes sent for auth flows."""

	PURPOSE_CHOICES = [
		("register", "Register"),
		("password_reset", "Password Reset"),
	]

	user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="email_otps")
	purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
	code = models.CharField(max_length=6)
	sent_to = models.EmailField()
	expires_at = models.DateTimeField()
	is_used = models.BooleanField(default=False)
	used_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "Email OTP"
		verbose_name_plural = "Email OTPs"

	def __str__(self):
		return f"{self.user.email} - {self.purpose}"


class TherapistRating(models.Model):
	"""Patient ratings for therapists after completed sessions."""

	patient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="given_ratings")
	therapist = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="received_ratings")
	appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="rating")
	rating = models.PositiveIntegerField(help_text="Rating 1-5 stars")
	review = models.TextField(blank=True, help_text="Optional review text")
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]
		verbose_name = "Therapist Rating"

	def __str__(self):
		return f"{self.patient.full_name} rated {self.therapist.full_name}: {self.rating}/5"

class VideoWatchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    video_id = models.CharField(max_length=50)
    video_title = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    video_source = models.CharField(max_length=50, default="youtube")
    watched_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.video_title}"


class SearchHistory(models.Model):
	"""Track user's search queries for personalized recommendations."""
	
	user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="search_history")
	query = models.CharField(max_length=255)
	results_count = models.PositiveIntegerField(default=0)
	clicked_video_id = models.CharField(max_length=255, blank=True, help_text="Video ID if user clicked a result")
	searched_at = models.DateTimeField(auto_now_add=True)
	
	class Meta:
		ordering = ["-searched_at"]
		verbose_name = "Search History"
		
	def __str__(self):
		return f"{self.user.full_name} searched: {self.query}"

class ChatSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, related_name="messages", on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=(("user","User"),("assistant","Assistant")))
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class Meta:
		ordering = ["created_at"]

def __str__(self):
	return f"[{self.role}] {self.content[:60]}"


class OnlineAwarenessProgram(models.Model):
	"""Online awareness programs created by admins."""

	title = models.CharField(max_length=255)
	description = models.TextField()
	date = models.DateField()
	time = models.TimeField()
	link = models.URLField()
	created_by = models.ForeignKey(
		CustomUser,
		on_delete=models.CASCADE,
		related_name="created_awareness_programs",
		limit_choices_to={"role": "admin"},
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-date", "-time"]
		verbose_name = "Online Awareness Program"
		verbose_name_plural = "Online Awareness Programs"

	def __str__(self):
		return self.title