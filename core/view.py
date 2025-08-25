from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    return JsonResponse({"status": "healthy", "service": "zamio_app"})

@csrf_exempt
def home_page(request):
    """Home page endpoint"""
    return JsonResponse({
        'message': 'Welcome to ZamIO API',
        'status': 'running',
        'version': '1.0.0',
        'endpoints': {
            'admin': '/admin/',
            'health': '/health/',
            'api': '/api/'
        }
    })
