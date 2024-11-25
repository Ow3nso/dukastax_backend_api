import os
import json

from django.apps import AppConfig
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app

service_account_key_content = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")

if not service_account_key_content:
    raise ValueError("Missing Firebase service account key in environment variables.")

class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        from django.conf import settings

        # if not firebase_admin._apps:
        #     cred = credentials.Certificate(settings.FIREBASE_AUTH["SERVICE_ACCOUNT_KEY"])
        #     firebase_admin.initialize_app(cred)

        if not firebase_admin._apps:
            # Use the parsed JSON dictionary directly
            # service_account_key = settings.FIREBASE_AUTH["SERVICE_ACCOUNT_KEY"]
            service_account_key = json.loads(service_account_key_content)
            cred = credentials.Certificate(service_account_key)
            firebase_admin.initialize_app(cred)

        self.firestore_client = firestore.client()
