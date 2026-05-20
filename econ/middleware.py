from .audit import log_action, page_title_for_request


class AuditLogMiddleware:
    SKIPPED_PREFIXES = (
        "/ISO/static/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if self._should_log(request, response):
            page_title = page_title_for_request(request)
            if request.method == "GET":
                action = "visit"
                label = "Page Visit"
            else:
                action = "submit"
                label = f"{request.method} Request"

            log_action(
                request,
                action,
                label,
                details={
                    "Page": page_title,
                    "URL": request.get_full_path(),
                    "HTTP method": request.method,
                    "Status": response.status_code,
                },
                page_title=page_title,
                status_code=response.status_code,
            )

        return response

    def _should_log(self, request, response):
        if request.path.startswith(self.SKIPPED_PREFIXES):
            return False
        if request.path.endswith("favicon.ico"):
            return False
        if response.status_code >= 500:
            return False
        return True
