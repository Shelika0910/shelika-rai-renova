from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		("accounts", "0015_alter_videowatchhistory_options_and_more"),
	]

	operations = [
		migrations.AddField(
			model_name="appointment",
			name="fee_amount",
			field=models.PositiveIntegerField(default=0, help_text="Session fee in NPR"),
		),
		migrations.AddField(
			model_name="appointment",
			name="paid_at",
			field=models.DateTimeField(blank=True, null=True),
		),
		migrations.AddField(
			model_name="appointment",
			name="payment_method",
			field=models.CharField(default="esewa", max_length=20),
		),
		migrations.AddField(
			model_name="appointment",
			name="payment_reference",
			field=models.CharField(blank=True, max_length=100),
		),
		migrations.AddField(
			model_name="appointment",
			name="payment_status",
			field=models.CharField(choices=[("pending", "Pending"), ("paid", "Paid"), ("refunded", "Refunded")], default="pending", max_length=20),
		),
		migrations.AddField(
			model_name="appointment",
			name="refund_status",
			field=models.CharField(choices=[("none", "None"), ("eligible", "Eligible"), ("not_eligible", "Not Eligible"), ("refunded", "Refunded")], default="none", max_length=20),
		),
		migrations.AddField(
			model_name="appointment",
			name="refunded_at",
			field=models.DateTimeField(blank=True, null=True),
		),
		migrations.AddField(
			model_name="appointment",
			name="therapist_paid_out_at",
			field=models.DateTimeField(blank=True, null=True),
		),
		migrations.AddField(
			model_name="appointment",
			name="therapist_payout_status",
			field=models.CharField(choices=[("pending", "Pending"), ("paid", "Paid")], default="pending", max_length=20),
		),
	]
