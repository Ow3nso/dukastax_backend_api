# ----- 3rd Party Libraries -----
import jwt
import os
import json
import uuid
import datetime
import subprocess
import requests

from decimal import Decimal
from django.apps import apps
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from google.cloud import firestore
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from dotenv import load_dotenv
from firebase_admin import auth

from intasend import APIService

# ----- In-Built Libraries -----
from .models import Transactions
from .serializers import *

# ----- API KEY Variables -----
intasend_secret_api_key = os.getenv('INTASEND_SECRET_API_KEY')
intasend_public_api_key = os.getenv('INTASEND_PUBLIC_API_KEY')

load_dotenv()

# ----- Time Formart Conversion -----
def convert_firestore_data(doc):
    data = doc.to_dict()
    if not data:
        return None

    # Convert any Firestore timestamp fields to ISO 8601 strings
    for key, value in data.items():
        if isinstance(value, dict) and 'seconds' in value and 'nanoseconds' in value:
            # Convert dict with 'seconds' and 'nanoseconds' to ISO 8601
            from datetime import datetime, timezone
            seconds = value['seconds']
            nanoseconds = value['nanoseconds']
            timestamp = datetime.fromtimestamp(seconds + nanoseconds / 1e9, tz=timezone.utc)
            data[key] = timestamp.isoformat()

    data['id'] = doc.id  # Add document ID to the data
    return data

# ----- Custom Date Json Encoder -----
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            # Option 1: Serialize as Unix timestamp
            return int(obj.timestamp())

            # Option 2: Serialize as ISO 8601 string without timezone
            # return obj.strftime('%Y-%m-%dT%H:%M:%S')

        return super().default(obj)

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


# ----- Views -----
class DepositView(FirebaseAuthenticationMixin, APIView):
    def post(self, request):
        try:
            # Get userId from Firebase JWT (from the authenticated user)
            firebase_user = request.firebase_user
            userId = firebase_user.get('uid')  # Access the 'uid' of the authenticated user

            if not userId:
                return Response({'error': 'userId is required'}, status=400)

            # Get request body data items
            amount = request.data.get('amount', 0)
            currency = request.data.get('currency')
            phone_number = request.data.get('phone_number')
            transaction_type = request.data.get('type')
            description = request.data.get('description')
            imageUrl = request.data.get('imageUrl')
            reference = request.data.get('reference')
            shopId = request.data.get('shopId')
            metadata = request.data.get('metadata')
            walletId = request.data.get('walletId')

            # Post request to IntaSend API
            response = requests.post(
                'https://sandbox.intasend.com/api/v1/payment/mpesa-stk-push/',
                json={
                    'amount': amount,
                    'payment_method': 'MOBILE_MONEY',
                    'phone_number': phone_number,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,  # Use userId from Firebase
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata': metadata,
                },
                headers={
                    'Authorization': f'Bearer {intasend_secret_api_key}'
                },
            )

            # Success response from IntaSend API
            if response.status_code == 200:
                data = response.json()
                transaction_id = data.get('id')
                invoice_id = data.get('invoice', {}).get('invoice_id')
                status = data.get('invoice', {}).get('state')
                createdAt = data.get('created_at')
                updatedAt = data.get('updated_at')

                # Save transaction details to Django database
                transaction = Transactions.objects.create(
                    id=transaction_id,
                    amount=amount,
                    phone_number=phone_number,
                    invoice_id=invoice_id,
                    status=status,
                    currency=currency,
                    type=transaction_type,
                    description=description,
                    imageUrl=imageUrl,
                    reference=reference,
                    userId=userId,  # Use userId from Firebase
                    shopId=shopId,
                    walletId=walletId,
                    metadata=metadata,
                )

                # Save to Firestore
                firestore_client = apps.get_app_config('payments').firestore_client
                firestore_client.collection('mytransactions').document(transaction_id).set({
                    'id': transaction_id,
                    'amount': str(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': status,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,  # Use userId from Firebase
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata': metadata,
                })

                # Return the response from IntaSend
                return Response(data, status=response.status_code)

            # Error response from IntaSend API
            else:
                return Response(response.json(), status=response.status_code)

        # General error handling
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProcessOrderView(FirebaseAuthenticationMixin, APIView):
    def post(self, request):
        try:
            firebase_user = request.firebase_user
            userId = firebase_user.get('uid')  # Access the 'uid' of the authenticated user

            if not userId:
                return Response({'error': 'userId is required'}, status=400)

            # get request body data items
            amount = request.data.get('amount', 0)
            currency = request.data.get('currency')
            phone_number = request.data.get('phone_number')
            transaction_type = request.data.get('type')
            description = request.data.get('description')
            imageUrl = request.data.get('imageUrl')
            reference = request.data.get('reference')
            shopId = request.data.get('shopId')
            metadata = request.data.get('metadata')
            walletId = request.data.get('walletId')
            # new order fields
            name = request.data.get('name')
            orderId = request.data.get('orderId')
            customerId = request.data.get('customerId')
            items = request.data.get('items')
            statusType = request.data.get('statusType')

            # Post Request
            response = requests.post(
                'https://sandbox.intasend.com/api/v1/payment/mpesa-stk-push/',
                json={
                    'amount': amount,
                    'payment_method': 'MOBILE_MONEY',
                    'phone_number': phone_number,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata': metadata,
                    # new order fields
                    'name':name,
                    'orderId':orderId,
                    'customerId':customerId,
                    'items':items,
                    'statusType':statusType,
                },
                headers={
                    'Authorization': f'Bearer {intasend_secret_api_key}'
                },
            )

            # Successfull Response
            if response.status_code == 200:
                data = response.json()
                transaction_id = data.get('id')
                invoice_id = data.get('invoice', {}).get('invoice_id')
                status = data.get('invoice', {}).get('state')
                createdAt = data.get('created_at')
                updatedAt = data.get('updated_at')

                # Save part of it to Firestore as transactions
                firestore_client = apps.get_app_config('payments').firestore_client
                firestore_client.collection('mytransactions').document(transaction_id).set({
                    'id':transaction_id,
                    'amount': str(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': status,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata':metadata,
                    # 'createdAt': createdAt,
                    # 'updatedAt':updatedAt
                })

                # Save to firestore as orders
                firestore_client = apps.get_app_config('payments').firestore_client
                firestore_client.collection('orders').document(transaction_id).set({
                    'id':transaction_id,
                    'amount': str(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': False,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata':metadata,
                    'name':name,
                    'orderId':orderId,
                    'customerId':customerId,
                    'items':items,
                    'statusType':"pending",
                    # 'createdAt': createdAt,
                    # 'updatedAt':updatedAt
                })

                return Response(data, status=response.status_code)
            # error handling
            else:
                return Response(response.json(), status=response.status_code)

        # error handling
        except Exception as e:
            raise e


# ----- Balance View -----
class BalanceView(FirebaseAuthenticationMixin, APIView):
    def get(self, request):
        try:
            # get userId
            firebase_user = request.firebase_user
            user_id = firebase_user.get('uid')  # Access the 'uid' of the authenticated user

            if not user_id:
                return Response({'error': 'userId is required'}, status=400)
            
            # Initialize Firestore client from Django app config
            firestore_client = apps.get_app_config('payments').firestore_client

            # Fetch all transactions from Firestore collection 'mytransactions'
            transactions_ref = firestore_client.collection('mytransactions')
            docs = transactions_ref.where(field_path='userId', op_string='==', value=user_id).stream()

            # Convert Firestore documents to a list of transaction dictionaries
            transactions = [doc.to_dict() for doc in docs]

            # Calculate the balance using the provided method
            availableBalance = (
                sum(float(transaction.get('amount', 0)) for transaction in transactions if transaction.get('status') == "COMPLETE" and transaction.get('metadata', {}).get('transaction') == "topup") -
                sum(float(transaction.get('amount', 0)) for transaction in transactions if transaction.get('status') == "COMPLETE" and transaction.get('metadata', {}).get('transaction') == "withdraw")
            )
            pendingBalance = (
                sum(float(transaction.get('amount', 0)) for transaction in transactions if transaction.get('status') == "COMPLETE" and transaction.get('metadata', {}).get('type') == "pending")
            )

            return Response(
                {
                    'availableBalance': availableBalance,
                    'pendingBalance':pendingBalance
                },
            )

        # error handling
        except Exception as e:
            raise e

# ----- Transactions View -----
class TransactionView(FirebaseAuthenticationMixin, APIView):
    def get(self, request):
        try:
            # Get the user's Firebase UID from the decoded token
            firebase_user = request.firebase_user
            user_id = firebase_user.get('uid')  # Correctly fetch the user UID

            if not user_id:
                return Response({'error': 'userId is required'}, status=400)

            # Access Firestore client
            firestore_client = apps.get_app_config('payments').firestore_client

            # Fetch transactions for the specific user
            transactions_ref = firestore_client.collection('mytransactions')
            docs = transactions_ref.where('userId', '==', user_id).stream()

            # Convert Firestore documents to a list of transaction dictionaries
            transactions = []
            for doc in docs:
                transaction_data = convert_firestore_data(doc)
                if transaction_data:
                    transaction_data['id'] = doc.id  # Add the document ID to the data
                    if transaction_data['status'] == "COMPLETE":
                        transactions.append(transaction_data)

            # Return all transactions with status "COMPLETE"
            return Response(transactions, status=status.HTTP_200_OK)

        # Error handling
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ----- withdraw from wallet -----
class WithdrawalView(FirebaseAuthenticationMixin, APIView):
    def post(self, request):
        # variables
        intasend_url = "https://api.intasend.com/api/v1/send-money/initiate/"

        # Get the withdrawal details from the request
        try:
            amount = Decimal(request.data.get('amount', '0'))  # Convert amount to Decimal
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount format."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the user's Firebase UID from the decoded token
        firebase_user = request.firebase_user
        userId = firebase_user.get('uid')  # Correctly fetch the user UID

        if not userId:
            return Response({'error': 'userId is required'}, status=400)

        id = uuid.uuid4()
        account = request.data.get('account')
        currency = request.data.get('currency')
        transaction_type = request.data.get('type')
        description = request.data.get('description')
        imageUrl = request.data.get('imageUrl')
        reference = request.data.get('reference')
        shopId = request.data.get('shopId')
        metadata = request.data.get('metadata')
        walletId = request.data.get('walletId')

        # Validation
        if not amount or not account:
            return Response(
                {"error": "Amount and phone number are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the payload for the withdrawal request
        payload = {
            "requires_approval": "NO",
            "currency": "KES",
            "provider": "MPESA-B2C",
            "transactions": [
                {
                    "amount": str(amount),
                    "account": account,
                }
            ]
        }

        # Define the headers including the API key
        headers = {
            "Authorization": f"Bearer {intasend_secret_api_key}",
            "Content-Type": "application/json"
        }

        # Start transaction
        try:
            transaction = Transactions.objects.create(
                amount=amount,
                currency=currency,
                phone_number=account,
                status='COMPLETE',
                type=transaction_type,
                description=description,
                imageUrl=imageUrl,
                reference=reference,
                userId=userId,
                shopId=shopId,
                walletId=walletId,
                metadata=metadata,
            )

            # Save transaction to Firestore\
            firestore_client = apps.get_app_config('payments').firestore_client
            firestore_client.collection('mytransactions').document(str(id)).set({
                'id':str(id),
                'amount': float(amount),
                'currency': currency,
                'phone_number': account,
                'status': 'COMPLETE',
                'type': transaction_type,
                'description': description,
                'imageUrl': imageUrl,
                'reference': reference,
                'userId': userId,
                'shopId': shopId,
                'walletId': walletId,
                'metadata': metadata,
            })

            # Make the request to IntaSend
            response = requests.post(intasend_url, json=payload, headers=headers)

            if response.status_code == 201:
                # transaction.status = 'COMPLETED'
                # Update the account balance
                # Fetch all transactions from Firestore collection 'mytransactions'
                # Get the user's Firebase UID from the decoded token
                firebase_user = request.firebase_user
                user_id = firebase_user.get('uid')  # Correctly fetch the user UID

                if not user_id:
                    return Response({'error': 'userId is required'}, status=400)
                
                transactions_ref = firestore_client.collection('mytransactions')
                docs = transactions_ref.where(field_path='userId', op_string='==', value=user_id).stream()

                # Convert Firestore documents to a list of transaction dictionaries
                transactions = [doc.to_dict() for doc in docs]

                # Calculate the balance using the provided method
                balance = (
                    sum(float(transaction.get('amount', 0)) for transaction in transactions if transaction.get('status') == "PENDING" and transaction.get('metadata', {}).get('transaction') == "topup") -
                    sum(float(transaction.get('amount', 0)) for transaction in transactions if transaction.get('status') == "PENDING" and transaction.get('metadata', {}).get('transaction') == "withdraw")
                )

                print(f"The balance is {balance}")
                # if balance < amount:
                #     transaction.state = 'FAILED'
                # else:
                #     balance -= amount
            else:
                transaction.state = 'FAILED'

            # Update Firestore document
            # firestore_client.collection('transactions').document(transaction_ref.id).update({
            #     'status': transaction.status,
            #     'state': transaction.state
            # })

            transaction.save()

            return Response(response.json(), status=response.status_code)
        except requests.exceptions.RequestException as e:
            transaction.status = 'FAILED'
            # Update Firestore document in case of failure
            # firestore_client.collection('transactions').document(transaction_ref.id).update({
            #     'status': transaction.status,
            #     'state': 'FAILED'
            # })
            transaction.save()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ----- Deposit with Card -----
class CardDepositView(FirebaseAuthenticationMixin, APIView):
    def post(self, request):
        # Prepare data for IntaSend API
        firebase_user = request.firebase_user
        userId = firebase_user.get('uid')  # Correctly fetch the user UID

        if not userId:
            return Response({'error': 'userId is required'}, status=400)
        
        amount = request.data.get('amount', 0)
        currency = request.data.get('currency')
        transaction_type = request.data.get('type')
        description = request.data.get('description')
        shopId = request.data.get('shopId')
        metadata = request.data.get('metadata')
        walletId = request.data.get('walletId')

        intasend_data = {
            'public_key': settings.INTASEND_API_KEY,
            "method": "CARD-PAYMENT",
            "currency": currency,
            'amount': amount,
            'type':  transaction_type,
            'description': description,
            'userId': userId,
            'shopId': shopId,
            'walletId': walletId,
            "metadata":metadata,
        }

        # Send request to IntaSend API
        response = requests.post("https://sandbox.intasend.com/api/v1/checkout/", json=intasend_data)

        if response.status_code == 201:
            data = response.json()
            id = data.get("id")
            transaction_id = str(id)

            # Save to Django's database
            transaction = Transactions.objects.create(
                id=transaction_id,
                amount=amount,
                status="PENDING",
                currency=currency,
                type=transaction_type,
                description=description,
                userId=userId,
                shopId=shopId,
                walletId=walletId,
                metadata=metadata,
            )

            # Save to Firestore
            firestore_client = apps.get_app_config('payments').firestore_client
            firestore_client.collection('mytransactions').document(transaction_id).set({
                'id':transaction_id,
                'amount': str(amount),
                'status': "PENDING",
                'currency': currency,
                'type': transaction_type,
                'description': description,
                'userId': userId,
                'shopId': shopId,
                'walletId': walletId,
                'metadata':metadata,

                # 'createdAt': createdAt,
                # 'updatedAt':updatedAt
            })
            return Response(data, status=response.status_code)

        else:
            return Response({
                'status': 'Payment Initiation failed',
                'detail': response.json(),
                'response_text': response.text
            }, status=response.status_code)

# Check if Card Deposit is Successfull
class CheckoutStatus(FirebaseAuthenticationMixin, APIView):
    def post(self, request):
        # prepare checkout details
        firebase_user = request.firebase_user
        user_id = firebase_user.get('uid')  # Correctly fetch the user UID

        if not user_id:
            return Response({'error': 'userId is required'}, status=400)

        checkout_id = request.data.get("checkout_id")
        signature = request.data.get("signature")

        # prepare json data
        intasend_data = {
            'public_key': settings.INTASEND_API_KEY,
            "checkout_id":"5d405859-ca38-4821-a95e-5d6553d1a9b3",
            "signature":"eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzY29wZSI6ImV4cHJlc3MtY2hlY2tvdXQiLCJpc3MiOiJJbnRhU2VuZCBTb2x1dGlvbnMgTGltaXRlZCIsImF1ZCI6WyI1ZDQwNTg1OS1jYTM4LTQ4MjEtYTk1ZS01ZDY1NTNkMWE5YjMiXSwiaWF0IjoxNzIzNTE1OTk4LCJleHAiOjE3MjM1MTk1OTgsImFjY291bnRJRCI6IlBRVzlERFEiLCJyZWZlcmVuY2UiOiI1ZDQwNTg1OS1jYTM4LTQ4MjEtYTk1ZS01ZDY1NTNkMWE5YjMifQ._Zhl9ZdMZ8mueoFlG9nr8DQEPkfjbFajDeypXhXOyRo"
        }

        # Send request to IntaSend API
        response = requests.post(
                        "https://sandbox.intasend.com/api/v1/checkout/details/",
                        json=intasend_data
                    )
        if response.status_code == 200:
            data = response.json()
            return Response(data, status=response.status_code)
        else:
            data = response.json()
            return Response(data, status=response.status_code)

class TransactionDetailView(FirebaseAuthenticationMixin, APIView):
    def get(self, request, transaction_id):
        try:
            firebase_user = request.firebase_user
            user_id = firebase_user.get('uid')  # Correctly fetch the user UID

            if not user_id:
                return Response({'error': 'userId is required'}, status=400)
                
            # Access Firestore client
            firestore_client = apps.get_app_config('payments').firestore_client

            # Fetch the specific transaction by transactionId
            transaction_ref = firestore_client.collection('mytransactions').document(transaction_id)
            doc = transaction_ref.get()

            # Check if document exists
            if not doc.exists:
                return Response({'error': 'Transaction not found'}, status=404)

            # Convert Firestore document to a transaction dictionary
            transaction = convert_firestore_data(doc)

            return Response(transaction, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=500)