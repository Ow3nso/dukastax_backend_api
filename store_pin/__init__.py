# ----- 3rd Party Libraries -----
from django.http import JsonResponse

from firebase_admin import auth

# ----- In-Built Libraries -----
from .serializers import *

class FirebaseAuthenticationMixin:
    def dispatch(self, request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return JsonResponse({'error': 'Authorization header missing or invalid'}, status=401)

        token = auth_header.split('Bearer ')[1]
        try:
            decoded_token = auth.verify_id_token(token)
            request.firebase_user = decoded_token
        except Exception:
            return JsonResponse({'error': 'Invalid or expired token'}, status=401)

        return super().dispatch(request, *args, **kwargs)