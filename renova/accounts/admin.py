from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
	CustomUser, PatientMCQResult, TherapistAvailability,
	Appointment, SessionReport, Message, Notification,
	Resource, GuidedExercise,
)


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
	list_display = ("email", "full_name", "role", "is_active", "is_staff", "date_joined")
	list_filter = ("role", "is_active", "is_staff", "specialization")
	search_fields = ("email", "full_name")
	ordering = ("-date_joined",)
	fieldsets = (
		(None, {"fields": ("email", "password")}),
		("Personal Info", {"fields": ("full_name", "phone", "bio", "profile_image")}),
		("Role & Specialization", {"fields": ("role", "specialization", "is_verified")}),
		("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
		("Dates", {"fields": ("date_joined",)}),
	)
	add_fieldsets = (
		(None, {"classes": ("wide",), "fields": ("email", "full_name", "role", "password1", "password2")}),
	)


@admin.register(PatientMCQResult)
class PatientMCQResultAdmin(admin.ModelAdmin):
	list_display = ("user", "category", "score", "completed_at")
	list_filter = ("category",)
	search_fields = ("user__email", "user__full_name")


@admin.register(TherapistAvailability)
class TherapistAvailabilityAdmin(admin.ModelAdmin):
	list_display = ("therapist", "day_of_week", "start_time", "end_time", "is_active")
	list_filter = ("day_of_week", "is_active")
	search_fields = ("therapist__full_name",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	list_display = ("patient", "therapist", "date_time", "duration_minutes", "status", "created_at")
	list_filter = ("status",)
	search_fields = ("patient__full_name", "therapist__full_name")
	date_hierarchy = "date_time"


@admin.register(SessionReport)
class SessionReportAdmin(admin.ModelAdmin):
	list_display = ("appointment", "therapist", "mood_rating", "progress_rating", "created_at")
	list_filter = ("mood_rating", "progress_rating")
	search_fields = ("therapist__full_name",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
	list_display = ("sender", "receiver", "is_read", "created_at")
	list_filter = ("is_read",)
	search_fields = ("sender__full_name", "receiver__full_name", "content")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ("user", "type", "title", "is_read", "created_at")
	list_filter = ("type", "is_read")
	search_fields = ("user__full_name", "title")


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "resource_type", "is_featured", "order", "created_at")
	list_filter = ("category", "resource_type", "is_featured")
	search_fields = ("title", "description")
	list_editable = ("is_featured", "order")


@admin.register(GuidedExercise)
class GuidedExerciseAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "exercise_type", "duration_minutes", "difficulty", "created_at")
	list_filter = ("category", "exercise_type", "difficulty")
	search_fields = ("title", "description")
