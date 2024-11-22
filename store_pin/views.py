# ----- 3rd Party Libraries -----
from django.apps import apps
from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from firebase_admin import auth

# ----- In-Built Libraries -----
from .serializers import *
from . import FirebaseAuthenticationMixin

class SavePinView(APIView):
    def post(self, request):
        serializer = PinSerializer(data=request.data)
        firestore_client = apps.get_app_config('payments').firestore_client

        if serializer.is_valid():
            pin = serializer.validated_data['pin']
            user_id = serializer.validated_data['user_id']

            try:
                firestore_client.collection('users_store_pin').document(str(user_id)).set({
                    'pin': pin
                }, merge=True)
                return Response({"message": "PIN saved successfully"}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ConfirmPinView(APIView):
    def post(self, request):
        serializer = ConfirmPinSerializer(data=request.data)
        firestore_client = apps.get_app_config('payments').firestore_client

        if serializer.is_valid():
            pin = serializer.validated_data['pin']
            user_id = serializer.validated_data['user_id']

            # Retrieve the user's stored PIN from Firestore
            user_doc = firestore_client.collection('users_store_pin').document(str(user_id)).get()

            if user_doc.exists:
                stored_pin = user_doc.to_dict().get('pin')

                if stored_pin == pin:
                    return Response({"message": "PIN confirmed. Access granted."}, status=status.HTTP_200_OK)
                else:
                    return Response({"error": "Incorrect PIN."}, status=status.HTTP_403_FORBIDDEN)
            else:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CheckPinStatusView(APIView):
    def get(self, request, user_id):
        firestore_client = apps.get_app_config('payments').firestore_client  # Access Firestore client from app config

        try:
            # Fetch the document for the given user_id
            pin_doc = firestore_client.collection('users_store_pin').document(str(user_id)).get()

            # Check if the document exists and return appropriate response
            if pin_doc.exists:
                return Response({"pin_exists": True, "message": "PIN exists for the user."}, status=status.HTTP_200_OK)
            else:
                return Response({"pin_exists": False, "message": "No PIN found for the user."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)