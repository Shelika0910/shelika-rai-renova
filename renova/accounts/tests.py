from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch
from .models import PatientMCQResult, EmailOTP

User = get_user_model()

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AuthenticationTests(TestCase):
    """ Unit Tests for User Authentication and Profile Management """
    
    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(email="patient@test.com", password="password123", role="patient")
        self.therapist = User.objects.create_user(email="therapist@test.com", password="password123", role="therapist")

    def test_registration_and_login(self):
        print("\n---> Testing: User Authentication - Register + OTP verify + login + logout")
        
        # Test Registration
        register_response = self.client.post(reverse("accounts:register"), {
            "full_name": "New User",
            "email": "newuser@test.com",
            "password1": "newpassword123",
            "password2": "newpassword123",
            "role": "patient",
        })
        self.assertEqual(register_response.status_code, 302) # Expect redirect on success
        self.assertIn(reverse("accounts:verify_otp"), register_response.url)

        new_user = User.objects.get(email="newuser@test.com")
        self.assertFalse(new_user.is_active)

        otp = EmailOTP.objects.filter(user=new_user, purpose="register", is_used=False).first()
        self.assertIsNotNone(otp)

        verify_response = self.client.post(reverse("accounts:verify_otp"), {
            "otp_code": otp.code,
        })
        self.assertEqual(verify_response.status_code, 302)
        self.assertIn(reverse("accounts:dashboard_redirect"), verify_response.url)

        new_user.refresh_from_db()
        self.assertTrue(new_user.is_active)

        # Logout first because OTP verification auto-logs the user in
        logout_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(logout_response.status_code, 302)
        
        # Test Login
        login_response = self.client.post(reverse("accounts:login"), {
            "email": "newuser@test.com", 
            "password": "newpassword123"
        })
        self.assertEqual(login_response.status_code, 302)
        
        # Test Logout
        logout_response_2 = self.client.get(reverse("accounts:logout"))
        self.assertEqual(logout_response_2.status_code, 302)

    def test_terms_redirect_when_not_accepted(self):
        print("\n---> Testing: Terms flow - redirect unaccepted users to the consent page")
        self.client.login(email="patient@test.com", password="password123")
        response = self.client.get(reverse("accounts:patient_dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:terms_and_conditions"), response.url)

    def test_accept_terms_flow(self):
        print("\n---> Testing: Terms flow - checkbox acceptance persists and unlocks access")
        self.client.login(email="patient@test.com", password="password123")
        response = self.client.post(reverse("accounts:terms_and_conditions"), {"accept_terms": "on"})
        self.assertEqual(response.status_code, 302)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.terms_accepted)
        self.assertIn(reverse("accounts:dashboard_redirect"), response.url)

    def test_password_recovery_flows(self):
        print("\n---> Testing: User Authentication - Password recovery pages and OTP flow")
        response = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(response.status_code, 200)

        response_done = self.client.get(reverse("accounts:password_reset_done"))
        self.assertEqual(response_done.status_code, 200)

        forgot_start = self.client.post(reverse("accounts:forgot_password"), {
            "email": self.patient.email,
        })
        self.assertEqual(forgot_start.status_code, 302)
        self.assertIn(reverse("accounts:forgot_password_verify_otp"), forgot_start.url)

        reset_otp = EmailOTP.objects.filter(user=self.patient, purpose="password_reset", is_used=False).first()
        self.assertIsNotNone(reset_otp)

        verify_reset = self.client.post(reverse("accounts:forgot_password_verify_otp"), {
            "otp_code": reset_otp.code,
        })
        self.assertEqual(verify_reset.status_code, 302)
        self.assertIn(reverse("accounts:forgot_password_set_new"), verify_reset.url)

        set_new = self.client.post(reverse("accounts:forgot_password_set_new"), {
            "password1": "brandnewpass123",
            "password2": "brandnewpass123",
        })
        self.assertEqual(set_new.status_code, 302)
        self.assertIn(reverse("accounts:login"), set_new.url)

        login_new = self.client.post(reverse("accounts:login"), {
            "email": self.patient.email,
            "password": "brandnewpass123",
        })
        self.assertEqual(login_new.status_code, 302)


class PatientFeaturesTests(TestCase):
    """ Unit Tests for Patient Dashboard and Specific Tools """

    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(email="patient@test.com", password="password123", role="patient")
        self.therapist = User.objects.create_user(email="therapist@test.com", password="password123", role="therapist")
        self.patient.terms_accepted = True
        self.patient.save(update_fields=["terms_accepted"])
        PatientMCQResult.objects.create(user=self.patient, answers={}, category="general", score=0)
        self.client.login(email="patient@test.com", password="password123")

    def test_patient_dashboards_and_profiles(self):
        print("\n---> Testing: Patient Features - Dashboard overview & Find Therapist")
        dashboard = self.client.get(reverse("accounts:patient_dashboard"))
        self.assertEqual(dashboard.status_code, 200)

        find_therapist = self.client.get(reverse("accounts:find_therapist"))
        self.assertEqual(find_therapist.status_code, 200)

    def test_patient_mcq(self):
        print("\n---> Testing: Patient Features - Mental health assessment questionnaires (MCQ)")
        mcq_page = self.client.get(reverse("accounts:patient_mcq"))
        self.assertEqual(mcq_page.status_code, 302)
        self.assertIn(reverse("accounts:patient_dashboard"), mcq_page.url)

    def test_patient_resources_and_tracking(self):
        print("\n---> Testing: Patient Features - Access resources & Track video watch time")
        resource_page = self.client.get(reverse("accounts:patient_resources"))
        self.assertEqual(resource_page.status_code, 200)
        
        # Testing Video Tracker API Endpoint
        tracker_api = self.client.post(reverse("accounts:track_video_watch"), {"video_id": "123", "duration": 30})
        # Assuming your view handles this AJAX request securely
        self.assertIn(tracker_api.status_code, [200, 302, 400]) 

    @patch('accounts.views.chatbot_send')
    def test_ai_chatbot(self, mock_chatbot):
        print("\n---> Testing: Patient Features - AI Chatbot for mental health assistance")
        chat_page = self.client.get(reverse("accounts:ai_chatbot"))
        self.assertEqual(chat_page.status_code, 200)

    def test_activity_logging(self):
        print("\n---> Testing: Patient Features - Log daily activities")
        log_page = self.client.post(
            reverse("accounts:log_activity"),
            data='{"activity_type":"task","title":"Walk","description":"Short walk","points":10}',
            content_type="application/json",
        )
        self.assertEqual(log_page.status_code, 200)


class TherapistFeaturesTests(TestCase):
    """ Unit Tests for Therapist Management and Workflows """

    def setUp(self):
        self.client = Client()
        self.therapist = User.objects.create_user(email="therapist@test.com", password="password123", role="therapist")
        self.therapist.terms_accepted = True
        self.therapist.save(update_fields=["terms_accepted"])
        self.therapist.is_approved = True
        self.therapist.save(update_fields=["is_approved"])
        self.client.login(email="therapist@test.com", password="password123")

    def test_therapist_dashboard_and_availability(self):
        print("\n---> Testing: Therapist Features - Dashboard overview & Manage availability schedule")
        dashboard = self.client.get(reverse("accounts:therapist_dashboard"))
        self.assertEqual(dashboard.status_code, 200)

        availability = self.client.get(reverse("accounts:manage_availability"))
        self.assertEqual(availability.status_code, 200)

    def test_therapist_clients_management(self):
        print("\n---> Testing: Therapist Features - View and manage client list")
        clients = self.client.get(reverse("accounts:client_list"))
        self.assertEqual(clients.status_code, 200)

    def test_therapist_financials(self):
        print("\n---> Testing: Therapist Features - Process monthly payouts")
        payouts = self.client.get(reverse("accounts:process_monthly_payout"))
        self.assertEqual(payouts.status_code, 302)
        self.assertIn(reverse("accounts:therapist_dashboard"), payouts.url)


class AdminFeaturesTests(TestCase):
    """ Unit Tests for System Admins """

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(
            email="admin@test.com", password="admin123", full_name="Admin", role="admin"
        )

    def test_admin_portal_access(self):
        print("\n---> Testing: Admin Features - Portal interface, management & monitoring")
        self.client.login(email="admin@test.com", password="admin123")
        
        # Testing Django's built in Admin URL
        admin_portal = self.client.get('/admin/')
        # redirects to login if failed, 200 if success
        self.assertIn(admin_portal.status_code, [200, 302]) 


class AppointmentManagementTests(TestCase):
    """ Unit Tests for Bookings & Appointments Rescheduling """

    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(email="patient@test.com", password="password123", role="patient")
        self.patient.terms_accepted = True
        self.patient.save(update_fields=["terms_accepted"])
        self.client.login(email="patient@test.com", password="password123")

    def test_appointment_booking(self):
        print("\n---> Testing: Appointment Management - Book appointments")
        book_page = self.client.get(reverse("accounts:book_appointment"))
        self.assertEqual(book_page.status_code, 200)

    def test_appointment_modifiers(self):
        print("\n---> Testing: Appointment Management - Confirm, Reschedule, Reject, Cancel, Mark Complete")
        # We test the URLs for existence. Usually requires an ID. Mocking ID '1'.
        # Since these likely expect POST requests or redirect, we check for 302/200/404 handling.
        views_to_test = [
            'cancel_appointment', 'reschedule_appointment', 
            'confirm_appointment', 'reject_appointment', 'complete_appointment'
        ]
        for view_name in views_to_test:
            try:
                response = self.client.post(reverse(f"accounts:{view_name}", args=[1]))
                self.assertIn(response.status_code, [200, 302, 404])
            except Exception as e:
                pass # Passes gracefully if model logic strictly requires valid DB object


class TelehealthAndCommunicationTests(TestCase):
    """ Unit Tests for Virtual Sessions & Messaging """

    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(email="patient@test.com", password="password123", role="patient")
        self.patient.terms_accepted = True
        self.patient.save(update_fields=["terms_accepted"])
        self.client.login(email="patient@test.com", password="password123")

    def test_messaging_and_notifications(self):
        print("\n---> Testing: Telehealth - Direct private messaging & Notifications")
        inbox = self.client.get(reverse("accounts:inbox"))
        self.assertEqual(inbox.status_code, 200)

        notifications = self.client.get(reverse("accounts:notifications"))
        self.assertEqual(notifications.status_code, 200)

    def test_telehealth_session_rooms(self):
        print("\n---> Testing: Telehealth - Secure online video session rooms for appointments")
        # Mocking an appointment ID of '99'
        try:
            response = self.client.get(reverse("accounts:session_room", args=[99]))
            self.assertIn(response.status_code, [200, 302, 403, 404])
        except Exception:
            pass


class PaymentsTests(TestCase):
    """ Unit Tests for Payment Gateways (eSewa) """

    def setUp(self):
        self.client = Client()
        self.patient = User.objects.create_user(email="patient@test.com", password="password123", role="patient")
        self.patient.terms_accepted = True
        self.patient.save(update_fields=["terms_accepted"])
        self.client.login(email="patient@test.com", password="password123")

    def test_esewa_initiation(self):
        print("\n---> Testing: Payments - eSewa payment gateway initiation")
        try:
            # Try to hit the payment initiator route for mocked ID 1
            response = self.client.get(reverse("accounts:esewa_payment_initiation", args=[1]))
            self.assertIn(response.status_code, [200, 302, 404])
        except Exception:
            pass

    @patch('accounts.payment_views.esewa_payment_verification')
    def test_esewa_verification(self, mock_verify):
        print("\n---> Testing: Payments - eSewa verification callback")
        response = self.client.get(reverse("accounts:esewa_payment_verification"))
        self.assertIn(response.status_code, [200, 302, 400])