# ----- 3rd Party Libraries -----
import os
import requests
import logging
from firebase_admin import firestore
from datetime import datetime
from celery import shared_task
from django.conf import settings
from dotenv import load_dotenv
from django.apps import apps
from celery.utils.log import get_task_logger

# ----- In-Built Libraries -----
from .models import Transactions

load_dotenv()
intasend_secret_api_key = os.getenv('INTASEND_SECRET_API_KEY')
intasend_public_api_key = os.getenv('INTASEND_PUBLIC_API_KEY')

logger = get_task_logger(__name__)

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

        # Fetch all PENDING or PROCESSING transactions with type 'M-PESA' in a single query
        card_query = transactions_ref.where('status', 'in', ['PENDING', 'PROCESSING']).where('type', '==', 'CARD')
        mpesa_query = transactions_ref.where('status', 'in', ['PENDING', 'PROCESSING']).where('type', '==', 'M-PESA')
        mpesa_transactions = mpesa_query.stream()
        card_transactions = card_query.stream()

        # Process transactions in bulk
        if mpesa_query:
            for transaction in mpesa_transactions:
                transaction_data = transaction.to_dict()
                transaction_id = transaction.id
                invoice_id = transaction_data.get('invoiceId')
                wallet_id = transaction_data.get('walletId')
                amount = float(transaction_data.get('amount', 0))
                description = transaction_data.get('description', '')

                # Skip if invoice_id or wallet_id is missing
                if not invoice_id or not wallet_id:
                    logger.warning(f"Transaction {transaction_id} has no invoice_id or wallet_id. Skipping.")
                    continue

                # Fetch status from the payment provider
                try:
                    response = requests.post(
                        'https://sandbox.intasend.com/api/v1/payment/status/',
                        json={'invoice_id': invoice_id},
                        headers={'Authorization': f'Bearer {intasend_secret_api_key}'},
                        timeout=5  # Reduce timeout to 5 seconds
                    )

                    if response.status_code == 200:
                        data = response.json()
                        invoice = data.get('invoice', {})
                        new_status = invoice.get('state')

                        # Update Firestore document with the new status
                        transaction.reference.update({'status': new_status})
                        logger.warning(f"Transaction {transaction_id} updated to {new_status}.")

                        # If the transaction is completed, update the wallet balance in Firestore
                        if new_status == 'COMPLETE':
                            wallet_ref = firestore_client.collection('wallet').document(wallet_id)
                            wallet_doc = wallet_ref.get()

                            if wallet_doc.exists:
                                wallet_data = wallet_doc.to_dict()
                                current_balance = float(wallet_data.get('balance', 0))
                                current_available_balance = float(wallet_data.get('availableBalance', 0))
                                current_pending_balance = float(wallet_data.get('pendingBalance', 0))

                                # Update the wallet balance and availableBalance (existing logic)
                                new_balance = current_balance + amount
                                new_available_balance = current_available_balance + amount

                                # Update the pendingBalance only if the description is "Bought Item"
                                if description == "Bought Item":
                                    new_pending_balance = current_pending_balance + amount
                                    wallet_ref.update({'pendingBalance': new_pending_balance})
                                    logger.warning(f"Wallet {wallet_id} pendingBalance updated to {new_pending_balance}.")

                                # Update the wallet balance and availableBalance (existing logic)
                                wallet_ref.update({
                                    'balance': new_balance,
                                    'availableBalance': new_available_balance
                                })
                                logger.warning(f"Wallet {wallet_id} balance updated to {new_balance} and availableBalance updated to {new_available_balance}.")
                            else:
                                logger.warning(f"Wallet {wallet_id} not found in Firestore.")
                    else:
                        logger.warning(f"Failed to fetch status for transaction {transaction_id}. "
                                    f"Status Code: {response.status_code}, Response: {response.json()}")
                except requests.exceptions.RequestException as req_exc:
                    logger.warning(f"Network error while processing transaction {transaction_id}: {str(req_exc)}")
        elif card_query:
            for transaction in card_transactions:
                transaction_data = transaction.to_dict()
                transaction_id = transaction.id
                invoice_id = transaction_data.get('invoiceId')
                wallet_id = transaction_data.get('walletId')
                amount = float(transaction_data.get('amount', 0))
                description = transaction_data.get('description', '')

                # Skip if invoice_id or wallet_id is missing
                if not invoice_id or not wallet_id:
                    logger.warning(f"Transaction {transaction_id} has no invoice_id or wallet_id. Skipping.")
                    continue

                # Fetch status from the payment provider
                try:
                    response = requests.post(
                        "https://sandbox.intasend.com/api/v1/checkout/details/",
                        headers={
                            'X-IntaSend-Public-API-Key': intasend_public_api_key,
                            'accept': 'application/json',
                            'content-type': 'application/json',
                        },
                        json={
                            'checkout_id': transaction_id,
                            'signature': invoice_id
                    }
                    )

                    if response.status_code == 200:
                        data = response.json()
                        paid = data.get("paid", False)

                        if paid:

                            # Update Firestore document with the new status
                            transaction.reference.update({'status': 'COMPLETE'})
                            transaction_status = transaction.reference.update({'status': 'COMPLETE'})
                            logger.warning(f"Transaction {transaction_id} updated to complete.")

                            # If the transaction is completed, update the wallet balance in Firestore
                            if transaction_status == 'COMPLETE':
                                wallet_ref = firestore_client.collection('wallet').document(wallet_id)
                                wallet_doc = wallet_ref.get()

                                if wallet_doc.exists:
                                    wallet_data = wallet_doc.to_dict()
                                    current_balance = float(wallet_data.get('balance', 0))
                                    current_available_balance = float(wallet_data.get('availableBalance', 0))
                                    current_pending_balance = float(wallet_data.get('pendingBalance', 0))

                                    # Update the wallet balance and availableBalance (existing logic)
                                    new_balance = current_balance + amount
                                    new_available_balance = current_available_balance + amount

                                    # Update the pendingBalance only if the description is "Bought Item"
                                    if description == "Bought Item":
                                        new_pending_balance = current_pending_balance + amount
                                        wallet_ref.update({'pendingBalance': new_pending_balance})
                                        logger.warning(f"Wallet {wallet_id} pendingBalance updated to {new_pending_balance}.")

                                    # Update the wallet balance and availableBalance (existing logic)
                                    wallet_ref.update({
                                        'balance': new_balance,
                                        'availableBalance': new_available_balance
                                    })
                                    logger.warning(f"Wallet {wallet_id} balance updated to {new_balance} and availableBalance updated to {new_available_balance}.")
                                else:
                                    logger.warning(f"Wallet {wallet_id} not found in Firestore.")
                    else:
                        logger.warning(f"Failed to fetch status for transaction {transaction_id}. "
                                    f"Status Code: {response.status_code}, Response: {response.json()}")
                except requests.exceptions.RequestException as req_exc:
                    logger.warning(f"Network error while processing transaction {transaction_id}: {str(req_exc)}")

    except Exception as general_exc:
        logger.error(f"General error in update_transaction_states task: {str(general_exc)}")


# @shared_task(bind=True)
# def check_transaction_status(self, checkout_id, signature, wallet_id, amount):
#     try:
#         firestore_client = firestore.client()
#         transaction_ref = firestore_client.collection('mytransactions').document(checkout_id)
#         transaction_doc = transaction_ref.get()

#         if transaction_doc.exists:
#             transaction_data = transaction_doc.to_dict()
#             transaction_type = transaction_data.get('type')

#             # Only proceed if the transaction type is 'CARD'
#             if transaction_type == 'CARD':
#                 # Fetch transaction status from IntaSend API
#                 response = requests.post(
#                     "https://sandbox.intasend.com/api/v1/checkout/details/",
#                     headers={
#                         'X-IntaSend-Public-API-Key': intasend_public_api_key,
#                         'accept': 'application/json',
#                         'content-type': 'application/json',
#                     },
#                     json={
#                         'checkout_id': checkout_id,
#                         'signature': signature
#                     }
#                 )

#                 print(f"API Response Status Code: {response.status_code}")

#                 if response.status_code == 200:
#                     data = response.json()
#                     paid = data.get("paid", False)

#                     print(data)

#                     if paid:
#                         # Update transaction status to COMPLETE
#                         transaction_ref.update({
#                             'status': 'COMPLETE',
#                             'updatedAt': datetime.now().isoformat(),
#                         })

#                         # Update wallet balance
#                         wallet_ref = firestore_client.collection('wallet').document(wallet_id)
#                         wallet_doc = wallet_ref.get()

#                         if wallet_doc.exists:
#                             wallet_data = wallet_doc.to_dict()
#                             current_balance = float(wallet_data.get('balance', 0))
#                             new_balance = current_balance + amount

#                             # Update wallet balance in Firestore
#                             wallet_ref.update({
#                                 'availableBalance': new_balance,
#                                 'balance': new_balance
#                             })
#                             print(f"Wallet {wallet_id} balance updated to {new_balance}.")
#                         else:
#                             print(f"Wallet {wallet_id} not found in Firestore.")
#                     else:
#                         # Retry the task with exponential backoff
#                         raise self.retry(countdown=2 ** self.request.retries, max_retries=5)
#                 elif response.status_code == 429:
#                     # Handle rate limiting by adding a delay before retrying
#                     retry_after = int(response.headers.get('Retry-After', 10))  # Default to 10 seconds if header is missing
#                     print(f"Rate limit exceeded. Retrying after {retry_after} seconds.")
#                     raise self.retry(countdown=retry_after, max_retries=5)
#                 else:
#                     print(f"Failed to fetch status for checkout {checkout_id}. Status Code: {response.status_code}")
#                     raise self.retry(countdown=2 ** self.request.retries, max_retries=5)
#             else:
#                 print(f"Transaction {checkout_id} is not of type 'CARD'. Skipping.")
#         else:
#             print(f"Transaction {checkout_id} not found in Firestore.")
#     except Exception as e:
#         if self.request.retries == self.max_retries:
#             # Mark the transaction as failed after retries are exhausted
#             transaction_ref.update({
#                 'status': 'FAILED',
#                 'updatedAt': datetime.now().isoformat(),
#             })
#             print(f"Max retries exceeded for checkout {checkout_id}. Marking as FAILED.")
#         else:
#             print(f"Error in check_transaction_status task: {str(e)}")
#             raise self.retry(countdown=2 ** self.request.retries, max_retries=5)    



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