from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
	CustomUser, PatientMCQResult, TherapistAvailability,
	Appointment, Payment, SessionReport,  Notification,
	Resource, OnlineAwarenessProgram,
)

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
	list_display = ("email", "full_name", "role", "is_approved", "is_active", "is_staff", "date_joined")
	list_filter = ("role", "is_active", "is_staff", "is_approved", "specialization")
	search_fields = ("email", "full_name")
	ordering = ("-date_joined",)
	actions = ["approve_therapists", "disapprove_therapists"]

	fieldsets = (
		(None, {"fields": ("email", "password")}),
		("Personal Info", {"fields": ("full_name", "phone", "bio", "profile_image")}),
		("Role & Specialization", {"fields": ("role", "specialization", "is_verified", "is_approved")}),
		("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
		("Dates", {"fields": ("date_joined",)}),
	)
	add_fieldsets = (
		(None, {"classes": ("wide",), "fields": ("email", "full_name", "role", "password1", "password2")}),
	)

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
