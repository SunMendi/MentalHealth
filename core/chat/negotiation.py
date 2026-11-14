from rest_framework.exceptions import NotAcceptable
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.utils.mediatypes import media_type_matches


class EventStreamContentNegotiation(DefaultContentNegotiation):
    """Accept SSE requests while keeping DRF errors in JSON.

    Successful requests use StreamingHttpResponse directly. DRF still needs a
    renderer during request initialization, before that response exists. Use the
    view's JSON renderer for validation, authentication, and throttle errors.
    """

    def select_renderer(self, request, renderers, format_suffix=None):
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except NotAcceptable:
            if any(
                media_type_matches("text/event-stream", media_type)
                for media_type in self.get_accept_list(request)
            ):
                return renderers[0], renderers[0].media_type
            raise
