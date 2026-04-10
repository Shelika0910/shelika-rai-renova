from django.shortcuts import redirect


class TermsAcceptanceMiddleware:
	"""Require accepted terms before authenticated users can reach app pages."""

	EXEMPT_URL_NAMES = {
		"login",
		"register",
		"logout",
		"terms_and_conditions",
		"password_reset",
		"password_reset_done",
		"password_reset_confirm",
		"password_reset_complete",
	}

	EXEMPT_PREFIXES = (
		"/terms-and-conditions/",
		"/admin/",
		"/static/",
		"/media/",
	)

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		user = getattr(request, "user", None)
		if self._requires_terms_acceptance(request, user):
			return redirect("accounts:terms_and_conditions")
		return self.get_response(request)

	def _requires_terms_acceptance(self, request, user):
		if user is None or not user.is_authenticated:
			return False
		if getattr(user, "terms_accepted", False):
			return False

		path = request.path_info or ""
		if path.startswith(self.EXEMPT_PREFIXES):
			return False

		if path in {
			"/login/",
			"/register/",
			"/logout/",
			"/password-reset/",
			"/password-reset/done/",
			"/password-reset/complete/",
		}:
			return False

		if path.startswith("/password-reset/confirm/"):
			return False

		resolver_match = getattr(request, "resolver_match", None)
		if resolver_match and resolver_match.url_name in self.EXEMPT_URL_NAMES:
			return False

		return True