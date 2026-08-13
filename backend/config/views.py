from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["GET"])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "service": "TuPymeGestiona API",
            "version": "2.0",
        }
    )
