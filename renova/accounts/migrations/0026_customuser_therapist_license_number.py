from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0025_therapistpayoutrequest"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="therapist_license_number",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
