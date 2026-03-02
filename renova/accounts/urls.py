from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
	path("", views.home, name="home"),
	path("login/", views.login_view, name="login"),
	path("register/", views.register_view, name="register"),
	path("logout/", views.logout_view, name="logout"),
	path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),

	# ── patient ──
	path("dashboard/patient/", views.patient_dashboard, name="patient_dashboard"),
	path("dashboard/patient/assessment/", views.patient_mcq, name="patient_mcq"),
	path("dashboard/patient/find-therapist/", views.find_therapist, name="find_therapist"),
	path("dashboard/patient/appointments/", views.patient_appointments, name="patient_appointments"),
	path("dashboard/patient/book/", views.book_appointment, name="book_appointment"),
	path("dashboard/patient/resources/", views.patient_resources, name="patient_resources"),
	path("dashboard/patient/resources/exercise/<int:exercise_id>/", views.exercise_detail, name="exercise_detail"),
	path("dashboard/patient/ai-chatbot/", views.ai_chatbot, name="ai_chatbot"),
	path("dashboard/patient/profile/", views.patient_profile, name="patient_profile"),
	path("dashboard/patient/therapist/<int:therapist_id>/", views.view_therapist_profile, name="view_therapist_profile"),
	path("dashboard/patient/log-activity/", views.log_activity, name="log_activity"),

	# ── appointments shared ──
	path("appointment/<int:appointment_id>/cancel/", views.cancel_appointment, name="cancel_appointment"),
	path("appointment/<int:appointment_id>/reschedule/", views.reschedule_appointment, name="reschedule_appointment"),
	path("appointment/<int:appointment_id>/confirm/", views.confirm_appointment, name="confirm_appointment"),
	path("appointment/<int:appointment_id>/reject/", views.reject_appointment, name="reject_appointment"),
	path("appointment/<int:appointment_id>/complete/", views.complete_appointment, name="complete_appointment"),
	path("appointment/<int:appointment_id>/rate/", views.rate_therapist, name="rate_therapist"),


	# ── therapist ──
	path("dashboard/doctor/", views.doctor_dashboard, name="doctor_dashboard"),
	path("dashboard/therapist/appointments/", views.therapist_appointments, name="therapist_appointments"),
	path("dashboard/therapist/availability/", views.manage_availability, name="manage_availability"),
	path("dashboard/therapist/reports/", views.session_reports, name="session_reports"),
	path("dashboard/therapist/reports/create/<int:appointment_id>/", views.create_session_report, name="create_session_report"),
	path("dashboard/therapist/reports/edit/<int:report_id>/", views.edit_session_report, name="edit_session_report"),
	path("dashboard/therapist/reports/view/<int:report_id>/", views.view_session_report, name="view_session_report"),
	path("dashboard/therapist/clients/", views.client_list, name="client_list"),
	path("dashboard/therapist/clients/<int:client_id>/", views.client_profile, name="client_profile"),
	path("dashboard/therapist/profile/", views.therapist_profile, name="therapist_profile"),

	# ── messaging ──
	path("messages/", views.inbox, name="inbox"),
	path("messages/<int:partner_id>/", views.conversation, name="conversation"),

	# ── notifications ──
	path("notifications/", views.notifications_view, name="notifications"),
	
	# ── api endpoints ──
	path("api/track-video-watch/", views.track_video_watch, name="track_video_watch"),
]
