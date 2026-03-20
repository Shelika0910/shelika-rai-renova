from django.contrib import admin, messages
from django.utils.translation import ngettext

from .models import CustomUser, PatientMCQResult


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
	list_display = ("email", "full_name", "role", "is_approved", "is_active", "is_staff")
	list_filter = ("role", "is_approved", "is_active", "is_staff", "specialization")
	search_fields = ("email", "full_name")
	ordering = ("-date_joined",)
	actions = ["approve_therapists", "reject_therapists"]

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		("Personal Info", {"fields": ("full_name", "phone", "bio", "profile_image")}),
		("Role & Specialization", {"fields": ("role", "specialization")}),
		(
			"Approval",
			{
				"fields": (
					"is_approved",
					"rejected",
					"rejection_reason",
					"approved_by",
				)
			},
		),
		(
			"Permissions",
			{
				"fields": (
					"is_active",
					"is_staff",
					"is_superuser",
					"groups",
					"user_permissions",
				)
			},
		),
		("Dates", {"fields": ("date_joined",)}),
	)
	add_fieldsets = (
		(
			None,
			{
				"classes": ("wide",),
				"fields": ("email", "full_name", "role", "password"),
			},
		),
	)
	readonly_fields = ["approved_by", "date_joined"]

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		return qs.filter(role="therapist")

	def approve_therapists(self, request, queryset):
		updated = queryset.update(is_approved=True, rejected=False, approved_by=request.user)
		self.message_user(
			request,
			ngettext(
				"%d therapist was successfully approved.",
				"%d therapists were successfully approved.",
				updated,
			)
			% updated,
			messages.SUCCESS,
		)

	approve_therapists.short_description = "Approve selected therapists"

	def reject_therapists(self, request, queryset):
		# For simplicity, we're not asking for a reason in the action itself.
		# Admins can set it in the user's profile.
		updated = queryset.update(is_approved=False, rejected=True)
		self.message_user(
			request,
			ngettext(
				"%d therapist was successfully rejected.",
				"%d therapists were successfully rejected.",
				updated,
			)
			% updated,
			messages.WARNING,
		)

	reject_therapists.short_description = "Reject selected therapists"


@admin.register(PatientMCQResult)
class PatientMCQResultAdmin(admin.ModelAdmin):
	list_display = ("user", "category", "score", "completed_at")
	list_filter = ("category",)
	search_fields = ("user__email", "user__full_name")


# To simplify the admin dashboard, we are commenting out other models.
# You can uncomment them as you build out the features.
#
# @admin.register(TherapistAvailability)
# class TherapistAvailabilityAdmin(admin.ModelAdmin):
# 	list_display = ("therapist", "day_of_week", "start_time", "end_time", "is_active")
# 	list_filter = ("day_of_week", "is_active")
# 	search_fields = ("therapist__full_name",)
#
#
# @admin.register(Appointment)
# class AppointmentAdmin(admin.ModelAdmin):
# 	list_display = (
# 		"patient", "therapist", "date_time", "duration_minutes", "status",
# 		"payment_status", "fee_amount", "refund_status", "therapist_payout_status", "created_at",
# 	)
# 	list_filter = ("status", "payment_status", "refund_status", "therapist_payout_status", "session_type")
# 	search_fields = ("patient__full_name", "therapist__full_name")
# 	date_hierarchy = "date_time"
#
#
# @admin.register(SessionReport)
# class SessionReportAdmin(admin.ModelAdmin):
# 	list_display = ("appointment", "therapist", "mood_rating", "progress_rating", "created_at")
# 	list_filter = ("mood_rating", "progress_rating")
# 	search_fields = ("therapist__full_name",)
#
#
# @admin.register(Message)
# class MessageAdmin(admin.ModelAdmin):
# 	list_display = ("sender", "receiver", "is_read", "created_at")
# 	list_filter = ("is_read",)
# 	search_fields = ("sender__full_name", "receiver__full_name", "content")
#
#
# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
# 	list_display = ("user", "type", "title", "is_read", "created_at")
# 	list_filter = ("type", "is_read")
# 	search_fields = ("user__full_name", "title")
#
#
# @admin.register(Resource)
# class ResourceAdmin(admin.ModelAdmin):
# 	list_display = ("title", "category", "is_featured", "order", "created_at")
# 	list_filter = ("category", "is_featured")
# 	search_fields = ("title", "description")
# 	list_editable = ("is_featured", "order")
#
#
# @admin.register(GuidedExercise)
# class GuidedExerciseAdmin(admin.ModelAdmin):
# 	list_display = ("title", "category", "exercise_type", "duration_minutes", "difficulty", "created_at")
# 	list_filter = ("category", "exercise_type", "difficulty")
# 	search_fields = ("title", "description")
