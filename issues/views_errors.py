import logging
from django.shortcuts import render

logger = logging.getLogger("issues")


def handler404(request, exception=None):
    logger.warning("404 Not Found: %s", request.path)
    return render(request, "404.html", status=404)


def handler500(request):
    logger.error("500 Server Error: %s", request.path)
    return render(request, "500.html", status=500)
