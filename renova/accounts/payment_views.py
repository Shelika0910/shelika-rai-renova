import base64
import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Appointment
from .views import _notify


@login_required
def esewa_payment_initiation(request, appointment_id):
	appointment = get_object_or_404(Appointment, id=appointment_id, patient=request.user)

	# Unique transaction ID for eSewa
	transaction_uuid = f"TXN-{uuid.uuid4().hex[:12].upper()}"
	appointment.payment_reference = transaction_uuid
	appointment.save()

	total_amount = appointment.fee_amount
	product_code = settings.ESEWA_PRODUCT_CODE

	# The message to be signed
	message = f"total_amount={total_amount},transaction_uuid={transaction_uuid},product_code={product_code}"

	# Generate the signature
	secret_key = settings.ESEWA_SECRET_KEY
	hash_obj = hmac.new(
		key=secret_key.encode("utf-8"),
		msg=message.encode("utf-8"),
		digestmod=hashlib.sha256,
	)
	signature = base64.b64encode(hash_obj.digest()).decode('utf-8')

	# Data to be sent to the eSewa template
	context = {
		"esewa_url": settings.ESEWA_URL,
        "amount": total_amount,
        "tax_amount": 0,
        "product_service_charge": 0,
        "product_delivery_charge": 0,
		"total_amount": total_amount,
		"transaction_uuid": transaction_uuid,
		"product_code": product_code,
		"signature": signature,
        "signed_field_names": "total_amount,transaction_uuid,product_code",
		"success_url": request.build_absolute_uri(reverse("accounts:esewa_payment_verification")),
		"failure_url": request.build_absolute_uri(reverse("accounts:patient_appointments")), 
	}

	return render(request, "payment/esewa_initiate.html", context)


@csrf_exempt
def esewa_payment_verification(request):
	if request.method == "GET":
		data_param = request.GET.get("data")
		if not data_param:
			messages.error(request, "Payment verification failed: No data received from eSewa.")
			return redirect("accounts:patient_appointments")

		try:
			# Decode the base64 data
			decoded_data = base64.b64decode(data_param).decode("utf-8")
			data = json.loads(decoded_data)

			transaction_uuid = data.get("transaction_uuid")
			status = data.get("status")
			
			# Find the appointment by transaction_uuid
			appointment = get_object_or_404(Appointment, payment_reference=transaction_uuid)

			if status == "COMPLETE":
				# Verify the signature to ensure the request is genuinely from eSewa
				signed_field_names = data.get("signed_field_names")
				message_parts = []
				for field in signed_field_names.split(','):
					if field in data:
						message_parts.append(f"{field}={data[field]}")
				
				message = ",".join(message_parts)
				
				secret_key = settings.ESEWA_SECRET_KEY
				
				# Generate HMAC SHA256 signature
				hash_obj = hmac.new(
					key=secret_key.encode("utf-8"),
					msg=message.encode("utf-8"),
					digestmod=hashlib.sha256
				)
				
				# Get the signature in Base64
				signature_base64 = base64.b64encode(hash_obj.digest()).decode('utf-8')


				if signature_base64 == data.get("signature"):
					# Payment is successful and verified
					appointment.payment_status = "paid"
					appointment.paid_at = timezone.now()
					appointment.payment_method = "esewa"
					appointment.payment_reference = data.get("transaction_code") # Store eSewa's transaction code
					appointment.save()

					# Notify therapist
					_notify(
						appointment.therapist, "appointment_requested",
						"New Paid Appointment Request",
						f"{appointment.patient.full_name} paid NPR {appointment.fee_amount} and requested an appointment on {appointment.date_time.strftime('%b %d, %Y at %I:%M %p')}.",
						appointment,
						"/dashboard/therapist/appointments/"
					)
					return render(
						request,
						"payment/success.html",
						{
							"appointment": appointment,
							"redirect_url": reverse("accounts:patient_appointments"),
							"redirect_seconds": 8,
						},
					)
				else:
					# Signature mismatch
					appointment.payment_status = "failed"
					appointment.save()
					messages.error(request, "Payment verification failed: Invalid signature.")
			else:
				# Payment was not complete
				appointment.payment_status = "failed"
				appointment.save()
				messages.warning(request, f"Payment was not completed. Status: {status}")

		except (json.JSONDecodeError, UnicodeDecodeError, Appointment.DoesNotExist, Exception) as e:
			messages.error(request, f"An error occurred during payment verification: {e}")

		return redirect("accounts:patient_appointments")

	return redirect("accounts:patient_appointments")
