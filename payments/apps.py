from django.apps import AppConfig
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app


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
            service_account_key = settings.FIREBASE_AUTH["SERVICE_ACCOUNT_KEY"]
            cred = credentials.Certificate(service_account_key)
            firebase_admin.initialize_app(cred)

        self.firestore_client = firestore.client()
