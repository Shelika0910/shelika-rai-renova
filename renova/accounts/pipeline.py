from django.contrib.auth import get_user_model

User = get_user_model()


def create_user(strategy, details, backend, uid, user=None, *args, **kwargs):
    """Custom pipeline step: create or return an existing user for social auth."""
    if user:
        return {"is_new": False}

    email = details.get("email", "").strip().lower()
    if not email:
        return None

    # Re-use existing account if email already registered
    try:
        existing = User.objects.get(email=email)
        return {"is_new": False, "user": existing}
    except User.DoesNotExist:
        pass

    full_name = (
        details.get("fullname")
        or f"{details.get('first_name', '')} {details.get('last_name', '')}".strip()
        or email.split("@")[0]
    )

    new_user = User.objects.create_user(
        email=email,
        full_name=full_name,
        role="patient",
        password=None,
    )
    return {"is_new": True, "user": new_user}
