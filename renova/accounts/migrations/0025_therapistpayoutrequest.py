from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0024_alter_customuser_specialization"),
    ]

    operations = [
        migrations.CreateModel(
            name="TherapistPayoutRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requested_amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("session_count", models.PositiveIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"), ("paid", "Paid")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("admin_note", models.TextField(blank=True, default="")),
                ("bank_name", models.CharField(max_length=120)),
                ("account_holder_name", models.CharField(max_length=120)),
                ("account_number", models.CharField(max_length=60)),
                ("branch_name", models.CharField(blank=True, default="", max_length=120)),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("is_paid", models.BooleanField(default=False)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "processed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="processed_payout_requests",
                        to="accounts.customuser",
                    ),
                ),
                (
                    "therapist",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payout_requests",
                        to="accounts.customuser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Therapist Payout Request",
                "verbose_name_plural": "Therapist Payout Requests",
                "ordering": ["-requested_at"],
            },
        ),
    ]
