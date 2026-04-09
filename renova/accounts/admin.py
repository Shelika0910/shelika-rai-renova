from django.contrib import admin, messages
from django.utils.translation import ngettext

<<<<<<< HEAD
from .models import (
	CustomUser, PatientMCQResult, TherapistAvailability,
	Appointment, Payment, SessionReport,  Notification,
	Resource, OnlineAwarenessProgram,
)
=======
from .models import CustomUser, PatientMCQResult
>>>>>>> parent of 482fd21 (Admin portal)

@admin.register(CustomUser)
<<<<<<< HEAD
class CustomUserAdmin(BaseUserAdmin):
	list_display = ("email", "full_name", "role", "is_approved", "is_active", "is_staff", "date_joined")
	list_filter = ("role", "is_active", "is_staff", "is_approved", "specialization")
	search_fields = ("email", "full_name")
	ordering = ("-date_joined",)
	actions = ["approve_therapists", "disapprove_therapists"]
=======
class CustomUserAdmin(admin.ModelAdmin):
	list_display = ("email", "full_name", "role", "is_approved", "is_active", "is_staff")
	list_filter = ("role", "is_approved", "is_active", "is_staff", "specialization")
	search_fields = ("email", "full_name")
	ordering = ("-date_joined",)
	actions = ["approve_therapists", "reject_therapists"]
>>>>>>> parent of 482fd21 (Admin portal)

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		("Personal Info", {"fields": ("full_name", "phone", "bio", "profile_image")}),
<<<<<<< HEAD
		("Role & Specialization", {"fields": ("role", "specialization", "is_verified", "is_approved")}),
		("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
=======
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
>>>>>>> parent of 482fd21 (Admin portal)
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

	def approve_therapists(self, request, queryset):
		queryset.update(is_approved=True)
	approve_therapists.short_description = "Approve selected therapists"

	def disapprove_therapists(self, request, queryset):
		queryset.update(is_approved=False)
	disapprove_therapists.short_description = "Disapprove selected therapists"


@admin.register(PatientMCQResult)
class PatientMCQResultAdmin(admin.ModelAdmin):
	list_display = ("user", "category", "score", "completed_at")
	list_filter = ("category",)
	search_fields = ("user__email", "user__full_name")


<<<<<<< HEAD
@admin.register(TherapistAvailability)
class TherapistAvailabilityAdmin(admin.ModelAdmin):
	list_display = ("therapist", "day_of_week", "start_time", "end_time", "is_active")
	list_filter = ("day_of_week", "is_active")
	search_fields = ("therapist__full_name",)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
	list_display = (
		"patient", "therapist", "date_time", "status",
		"payment_status", "fee_amount", "admin_earnings", "therapist_earnings", 
		"payment_method", "refund_status", "therapist_payout_status",
	)
	list_filter = ("status", "payment_status", "refund_status", "therapist_payout_status")
	search_fields = ("patient__full_name", "therapist__full_name", "payment_reference")
	date_hierarchy = "date_time"
	readonly_fields = ("admin_earnings", "therapist_earnings", "refund_eligibility_status")

	fieldsets = (
		("Appointment Details", {
			"fields": ("patient", "therapist", "date_time", "duration_minutes", "status", "notes")
		}),
		("Payment & Revenue Split (25% Admin / 75% Therapist)", {
			"fields": (
				"fee_amount", "payment_status", "payment_method", "payment_reference", "paid_at",
				"admin_earnings", "therapist_earnings",
				"therapist_payout_status", "therapist_paid_out_at"
			),
			"description": "Details showing the NPR fee split: 25% Admin and 75% Therapist."
		}),
		("Cancellation & Refunds", {
			"fields": ("cancellation_reason", "refund_status", "refunded_at", "refund_eligibility_status"),
			"description": "Refund logic: If the patient cancels > 24h before the session, they get a refund."
		}),
	)

	def admin_earnings(self, obj):
		if obj.payment_status in ['paid', 'refunded']:
			return f"NPR {obj.fee_amount * 0.25:.2f}"
		return "NPR 0.00"
	admin_earnings.short_description = "Admin Earnings (25%)"

	def therapist_earnings(self, obj):
		if obj.payment_status in ['paid', 'refunded'] or obj.status == 'completed':
			return f"NPR {obj.fee_amount * 0.75:.2f}"
		return "NPR 0.00"
	therapist_earnings.short_description = "Therapist Earnings (75%)"

	def refund_eligibility_status(self, obj):
		if obj.status == "cancelled" and obj.payment_status == "paid":
			return "Eligible (Cancelled > 24h before)" if obj.refund_status in ["eligible", "refunded"] else "Not Eligible (Cancelled < 24h before)"
		if obj.refund_status == "refunded":
			return "Refund Already Processed (Returned to Patient)"
		return "N/A"
	refund_eligibility_status.short_description = "Refund Status Details"

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
	list_display = ("payment_reference", "patient", "therapist", "date_time", "fee_amount", "payment_status", "refund_status", "therapist_payout_status")
	list_filter = ("payment_status", "refund_status", "payment_method", "therapist_payout_status", "date_time")
	search_fields = ("payment_reference", "patient__full_name", "therapist__full_name")
	date_hierarchy = "date_time"
	list_editable = ("payment_status", "refund_status", "therapist_payout_status")
	readonly_fields = ("patient", "therapist", "date_time", "fee_amount")

	fieldsets = (
		("Payment Information", {
			"fields": ("payment_reference", "patient", "therapist", "date_time", "fee_amount", "payment_method", "paid_at")
		}),
		("Status & Payout", {
			"fields": ("payment_status", "therapist_payout_status", "therapist_paid_out_at")
		}),
		("Refunds", {
			"fields": ("refund_status", "refunded_at")
		})
	)

class SessionReportAdmin(admin.ModelAdmin):
	list_display = ("appointment", "therapist", "mood_rating", "progress_rating", "created_at")
	list_display = ("appointment", "therapist", "mood_rating", "progress_rating", "created_at")
	list_filter = ("mood_rating", "progress_rating")
	search_fields = ("therapist__full_name",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
	list_display = ("user", "type", "title", "is_read", "created_at", "program_title")
	list_filter = ("type", "is_read")
	search_fields = ("user__full_name", "title", "program_title")
	fieldsets = (
		(None, {"fields": ("user", "type", "title", "message", "is_read", "redirect_url")}),
		("Program Details", {"fields": ("program_title", "program_description", "program_link", "program_datetime")}),
	)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
	list_display = ("title", "category", "is_featured", "order", "created_at")
	list_filter = ("category", "is_featured")
	search_fields = ("title", "description")
	list_editable = ("is_featured", "order")


@admin.register(OnlineAwarenessProgram)
class OnlineAwarenessProgramAdmin(admin.ModelAdmin):
	list_display = ("title", "date", "time", "created_by", "created_at")
	list_filter = ("date",)
	search_fields = ("title", "description", "created_by__full_name")
	ordering = ("-date", "-time")

	fieldsets = (
		(None, {"fields": ("title", "description", "link")}),
		("Schedule", {"fields": ("date", "time")}),
		("Author", {"fields": ("created_by",)}),
	)

	def get_queryset(self, request):
		qs = super().get_queryset(request)
		if request.user.is_superuser:
			return qs
		return qs.filter(created_by=request.user)

	def formfield_for_foreignkey(self, db_field, request, **kwargs):
		if db_field.name == "created_by":
			kwargs["initial"] = request.user.id
			kwargs["queryset"] = CustomUser.objects.filter(role="admin")
		return super().formfield_for_foreignkey(db_field, request, **kwargs)

	def save_model(self, request, obj, form, change):
		if not obj.created_by_id:
			obj.created_by = request.user
		super().save_model(request, obj, form, change)
=======
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
>>>>>>> parent of 482fd21 (Admin portal)
