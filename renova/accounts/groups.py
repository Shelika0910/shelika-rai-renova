from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from .models import CustomUser

def create_user_groups(sender, **kwargs):
    # Group for therapists
    therapist_group, created = Group.objects.get_or_create(name='Therapists')
    if created:
        content_type = ContentType.objects.get_for_model(CustomUser)
        view_patient = Permission.objects.get(codename='view_customuser', content_type=content_type)
        therapist_group.permissions.add(view_patient)

    # Group for patients
    patient_group, created = Group.objects.get_or_create(name='Patients')
    if created:
        content_type = ContentType.objects.get_for_model(CustomUser)
        view_therapist = Permission.objects.get(codename='view_customuser', content_type=content_type)
        patient_group.permissions.add(view_therapist)

    # Group for admin assistants or staff
    admin_staff_group, created = Group.objects.get_or_create(name='Admin Staff')
    if created:
        # Permissions for staff who help manage the site but are not superusers
        content_type = ContentType.objects.get_for_model(CustomUser)
        can_approve_therapists = Permission.objects.get(
            codename='change_customuser',
            content_type=content_type,
        )
        admin_staff_group.permissions.add(can_approve_therapists)
