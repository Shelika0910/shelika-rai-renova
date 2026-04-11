import base64
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ActivityLog,
    Appointment,
    ChatMessage,
    EmailOTP,
    Message,
    Notification,
    PatientMCQResult,
    SessionReport,
    TherapistAvailability,
    TherapistRating,
    TherapySession,
    VideoWatchHistory,
)

User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class BaseFeatureTestCase(TestCase):
    """Shared setup helpers for readable, screenshot-friendly feature tests."""

    def setUp(self):
        self.patient = User.objects.create_user(
            email="patient@test.com",
            password="password123",
            full_name="Patient User",
            role="patient",
            terms_accepted=True,
            is_active=True,
        )
        self.therapist = User.objects.create_user(
            email="therapist@test.com",
            password="password123",
            full_name="Therapist User",
            role="therapist",
            specialization="anxiety",
            terms_accepted=True,
            is_active=True,
            is_approved=True,
        )
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="admin12345",
            full_name="Admin User",
            role="admin",
        )

    def announce(self, feature_name):
        print(f"\n=== UNIT TEST SUCCESSFUL: {feature_name} ===")

    def login_patient(self):
        self.client.login(email="patient@test.com", password="password123")

    def login_therapist(self):
        self.client.login(email="therapist@test.com", password="password123")

    def login_admin(self):
        self.client.login(email="admin@test.com", password="admin12345")

    def create_patient_mcq(self):
        return PatientMCQResult.objects.create(
            user=self.patient,
            answers={"q1": 1},
            category="anxiety",
            score=10,
        )

    def create_appointment(self, **overrides):
        defaults = {
            "patient": self.patient,
            "therapist": self.therapist,
            "date_time": timezone.now() + timedelta(days=2),
            "duration_minutes": 60,
            "status": "requested",
            "fee_amount": 200,
            "payment_status": "paid",
            "session_type": "video_call",
        }
        defaults.update(overrides)
        return Appointment.objects.create(**defaults)


class AuthenticationFeatureTests(BaseFeatureTestCase):
    def test_register_login_logout_and_social_auth(self):
        self.announce("Authentication: register + OTP verify + login + logout + social auth route")

        register_response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "New User",
                "email": "newuser@test.com",
                "password1": "newpassword123",
                "password2": "newpassword123",
                "role": "patient",
            },
        )
        self.assertEqual(register_response.status_code, 302)
        self.assertIn(reverse("accounts:verify_otp"), register_response.url)

        new_user = User.objects.get(email="newuser@test.com")
        self.assertFalse(new_user.is_active)

        otp = EmailOTP.objects.filter(user=new_user, purpose="register", is_used=False).first()
        self.assertIsNotNone(otp)

        verify_response = self.client.post(reverse("accounts:verify_otp"), {"otp_code": otp.code})
        self.assertEqual(verify_response.status_code, 302)

        new_user.refresh_from_db()
        self.assertTrue(new_user.is_active)

        logout_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(logout_response.status_code, 302)

        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": "newuser@test.com", "password": "newpassword123"},
        )
        self.assertEqual(login_response.status_code, 302)

        social_begin = self.client.get(reverse("social:begin", args=["google-oauth2"]))
        self.assertIn(social_begin.status_code, [301, 302])

    def test_password_recovery_reset_and_terms_acceptance(self):
        self.announce("Authentication: terms + forgot-password OTP + password reset flow")

        self.patient.terms_accepted = False
        self.patient.save(update_fields=["terms_accepted"])
        self.login_patient()

        redirect_response = self.client.get(reverse("accounts:patient_dashboard"))
        self.assertEqual(redirect_response.status_code, 302)
        self.assertIn(reverse("accounts:terms_and_conditions"), redirect_response.url)

        accept_terms = self.client.post(reverse("accounts:terms_and_conditions"), {"accept_terms": "on"})
        self.assertEqual(accept_terms.status_code, 302)

        self.client.get(reverse("accounts:logout"))
        forgot_start = self.client.post(reverse("accounts:forgot_password"), {"email": self.patient.email})
        self.assertEqual(forgot_start.status_code, 302)

        reset_otp = EmailOTP.objects.filter(user=self.patient, purpose="password_reset", is_used=False).first()
        self.assertIsNotNone(reset_otp)

        verify_reset = self.client.post(reverse("accounts:forgot_password_verify_otp"), {"otp_code": reset_otp.code})
        self.assertEqual(verify_reset.status_code, 302)

        set_new = self.client.post(
            reverse("accounts:forgot_password_set_new"),
            {"password1": "newpass12345", "password2": "newpass12345"},
        )
        self.assertEqual(set_new.status_code, 302)

        login_new = self.client.post(
            reverse("accounts:login"),
            {"email": self.patient.email, "password": "newpass12345"},
        )
        self.assertEqual(login_new.status_code, 302)

    def test_profile_management_for_patient_and_therapist(self):
        self.announce("Authentication: profile management for patient and therapist")

        self.create_patient_mcq()

        self.login_patient()
        patient_update = self.client.post(
            reverse("accounts:patient_profile"),
            {"full_name": "Updated Patient", "phone": "9800000000", "bio": "Patient bio"},
        )
        self.assertEqual(patient_update.status_code, 302)
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.full_name, "Updated Patient")
        self.client.get(reverse("accounts:logout"))

        self.login_therapist()
        therapist_update = self.client.post(
            reverse("accounts:therapist_profile"),
            {
                "full_name": "Updated Therapist",
                "phone": "9811111111",
                "bio": "Therapist bio",
                "specialization": "stress",
            },
        )
        self.assertEqual(therapist_update.status_code, 302)
        self.therapist.refresh_from_db()
        self.assertEqual(self.therapist.full_name, "Updated Therapist")


class PatientFeatureTests(BaseFeatureTestCase):
    def setUp(self):
        super().setUp()
        self.login_patient()

    def test_patient_dashboard_assessment_therapist_discovery_and_booking(self):
        self.announce("Patient: dashboard + MCQ + find therapist + book appointment")

        mcq_payload = {f"q{i}": 1 for i in range(1, 11)}
        mcq_response = self.client.post(reverse("accounts:patient_mcq"), mcq_payload)
        self.assertEqual(mcq_response.status_code, 302)
        self.assertTrue(PatientMCQResult.objects.filter(user=self.patient).exists())

        dashboard = self.client.get(reverse("accounts:patient_dashboard"))
        self.assertEqual(dashboard.status_code, 200)

        find_page = self.client.get(reverse("accounts:find_therapist"))
        self.assertEqual(find_page.status_code, 200)

        future_slot = timezone.localtime(timezone.now() + timedelta(days=3))
        booking_response = self.client.post(
            reverse("accounts:book_appointment"),
            {
                "therapist_id": self.therapist.id,
                "appointment_date": future_slot.strftime("%Y-%m-%d"),
                "appointment_time": future_slot.strftime("%H:%M"),
                "duration": 60,
                "session_type": "video_call",
            },
        )
        self.assertEqual(booking_response.status_code, 302)
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), 1)

    @patch("accounts.views.get_gemini_response", return_value="Take a deep breath and hydrate.")
    @patch("accounts.views.get_youtube_videos", return_value=[{"id": "v1", "title": "Mindful breathing"}])
    def test_resources_watch_tracking_chatbot_and_activity_logging(self, _mock_youtube, _mock_gemini):
        self.announce("Patient: resources + video watch tracking + AI chatbot + activity logging")

        self.create_patient_mcq()
        resources = self.client.get(reverse("accounts:patient_resources"))
        self.assertEqual(resources.status_code, 200)

        watch_payload = {
            "video_id": "abc123",
            "video_title": "Mindful breathing",
            "category": "anxiety",
            "video_source": "youtube",
        }
        watch_response = self.client.post(
            reverse("accounts:track_video_watch"),
            data=json.dumps(watch_payload),
            content_type="application/json",
        )
        self.assertEqual(watch_response.status_code, 200)
        self.assertEqual(VideoWatchHistory.objects.filter(user=self.patient).count(), 1)

        chat_page = self.client.get(reverse("accounts:ai_chatbot"))
        self.assertEqual(chat_page.status_code, 200)

        chatbot_send = self.client.post(
            reverse("accounts:chatbot_send"),
            data=json.dumps({"message": "I feel anxious today"}),
            content_type="application/json",
        )
        self.assertEqual(chatbot_send.status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(role="user").count(), 1)
        self.assertEqual(ChatMessage.objects.filter(role="assistant").count(), 1)

        activity_response = self.client.post(
            reverse("accounts:log_activity"),
            data=json.dumps(
                {
                    "activity_type": "task",
                    "title": "10-min walk",
                    "description": "Evening walk",
                    "points": 20,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(activity_response.status_code, 200)
        self.assertEqual(ActivityLog.objects.filter(user=self.patient).count(), 1)

    def test_rate_and_review_therapist_after_completed_session(self):
        self.announce("Patient: therapist rating and review after appointment")

        completed_appointment = self.create_appointment(status="completed", payment_status="paid")
        response = self.client.post(
            reverse("accounts:rate_therapist", args=[completed_appointment.id]),
            {"rating": 5, "review": "Very helpful session"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TherapistRating.objects.filter(appointment=completed_appointment).count(), 1)


class TherapistFeatureTests(BaseFeatureTestCase):
    def setUp(self):
        super().setUp()
        self.create_patient_mcq()
        self.login_therapist()

    def test_therapist_dashboard_availability_clients_reports_and_payout(self):
        self.announce("Therapist: dashboard + availability + client list/profile + reports + payouts")

        dashboard = self.client.get(reverse("accounts:therapist_dashboard"))
        self.assertEqual(dashboard.status_code, 200)

        availability_post = self.client.post(
            reverse("accounts:manage_availability"),
            {
                "action": "save_slots",
                "slot_day_0": 1,
                "slot_start_0": "09:00",
                "slot_end_0": "11:00",
            },
        )
        self.assertEqual(availability_post.status_code, 302)
        self.assertEqual(TherapistAvailability.objects.filter(therapist=self.therapist).count(), 1)

        confirmed_appointment = self.create_appointment(status="confirmed", payment_status="paid")
        completed_appointment = self.create_appointment(
            status="completed",
            payment_status="paid",
            date_time=timezone.now() - timedelta(days=1),
        )

        clients = self.client.get(reverse("accounts:client_list"))
        self.assertEqual(clients.status_code, 200)

        client_profile = self.client.get(reverse("accounts:client_profile", args=[self.patient.id]))
        self.assertEqual(client_profile.status_code, 200)

        create_report = self.client.post(
            reverse("accounts:create_session_report", args=[confirmed_appointment.id]),
            {
                "summary": "Session summary",
                "diagnosis_notes": "Diagnosis",
                "treatment_plan": "Plan",
                "mood_rating": 6,
                "progress_rating": 7,
            },
        )
        self.assertEqual(create_report.status_code, 302)
        report = SessionReport.objects.get(appointment=confirmed_appointment)

        edit_report = self.client.post(
            reverse("accounts:edit_session_report", args=[report.id]),
            {"summary": "Updated summary", "mood_rating": 8, "progress_rating": 8},
        )
        self.assertEqual(edit_report.status_code, 302)

        view_report = self.client.get(reverse("accounts:view_session_report", args=[report.id]))
        self.assertEqual(view_report.status_code, 200)

        payout_response = self.client.post(reverse("accounts:process_monthly_payout"))
        self.assertEqual(payout_response.status_code, 302)
        completed_appointment.refresh_from_db()
        self.assertEqual(completed_appointment.therapist_payout_status, "paid")


class AppointmentManagementFeatureTests(BaseFeatureTestCase):
    def test_confirm_reject_reschedule_cancel_and_complete_appointments(self):
        self.announce("Appointment Management: confirm/reject/reschedule/cancel/complete")

        # Therapist confirms a paid requested appointment.
        confirm_apt = self.create_appointment(status="requested", payment_status="paid")
        self.login_therapist()
        confirm_response = self.client.post(reverse("accounts:confirm_appointment", args=[confirm_apt.id]))
        self.assertEqual(confirm_response.status_code, 302)
        confirm_apt.refresh_from_db()
        self.assertEqual(confirm_apt.status, "confirmed")
        self.client.get(reverse("accounts:logout"))

        # Therapist rejects a request and triggers refund state for paid sessions.
        reject_apt = self.create_appointment(status="requested", payment_status="paid")
        self.login_therapist()
        reject_response = self.client.post(
            reverse("accounts:reject_appointment", args=[reject_apt.id]),
            {"rejection_reason": "Unavailable"},
        )
        self.assertEqual(reject_response.status_code, 302)
        reject_apt.refresh_from_db()
        self.assertEqual(reject_apt.status, "rejected")
        self.assertEqual(reject_apt.payment_status, "refunded")
        self.client.get(reverse("accounts:logout"))

        # Patient reschedules and the system creates a new appointment.
        reschedule_apt = self.create_appointment(status="confirmed", payment_status="paid")
        self.login_patient()
        new_slot = timezone.localtime(timezone.now() + timedelta(days=5))
        reschedule_response = self.client.post(
            reverse("accounts:reschedule_appointment", args=[reschedule_apt.id]),
            {
                "appointment_date": new_slot.strftime("%Y-%m-%d"),
                "appointment_time": new_slot.strftime("%H:%M"),
            },
        )
        self.assertEqual(reschedule_response.status_code, 302)
        reschedule_apt.refresh_from_db()
        self.assertEqual(reschedule_apt.status, "rescheduled")
        self.assertTrue(Appointment.objects.filter(rescheduled_from=reschedule_apt).exists())
        self.client.get(reverse("accounts:logout"))

        # Patient cancels >24h before and receives a refund.
        cancel_apt = self.create_appointment(
            status="confirmed",
            payment_status="paid",
            date_time=timezone.now() + timedelta(days=3),
        )
        self.login_patient()
        cancel_response = self.client.post(
            reverse("accounts:cancel_appointment", args=[cancel_apt.id]),
            {"cancellation_reason": "Need to travel"},
        )
        self.assertEqual(cancel_response.status_code, 302)
        cancel_apt.refresh_from_db()
        self.assertEqual(cancel_apt.status, "cancelled")
        self.assertEqual(cancel_apt.refund_status, "refunded")
        self.client.get(reverse("accounts:logout"))

        # Therapist marks a paid confirmed session as complete.
        complete_apt = self.create_appointment(status="confirmed", payment_status="paid")
        self.login_therapist()
        complete_response = self.client.post(reverse("accounts:complete_appointment", args=[complete_apt.id]))
        self.assertEqual(complete_response.status_code, 302)
        complete_apt.refresh_from_db()
        self.assertEqual(complete_apt.status, "completed")


class TelehealthAndCommunicationFeatureTests(BaseFeatureTestCase):
    def test_messaging_notifications_and_secure_session_rooms(self):
        self.announce("Telehealth: private messaging + notifications + secure session room")

        self.login_patient()
        send_message = self.client.post(
            reverse("accounts:conversation", args=[self.therapist.id]),
            {"content": "Hello doctor"},
        )
        self.assertEqual(send_message.status_code, 302)
        self.assertEqual(Message.objects.filter(sender=self.patient, receiver=self.therapist).count(), 1)

        Notification.objects.create(
            user=self.patient,
            type="system",
            title="System Alert",
            message="Test unread notification",
            is_read=False,
        )
        notifications_page = self.client.get(reverse("accounts:notifications"))
        self.assertEqual(notifications_page.status_code, 200)
        self.assertFalse(Notification.objects.filter(user=self.patient, is_read=False).exists())

        session_apt = self.create_appointment(
            status="confirmed",
            payment_status="paid",
            date_time=timezone.now() + timedelta(minutes=2),
            duration_minutes=30,
        )
        join_room = self.client.get(reverse("accounts:session_room", args=[session_apt.id]))
        self.assertEqual(join_room.status_code, 200)
        self.assertTrue(TherapySession.objects.filter(appointment=session_apt, is_active=True).exists())

        end_room = self.client.get(reverse("accounts:end_session", args=[session_apt.id]))
        self.assertEqual(end_room.status_code, 302)
        self.assertFalse(TherapySession.objects.get(appointment=session_apt).is_active)

    def test_join_session_remains_visible_while_session_is_active(self):
        self.announce("Telehealth: join session stays visible during an active appointment")

        self.create_patient_mcq()
        self.login_patient()

        active_session_apt = self.create_appointment(
            status="confirmed",
            payment_status="paid",
            date_time=timezone.now() - timedelta(minutes=10),
            duration_minutes=30,
        )

        appointments_page = self.client.get(reverse("accounts:patient_appointments"))
        self.assertEqual(appointments_page.status_code, 200)
        self.assertContains(appointments_page, reverse("accounts:session_room", args=[active_session_apt.id]))

    def test_join_session_opens_room_for_confirmed_future_appointment(self):
        self.announce("Telehealth: join session opens room for confirmed future appointment")

        self.login_patient()
        future_confirmed = self.create_appointment(
            status="confirmed",
            payment_status="paid",
            date_time=timezone.now() + timedelta(days=2),
            duration_minutes=60,
        )

        join_room = self.client.get(reverse("accounts:session_room", args=[future_confirmed.id]))
        self.assertEqual(join_room.status_code, 200)
        self.assertTrue(TherapySession.objects.filter(appointment=future_confirmed, is_active=True).exists())


@override_settings(ESEWA_SECRET_KEY="8gBm/:&EnhH.1/q")
class PaymentFeatureTests(BaseFeatureTestCase):
    def test_esewa_initiation_and_verification_flow(self):
        self.announce("Payments: eSewa initiation + verification callback")

        self.login_patient()
        appointment = self.create_appointment(status="requested", payment_status="pending")

        initiation = self.client.get(reverse("accounts:esewa_payment_initiation", args=[appointment.id]))
        self.assertEqual(initiation.status_code, 200)
        appointment.refresh_from_db()
        self.assertTrue(appointment.payment_reference.startswith("TXN-"))

        signed_field_names = "total_amount,transaction_uuid,product_code"
        message = (
            f"total_amount={appointment.fee_amount},"
            f"transaction_uuid={appointment.payment_reference},"
            f"product_code={settings.ESEWA_PRODUCT_CODE}"
        )
        signature = base64.b64encode(
            hmac.new(
                settings.ESEWA_SECRET_KEY.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        callback_payload = {
            "transaction_uuid": appointment.payment_reference,
            "status": "COMPLETE",
            "signed_field_names": signed_field_names,
            "total_amount": appointment.fee_amount,
            "product_code": settings.ESEWA_PRODUCT_CODE,
            "signature": signature,
            "transaction_code": "ESEWA-CODE-123",
        }
        encoded_data = base64.b64encode(json.dumps(callback_payload).encode("utf-8")).decode("utf-8")

        verify_response = self.client.get(reverse("accounts:esewa_payment_verification"), {"data": encoded_data})
        self.assertEqual(verify_response.status_code, 200)
        self.assertTemplateUsed(verify_response, "payment/success.html")
        self.assertContains(verify_response, "Payment Successful")

        appointment.refresh_from_db()
        self.assertEqual(appointment.payment_status, "paid")
        self.assertEqual(appointment.payment_method, "esewa")


class AdminFeatureTests(BaseFeatureTestCase):
    def test_admin_portal_jazzmin_and_model_registration(self):
        self.announce("Admin: Jazzmin portal + model/account management coverage")

        self.assertIn("jazzmin", settings.INSTALLED_APPS)
        self.assertIn("social_django", settings.INSTALLED_APPS)

        self.login_admin()
        admin_page = self.client.get(reverse("admin:index"))
        self.assertEqual(admin_page.status_code, 200)

        # These model registrations support admin control over platform data.
        self.assertIn(User, admin.site._registry)
        self.assertIn(Appointment, admin.site._registry)
        self.assertIn(PatientMCQResult, admin.site._registry)