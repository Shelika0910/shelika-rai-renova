from django.urls import path
from django.contrib.auth import views as auth_views

from . import views, payment_views

app_name = "accounts"

urlpatterns = [
	path("", views.home, name="home"),
	path("contact/", views.contact_us, name="contact_us"),
	path("login/", views.login_view, name="login"),
	path("register/", views.register_view, name="register"),
	# path('activate/<uidb64>/<token>/', views.activate, name='activate'),
	path("logout/", views.logout_view, name="logout"),
	path("dashboard/", views.dashboard_redirect, name="dashboard_redirect"),

	# ── password recovery ──
	path("password-reset/",
		auth_views.PasswordResetView.as_view(
			template_name="auth/password_reset.html",
			email_template_name="auth/password_reset_email.txt",
			subject_template_name="auth/password_reset_subject.txt",
			success_url="/password-reset/done/",
		), name="password_reset"),
	path("password-reset/done/",
		auth_views.PasswordResetDoneView.as_view(
			template_name="auth/password_reset_done.html",
		), name="password_reset_done"),
	path("password-reset/confirm/<uidb64>/<token>/",
		auth_views.PasswordResetConfirmView.as_view(
			template_name="auth/password_reset_confirm.html",
			success_url="/password-reset/complete/",
		), name="password_reset_confirm"),
	path("password-reset/complete/",
		auth_views.PasswordResetCompleteView.as_view(
			template_name="auth/password_reset_complete.html",
		), name="password_reset_complete"),

	# ── patient ──
	path("dashboard/patient/", views.patient_dashboard, name="patient_dashboard"),
	path("dashboard/patient/assessment/", views.patient_mcq, name="patient_mcq"),
	path("dashboard/patient/find-therapist/", views.find_therapist, name="find_therapist"),
	path("dashboard/patient/appointments/", views.patient_appointments, name="patient_appointments"),
	path("dashboard/patient/book/", views.book_appointment, name="book_appointment"),
<<<<<<< HEAD
=======
	path("dashboard/patient/appointment/<int:appointment_id>/payment/", views.esewa_payment, name="esewa_payment"),
	path("dashboard/patient/appointment/<int:appointment_id>/payment/success/", views.esewa_payment_success, name="esewa_payment_success"),
	path("dashboard/patient/appointment/<int:appointment_id>/payment/failed/", views.esewa_payment_failed, name="esewa_payment_failed"),
>>>>>>> parent of 482fd21 (Admin portal)
	path("dashboard/patient/resources/", views.patient_resources, name="patient_resources"),
	path("ai-chatbot/", views.chatbot_page, name="ai_chatbot"),
    path("ai-chatbot/<int:session_id>/", views.chatbot_page, name="chatbot_load_session"),
    path("ai-chatbot/send/", views.chatbot_send, name="chatbot_send"),
    path("ai-chatbot/new/", views.chatbot_new_session, name="chatbot_new_session"),
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

	# -- Payment --
	path('payment/initiate/<int:appointment_id>/', payment_views.esewa_payment_initiation, name='esewa_payment_initiation'),
    path('payment/verify/', payment_views.esewa_payment_verification, name='esewa_payment_verification'),

	# ── therapist ──
	path("dashboard/therapist/", views.therapist_dashboard, name="therapist_dashboard"),
	path("dashboard/therapist/appointments/", views.therapist_appointments, name="therapist_appointments"),
	path("dashboard/therapist/availability/", views.manage_availability, name="manage_availability"),
	path("dashboard/therapist/reports/", views.session_reports, name="session_reports"),
	path("dashboard/therapist/reports/create/<int:appointment_id>/", views.create_session_report, name="create_session_report"),
	path("dashboard/therapist/reports/edit/<int:report_id>/", views.edit_session_report, name="edit_session_report"),
	path("dashboard/therapist/reports/view/<int:report_id>/", views.view_session_report, name="view_session_report"),
	path("dashboard/therapist/clients/", views.client_list, name="client_list"),
	path("dashboard/therapist/clients/<int:client_id>/", views.client_profile, name="client_profile"),
	path("dashboard/therapist/profile/", views.therapist_profile, name="therapist_profile"),
	path("dashboard/therapist/payout/process/", views.process_monthly_payout, name="process_monthly_payout"),


	# ── messaging ──
	path("messages/", views.inbox, name="inbox"),
	path("messages/<int:partner_id>/", views.conversation, name="conversation"),

	# ── notifications ──
	path("notifications/", views.notifications_view, name="notifications"),
	
	# ── online sessions ──
	path("appointment/<int:appointment_id>/session/", views.session_room, name="session_room"),
	path("appointment/<int:appointment_id>/end-session/", views.end_session, name="end_session"),

	# ── api endpoints ──
	path("track-video/",views.track_video_watch,name="track_video_watch"),
]
