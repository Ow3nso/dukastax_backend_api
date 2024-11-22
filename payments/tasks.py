# ----- 3rd Party Libraries -----
import os
import requests
from celery import shared_task
from django.conf import settings
from dotenv import load_dotenv
from django.apps import apps

# ----- In-Built Libraries -----
from .models import Transactions

load_dotenv()
intasend_secret_api_key = os.getenv('INTASEND_SECRET_API_KEY')

# @shared_task
# def update_transaction_states():
#     transactions = Transactions.objects.filter(status__in=['PENDING', 'PROCESSING'])

#     for transaction in transactions:
#         response = requests.post(
#             'https://sandbox.intasend.com/api/v1/payment/status/',
#             json={
#                 'invoice_id': transaction.invoice_id,
#             },
#             headers={
#                 'Authorization': f'Bearer {intasend_secret_api_key}'
#             },
#         )

#         if response.status_code == 200:
#             data = response.json()
#             state = data.get('state')
#             transaction.state = state
#             transaction.save()

@shared_task
def update_transaction_states():

    try:
        firestore_client = apps.get_app_config('payments').firestore_client
        transactions_ref = firestore_client.collection('mytransactions')

        # Query transactions that are in PENDING or PROCESSING state
        query = transactions_ref.where('status', 'in', ['PENDING', 'PROCESSING'])
        transactions = query.stream()

        # Process transactions in batch for efficiency
        for transaction in transactions:
            transaction_data = transaction.to_dict()
            transaction_id = transaction.id
            invoice_id = transaction_data.get('invoiceId')

            # Skip if invoice_id is missing
            if not invoice_id:
                print(f"Transaction {transaction_id} has no invoice_id. Skipping.")
                continue

            # Fetch the current status directly (no need for a txn argument)
            current_status = transaction_data.get('status')
            if current_status not in ['PENDING', 'PROCESSING']:
                print(f"Transaction {transaction_id} already updated. Skipping.")
                continue

            # Fetch status from the payment provider
            try:
                response = requests.post(
                    'https://sandbox.intasend.com/api/v1/payment/status/',
                    json={'invoice_id': invoice_id},
                    headers={'Authorization': f'Bearer {intasend_secret_api_key}'},
                    timeout=10  # Set timeout for network requests
                )

                if response.status_code == 200:
                    data = response.json()
                    invoice = data.get('invoice', {})
                    new_status = invoice.get('state')

                    # Update Firestore document with the new status
                    transaction.reference.update({'status': new_status})
                    print(f"Transaction {transaction_id} updated to {new_status}.")
                else:
                    # Log error and retry if it's a recoverable error
                    print(f"Failed to fetch status for transaction {transaction_id}. "
                                      f"Status Code: {response.status_code}, Response: {response.json()}")
                    # self.retry(exc=Exception(f"Error fetching status for {transaction_id}"))

            except requests.exceptions.RequestException as req_exc:
                # Handle network-related errors gracefully
                print(f"Network error while processing transaction {transaction_id}: {str(req_exc)}")
                # self.retry(exc=req_exc)

    except Exception as general_exc:
        # Log general errors outside of individual transaction processing
        print(f"General error in update_transaction_states task: {str(general_exc)}")

# payments/tasks.py

# payments/tasks.py

# payments/tasks.py

# import os
# import logging
# import requests
# from django.apps import apps
# from celery import shared_task
# from dotenv import load_dotenv
# from celery.utils.log import get_task_logger

# load_dotenv()
# intasend_secret_api_key = os.getenv('INTASEND_SECRET_API_KEY')

# # Initialize Firestore client
# # db = firestore.Client()

# # Configure logging
# logger = get_task_logger(__name__)
# logger.setLevel(logging.WARNING)
# logging.getLogger('django').setLevel(logging.WARNING)
# logging.getLogger('celery').setLevel(logging.WARNING)

# @shared_task(bind=True, max_retries=5, default_retry_delay=60)
# def update_transaction_states(self):
#     """
#     Periodic task to update the status of transactions.
#     Handles transactions with PENDING or PROCESSING status.
#     Uses Firestore to fetch and update transactions.
#     """
#     # Initialize task-specific logger
#     task_logger = get_task_logger(__name__)

#     try:
#         firestore_client = apps.get_app_config('payments').firestore_client
#         transactions_ref = firestore_client.collection('mytransactions')

#         # Query transactions that are in PENDING or PROCESSING state
#         query = transactions_ref.where('status', 'in', ['PENDING', 'PROCESSING'])
#         transactions = query.stream()

#         # Process transactions in batch for efficiency
#         for transaction in transactions:
#             transaction_data = transaction.to_dict()
#             transaction_id = transaction.id
#             invoice_id = transaction_data.get('invoiceId')

#             # Skip if invoice_id is missing
#             if not invoice_id:
#                 task_logger.warning(f"Transaction {transaction_id} has no invoice_id. Skipping.")
#                 continue

#             # Fetch the current status directly (no need for a txn argument)
#             current_status = transaction_data.get('status')
#             if current_status not in ['PENDING', 'PROCESSING']:
#                 task_logger.info(f"Transaction {transaction_id} already updated. Skipping.")
#                 continue

#             # Fetch status from the payment provider
#             try:
#                 response = requests.post(
#                     'https://sandbox.intasend.com/api/v1/payment/status/',
#                     json={'invoice_id': invoice_id},
#                     headers={'Authorization': f'Bearer {intasend_secret_api_key}'},
#                     timeout=10  # Set timeout for network requests
#                 )

#                 if response.status_code == 200:
#                     data = response.json()
#                     invoice = data.get('invoice', {})
#                     new_status = invoice.get('state')

#                     # Update Firestore document with the new status
#                     transaction.reference.update({'status': new_status})
#                     task_logger.info(f"Transaction {transaction_id} updated to {new_status}.")
#                 else:
#                     # Log error and retry if it's a recoverable error
#                     task_logger.error(f"Failed to fetch status for transaction {transaction_id}. "
#                                       f"Status Code: {response.status_code}, Response: {response.json()}")
#                     self.retry(exc=Exception(f"Error fetching status for {transaction_id}"))

#             except requests.exceptions.RequestException as req_exc:
#                 # Handle network-related errors gracefully
#                 task_logger.error(f"Network error while processing transaction {transaction_id}: {str(req_exc)}")
#                 self.retry(exc=req_exc)

#     except Exception as general_exc:
#         # Log general errors outside of individual transaction processing
#         task_logger.exception(f"General error in update_transaction_states task: {str(general_exc)}")