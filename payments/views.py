# ----- 3rd Party Libraries -----
import jwt
import os
import json
import uuid
import datetime
import subprocess
import requests
import logging
import random
from datetime import datetime

from decimal import Decimal
from django.apps import apps
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta, datetime
from google.protobuf.timestamp_pb2 import Timestamp
from google.cloud import firestore
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from dotenv import load_dotenv
from firebase_admin import auth
from datetime import datetime  # Ensure datetime is imported

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

from intasend import APIService

# ----- In-Built Libraries -----
# from .tasks import check_transaction_status
from .models import Transactions
from .serializers import *

# ----- API KEY Variables -----
intasend_secret_api_key = os.getenv('INTASEND_SECRET_API_KEY')
intasend_public_api_key = os.getenv('INTASEND_PUBLIC_API_KEY')
FIREBASE_WEB_API_KEY = os.getenv('FIREBASE_WEB_API_KEY')

load_dotenv()

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the logging level

# Create a console handler and set the level to DEBUG
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)

def generate_swagger_schema(
    operation_description, 
    request_fields=None, 
    required_request_fields=None, 
    response_fields=None, 
    response_example=None
):
    """
    Generate a reusable Swagger schema decorator.

    Args:
        operation_description (str): Description of the operation.
        request_fields (dict): Request body fields with details.
        required_request_fields (list, optional): List of required request fields. Defaults to [].
        response_fields (dict, optional): Response body fields with details. Defaults to None.
        response_example (dict, optional): Example of the response body. Defaults to None.

    Returns:
        swagger_auto_schema: A DRF-YASG schema decorator.
    """
    required_request_fields = required_request_fields or []
    
    # Create request properties
    request_properties = {
        field_name: openapi.Schema(**field_details)
        for field_name, field_details in (request_fields or {}).items()
    }
    
    # Create response schema
    response_schema = None
    if response_fields:
        response_properties = {
            field_name: openapi.Schema(**field_details)
            for field_name, field_details in response_fields.items()
        }
        response_schema = openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties=response_properties,
        )
    
    return swagger_auto_schema(
        operation_description=operation_description,
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties=request_properties,
            required=required_request_fields,
        ) if request_fields else None,
        responses={
            200: openapi.Response(
                description="Success",
                schema=response_schema,
                examples={"application/json": response_example} if response_example else None
            ),
            201: "Created",
            400: "Bad Request",
            401: "Unauthorized",
        }
    )



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

class TransactionPagination(PageNumberPagination):
    page_size = 10  # Number of transactions per page
    page_size_query_param = 'page_size'  # Allow client to override the page size
    max_page_size = 100  # Maximum limit for page size

def calculate_income_overview(transactions, start_date, end_date, availableBalance):
    # Filter transactions within the specified period and with valid timestamps
    filtered_transactions = []
    for t in transactions:
        if t.get('createdAt') is not None:
            # Convert createdAt to datetime if it is a string in ISO 8601 format
            if isinstance(t['createdAt'], str):
                try:
                    t['createdAt'] = datetime.fromisoformat(t['createdAt'])
                except ValueError as e:
                    logger.warning(f"Failed to parse createdAt: {t['createdAt']}. Error: {e}")
                    continue  # Skip this transaction if parsing fails

            # Ensure createdAt is a datetime object
            if isinstance(t['createdAt'], datetime):
                if start_date <= t['createdAt'] <= end_date:
                    filtered_transactions.append(t)
            else:
                logger.warning(f"Invalid createdAt type: {type(t['createdAt'])}. Expected datetime.")

    # Calculate total top-ups and withdrawals
    total_topups = sum(
        float(t.get('amount', 0)) for t in filtered_transactions
        if t.get('status') == "COMPLETE" and t.get('metadata', {}).get('transaction') == "topup"
    )
    total_withdrawals = sum(
        float(t.get('amount', 0)) for t in filtered_transactions
        if t.get('status') == "COMPLETE" and t.get('metadata', {}).get('transaction') == "withdraw"
    )

    # Calculate net change in available balance
    net_change = availableBalance - sum(
        float(t.get('amount', 0)) for t in filtered_transactions
        if t.get('status') == "COMPLETE" and t.get('metadata', {}).get('transaction') == "topup"
    )

    # Income overview formula
    income_overview = (net_change + total_withdrawals) - total_topups
    
    # Prepare chart data based on period
    period_days = (end_date - start_date).days
    chart_data = {}
    
    if period_days == 0:  # Today - hourly data
        hourly_data = {str(hour): {
            'available': 0.0,
            'pending': 0.0,
            'topups': 0.0,
            'withdrawals': 0.0
        } for hour in range(24)}
        
        for t in filtered_transactions:
            hour = t['createdAt'].hour
            amount = float(t.get('amount', 0))
            status = t.get('status')
            transaction_type = t.get('metadata', {}).get('transaction')
            
            if status == "COMPLETE":
                if transaction_type == "topup":
                    hourly_data[str(hour)]['available'] += amount
                    hourly_data[str(hour)]['topups'] += amount
                elif transaction_type == "withdraw":
                    hourly_data[str(hour)]['available'] -= amount
                    hourly_data[str(hour)]['withdrawals'] += amount
            elif status == "PENDING":
                hourly_data[str(hour)]['pending'] += amount
        
        chart_data = {
            'type': 'hourly',
            'data': hourly_data
        }
        
    elif period_days <= 7:  # Weekly data
        daily_data = {str(day): {
            'available': 0.0,
            'pending': 0.0,
            'topups': 0.0,
            'withdrawals': 0.0
        } for day in range(7)}  # 0=Monday to 6=Sunday
        
        for t in filtered_transactions:
            day = t['createdAt'].weekday()  # Monday=0, Sunday=6
            amount = float(t.get('amount', 0))
            status = t.get('status')
            transaction_type = t.get('metadata', {}).get('transaction')
            
            if status == "COMPLETE":
                if transaction_type == "topup":
                    daily_data[str(day)]['available'] += amount
                    daily_data[str(day)]['topups'] += amount
                elif transaction_type == "withdraw":
                    daily_data[str(day)]['available'] -= amount
                    daily_data[str(day)]['withdrawals'] += amount
            elif status == "PENDING":
                daily_data[str(day)]['pending'] += amount
        
        chart_data = {
            'type': 'daily',
            'data': daily_data
        }
    
    # Calculate comparison percentage (simple example)
    comparison_percentage = 0.0
    if total_topups > 0:
        comparison_percentage = ((income_overview - total_topups) / total_topups) * 100
        comparison_text = f"{abs(comparison_percentage):.1f}% {'higher' if comparison_percentage >= 0 else 'lower'} than last period"
    else:
        comparison_text = "No comparison available"

    return {
        'income_overview': income_overview,
        'income_comparison': comparison_text,
        'chart_data': chart_data,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'available_balance': availableBalance,
        'pending_balance': sum(
            float(t.get('amount', 0)) for t in filtered_transactions
            if t.get('status') == "PENDING"
        ),
        'total_topups': total_topups,
        'total_withdrawals': total_withdrawals
    }

@csrf_exempt
def signup(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")
            display_name = data.get("display_name", "")

            if not email or not password:
                return JsonResponse({"error": "Email and password are required"}, status=400)

            # Create user in Firebase
            user = auth.create_user(email=email, password=password, display_name=display_name)

            return JsonResponse({"message": "User created successfully", "uid": user.uid}, status=201)
        
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
def login(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            email = data.get("email")
            password = data.get("password")

            if not email or not password:
                return JsonResponse({"error": "Email and password are required"}, status=400)

            # Firebase REST API endpoint for signing in users
            url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
            payload = {
                "email": email,
                "password": password,
                "returnSecureToken": True
            }
            headers = {"Content-Type": "application/json"}

            # Send POST request to Firebase Authentication REST API
            response = requests.post(url, data=json.dumps(payload), headers=headers)
            result = response.json()

            if "idToken" in result:
                return JsonResponse({
                    "message": "Login successful",
                    "idToken": result["idToken"],
                    "refreshToken": result["refreshToken"],
                    "expiresIn": result["expiresIn"]
                }, status=200)
            else:
                return JsonResponse({"error": result.get("error", "Invalid credentials")}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "Invalid request method"}, status=405)


class DepositView(FirebaseAuthenticationMixin, APIView):

    @generate_swagger_schema(
        operation_description="Wallet mobile money deposit endpoint",
        request_fields={
            'amount': {'type': openapi.TYPE_INTEGER,'description': "Amount to be deposited into the account"},
            'currency': {'type': openapi.TYPE_STRING,'description': "KES"},
            'phone_number': {'type': openapi.TYPE_INTEGER,'description': "Users phone number to enable stk push"},
            'transaction_type': {'type': openapi.TYPE_STRING,'description': "Can either be by M-PESA or CARD"},
            'description': {'type': openapi.TYPE_STRING, 'description': "Description / reason for example topup",},
            'shopId': {'type': openapi.TYPE_STRING, 'description': "User's ShopId",},
            'metadata': {
                'type': openapi.TYPE_ARRAY,
                'description': "An array of values for example transaction top up",
                'items': openapi.Items(type=openapi.TYPE_STRING),
            },
            'walletId': {'type': openapi.TYPE_STRING, 'description': "Users WalletId"},
            'userId': {'type': openapi.TYPE_STRING,'description': "Unique identification of the user"},
            
        },
        required_request_fields=['userId', 'walletId', 'shopId', 'amount', 'phone_number', 'transaction_type', 'currency'],
        response_example={
            "id": 1,
            "amount": "5",
            "currency": "KES",
            "description":"Top Up",
            "invoiceId": "YSHGD67",
            "phone_number":"25472345678",
            "status":"COMPLETE",
            "metadata": {"transaction":"topup"},
            "transcation_type":"M-PESA",
            "userId":"1",
            "walletId":"1",
            "shopId":"1",
            "newBalance": 1000,  # Add newBalance to the response example
        }
    )

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
                # transaction = Transactions.objects.create(
                #     id=transaction_id,
                #     amount=amount,
                #     phone_number=phone_number,
                #     invoice_id=invoice_id,
                #     status=status,
                #     currency=currency,
                #     type=transaction_type,
                #     description=description,
                #     imageUrl=imageUrl,
                #     reference=reference,
                #     userId=userId,  # Use userId from Firebase
                #     shopId=shopId,
                #     walletId=walletId,
                #     metadata=metadata,
                # )

                # Fetch the wallet document from Firestore
                firestore_client = apps.get_app_config('payments').firestore_client

                # Get the current timestamp in ISO format
                created_at_iso = datetime.now().isoformat()

                # Parse and format the timestamp
                created_at_datetime = datetime.fromisoformat(created_at_iso)
                formatted_created_at = created_at_datetime.strftime("%B %d, %Y at %I:%M:%S")
                # formatted_created_at = formatted_created_at.replace("+0300", "+3")

                # Save to Firestore
                firestore_client.collection('mytransactions').document(transaction_id).set({
                    'id': transaction_id,
                    'amount': float(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': 'COMPLETE',
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    'userId': userId,  # Use userId from Firebase
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata': metadata,
                    'createdAt': formatted_created_at,
                    # 'updatedAt': firestore.SERVER_TIMESTAMP,
                })

                # Return the response from IntaSend with newBalance
                return Response({
                    **data,
                    # 'newBalance': new_balance  # Include the new balance in the response
                }, status=response.status_code)

            # Error response from IntaSend API
            else:
                return Response(response.json(), status=response.status_code)

        # General error handling
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProcessOrderView(APIView):
    @generate_swagger_schema(
        operation_description="API endpoint to process order payment and checkout through mobile money stk push",
        request_fields={
            'amount': {'type': openapi.TYPE_INTEGER,'description': "Amount to be deposited into the account"},
            'currency': {'type': openapi.TYPE_STRING,'description': "KES"},
            'phone_number': {'type': openapi.TYPE_INTEGER,'description': "Users phone number to enable stk push"},
            'transaction_type': {'type': openapi.TYPE_STRING,'description': "Can either be by M-PESA or CARD"},
            'description': {'type': openapi.TYPE_STRING, 'description': "Description / reason for example topup",},
            'shopId': {'type': openapi.TYPE_STRING, 'description': "User's ShopId",},
            'metadata': {
                'type': openapi.TYPE_ARRAY,
                'description': "An array of values for example transaction top up",
                'items': openapi.Items(type=openapi.TYPE_STRING),
            },
            'imageUrl': {'type': openapi.TYPE_STRING, 'description': "Image of the item being ordered"},
            'walletId': {'type': openapi.TYPE_STRING, 'description': "Users WalletId"},
            'userId': {'type': openapi.TYPE_STRING,'description': "Unique identification of the user"},
            'name': {'type': openapi.TYPE_STRING, 'description': "Full name of the customer"},
            'customerId': {'type': openapi.TYPE_STRING, 'description': "Customer unique id"},
            'items': {'type': openapi.TYPE_STRING, 'description': "Users WalletId"},
            'statusType': {'type': openapi.TYPE_STRING, 'description': "The status of a transcation / order payment which can either be pending, ontransit, delivered, etc"},
        },
        # required_request_fields=lambda fields: list(fields.keys()),
        response_example={
            "id": 1,
            "transctionId":"1",
            "amount": "5",
            "currency": "KES",
            "description":"Top Up",
            "invoiceId": "YSHGD67",
            "phone_number":"25472345678",
            "status":"COMPLETE",
            "metadata": {"type":"pending"},
            "imageUrl":"https://image.com/",
            "transcation_type":"M-PESA",
            "userId":"1",
            "walletId":"1",
            "shopId":"1",
            "name":"James Doe",
            "orderId":"LUKHU-270325-0045",
            "customerId":"1",
            "statusType":"pending"
        }
    )
    def post(self, request):
        try:
            # firebase_user = request.firebase_user
            # userId = firebase_user.get('uid')  # Access the 'uid' of the authenticated user

            #if not userId:
             #   return Response({'error': 'userId is required'}, status=400)

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
            customerId = request.data.get('customerId')
            items = request.data.get('items')
            statusType = request.data.get('statusType')

            # Generate unique order ID
            current_date = datetime.now().strftime("%d%m%y")  # DDMMYY format
            random_code = f"{random.randint(0, 9999):04d}"  # 4-digit random number with leading zeros
            orderId = f"LUKHU-{current_date}-{random_code}"

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
                    # 'userId': userId,
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

                # Get the current timestamp in ISO format
                created_at_iso = datetime.now().isoformat()

                # Parse and format the timestamp
                created_at_datetime = datetime.fromisoformat(created_at_iso)
                formatted_created_at = created_at_datetime.strftime("%B %d, %Y at %I:%M:%S")

                # Save part of it to Firestore as transactions
                firestore_client = apps.get_app_config('payments').firestore_client
                firestore_client.collection('mytransactions').document(transaction_id).set({
                    'id':transaction_id,
                    'amount': float(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': 'COMPLETE',
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    # 'userId': userId,
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata':metadata,
                    'createdAt':formatted_created_at,
                    # 'updatedAt':firestore.SERVER_TIMESTAMP
                })

                # Save to firestore as orders
                firestore_client = apps.get_app_config('payments').firestore_client
                firestore_client.collection('orders').document(transaction_id).set({
                    'id':transaction_id,
                    'amount': float(amount),  # Firestore does not support Decimal, so convert to string
                    'phone_number': phone_number,
                    'invoiceId': invoice_id,
                    'status': False,
                    'currency': currency,
                    'type': transaction_type,
                    'description': description,
                    'imageUrl': imageUrl,
                    'reference': reference,
                    # 'userId': userId,
                    'shopId': shopId,
                    'walletId': walletId,
                    'metadata':metadata,
                    'name':name,
                    'orderId':orderId,
                    'customerId':customerId,
                    'items':items,
                    'statusType':"pending",
                    'createdAt': firestore.SERVER_TIMESTAMP,
                    # 'updatedAt':created_at_iso
                })

                return Response(data, status=response.status_code)
            # error handling
            else:
                return Response(response.json(), status=response.status_code)

        # error handling
        except Exception as e:
            raise e

# ---------------------Balance View ---------
class BalanceView(FirebaseAuthenticationMixin, APIView):
    @generate_swagger_schema(
        operation_description="API endpoint to request and check the available and pending balance of a user, and calculate income overview for a specific period.",
        response_example={
            "userId": "1",
            "walletId": "1",
            "shopId": "1",
            "availableBalance": 2000.00,
            "pendingBalance": 500.00,
            "currency": "KES",
            "incomeOverview": 1000.00,
            "incomeComparison": "14% higher than last week",
        }
    )
    def get(self, request):
        try:
            # Get userId
            firebase_user = request.firebase_user
            user_id = firebase_user.get('uid')  # Access the 'uid' of the authenticated user

            if not user_id:
                return Response({'error': 'userId is required'}, status=400)

            # Log user ID
            logger.info(f"User ID: {user_id}")

            # Get the period from query parameters
            period = request.query_params.get('period', 'today')  # Default to 'today'
            custom_start_date = request.query_params.get('start_date')
            custom_end_date = request.query_params.get('end_date')

            # Log period and custom dates
            logger.info(f"Period: {period}")
            logger.info(f"Custom Start Date: {custom_start_date}")
            logger.info(f"Custom End Date: {custom_end_date}")

            # Initialize Firestore client from Django app config
            firestore_client = apps.get_app_config('payments').firestore_client

            # Fetch all transactions from Firestore collection 'mytransactions'
            transactions_ref = firestore_client.collection('mytransactions')
            docs = transactions_ref.where(field_path='userId', op_string='==', value=user_id).stream()

            # Convert Firestore documents to a list of transaction dictionaries, filtering out None values
            transactions = [doc.to_dict() for doc in docs if doc.to_dict() is not None]

            # Log transactions after filtering
            logger.info(f"Transactions after filtering: {transactions}")

            # Check for missing timestamps
            for transaction in transactions:
                if transaction.get('createdAt') is None:
                    logger.warning(f"Transaction missing timestamp: {transaction}")

            # Convert Firestore Timestamp to Python datetime if necessary
            for transaction in transactions:
                if isinstance(transaction.get('createdAt'), Timestamp):  # Correct isinstance check
                    transaction['createdAt'] = transaction['createdAt'].to_pydatetime()

            # Calculate available and pending balances
            availableBalance = (
                sum(float(transaction.get('amount', 0)) for transaction in transactions 
                if transaction.get('status') == "COMPLETE" 
                and transaction.get('metadata', {}).get('transaction') == "topup"
            )) - (
                sum(float(transaction.get('amount', 0)) for transaction in transactions 
                if transaction.get('status') == "COMPLETE" 
                and transaction.get('metadata', {}).get('transaction') == "withdraw")
            )

            pendingBalance = (
                sum(float(transaction.get('amount', 0)) for transaction in transactions 
                if transaction.get('status') == "PENDING"
            ))

            # Log balances
            logger.info(f"Available Balance: {availableBalance}")
            logger.info(f"Pending Balance: {pendingBalance}")

            # Helper function to calculate start and end dates based on the period
            def get_date_range(period, custom_start_date=None, custom_end_date=None):
                now = timezone.now()
                if period == 'today':
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = now
                elif period == 'yesterday':
                    start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                elif period == 'this_week':
                    start_date = now - timedelta(days=now.weekday())
                    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = now
                elif period == 'last_7_days':
                    start_date = now - timedelta(days=7)
                    end_date = now
                elif period == 'last_30_days':
                    start_date = now - timedelta(days=30)
                    end_date = now
                elif period == 'last_6_months':
                    start_date = now - timedelta(days=180)
                    end_date = now
                elif period == 'last_1_year':
                    start_date = now - timedelta(days=365)
                    end_date = now
                elif period == 'custom' and custom_start_date and custom_end_date:
                    start_date = datetime.strptime(custom_start_date, '%Y-%m-%d')
                    end_date = datetime.strptime(custom_end_date, '%Y-%m-%d')
                else:
                    raise ValueError("Invalid period or missing custom date range")

                return start_date, end_date

            # Get date range for the specified period
            start_date, end_date = get_date_range(period, custom_start_date, custom_end_date)

            # Log date range
            logger.info(f"Start Date: {start_date}")
            logger.info(f"End Date: {end_date}")

            # Calculate income overview for the specified period
            income_overview = calculate_income_overview(transactions, start_date, end_date, availableBalance)

            # Log income overview
            logger.info(f"Income Overview: {income_overview}")

            return Response(
                {
                    'availableBalance': availableBalance,
                    'pendingBalance': pendingBalance,
                    'incomeOverview': income_overview,
                    'period': period,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                },
            )

        # Error handling
        except Exception as e:
            logger.error(f"Error in BalanceView: {str(e)}", exc_info=True)
            return Response({'error': str(e)}, status=400)

# ----- Transactions View -----
class TransactionView(FirebaseAuthenticationMixin, APIView):
    pagination_class = TransactionPagination

    @generate_swagger_schema(
        operation_description="API endpoint to get all the transactions performed by a user",
        response_example={
            "id": 1,
            "transactionId": "1",
            "amount": "5",
            "currency": "KES",
            "description": "Top Up",
            "invoiceId": "YSHGD67",
            "phone_number": "25472345678",
            "status": "COMPLETE",
            "metadata": {"type": "pending"},
            "imageUrl": "https://image.com/",
            "transaction_type": "M-PESA",
            "userId": "1",
            "walletId": "1",
            "shopId": "1",
            "name": "James Doe",
            "orderId": "1",
            "customerId": "1",
            "statusType": "pending"
        }
    )
    def get(self, request):
        try:
            # Get the user's Firebase UID from the decoded token
            firebase_user = request.firebase_user
            user_id = firebase_user.get('uid')  # Correctly fetch the user UID

            if not user_id:
                return Response({'error': 'userId is required'}, status=status.HTTP_400_BAD_REQUEST)

            # Access Firestore client
            firestore_client = apps.get_app_config('payments').firestore_client

            # First, get all wallets belonging to this user
            wallets_ref = firestore_client.collection('wallet')
            wallet_docs = wallets_ref.where('userId', '==', user_id).stream()
            
            # Get all wallet IDs for this user
            wallet_ids = [wallet.id for wallet in wallet_docs]
            
            if not wallet_ids:
                return Response({'message': 'No wallets found for this user'}, status=status.HTTP_404_NOT_FOUND)

            # Fetch transactions for the user's wallets
            transactions_ref = firestore_client.collection('mytransactions')
            
            # Create a query for transactions where walletId is in the user's wallet IDs
            docs = transactions_ref.where('walletId', 'in', wallet_ids).stream()

            # Convert Firestore documents to a list of transaction dictionaries
            transactions = []
            for doc in docs:
                transaction_data = convert_firestore_data(doc)
                if transaction_data:
                    transaction_data['id'] = doc.id  # Add the document ID to the data
                    if transaction_data['status'] == "COMPLETE":
                        transactions.append(transaction_data)

            # Sort transactions by createdAt in descending order (newest first)
            transactions.sort(key=lambda x: datetime.strptime(x['createdAt'], '%B %d, %Y at %H:%M:%S'), reverse=True)

            # Paginate the transactions
            paginator = self.pagination_class()
            paginated_transactions = paginator.paginate_queryset(transactions, request)

            # Return paginated transactions
            return paginator.get_paginated_response(paginated_transactions)

        # Error handling
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ----- withdraw from wallet -----
class WithdrawalView(FirebaseAuthenticationMixin, APIView):
    @generate_swagger_schema(
        operation_description="API endpoint to make a withdrawal request",
        request_fields={
            'amount': {'type': openapi.TYPE_INTEGER,'description': "Amount to be deposited into the account"},
            'currency': {'type': openapi.TYPE_STRING,'description': "KES"},
            'account': {'type': openapi.TYPE_INTEGER,'description': "Users phone number to enable stk push"},
            'transaction_type': {'type': openapi.TYPE_STRING,'description': "M-PESA"},
            'description': {'type': openapi.TYPE_STRING, 'description': "Description / reason for example Withdrawal",},
            'shopId': {'type': openapi.TYPE_STRING, 'description': "User's ShopId",},
            'metadata': {
                'type': openapi.TYPE_ARRAY,
                'description': "An array of values for example transaction withdrawal",
                'items': openapi.Items(type=openapi.TYPE_STRING),
            },
            'walletId': {'type': openapi.TYPE_STRING, 'description': "Users WalletId"},
            'userId': {'type': openapi.TYPE_STRING,'description': "Unique identification of the user"},
            
        },
        # required_request_fields=['userId', 'walletId', 'shopId', 'amount', 'phone_number', 'transaction_type', 'currency'],
        response_example={
            "id": 1,
            "amount": "15",
            "currency": "KES",
            "description":"Withdrawal",
            "invoiceId": "YSHGD67",
            "account":"25472345678",
            "status":"COMPLETE",
            "metadata": {"transaction":"withdraw"},
            "transcation_type":"M-PESA",
            "userId":"1",
            "walletId":"1",
            "shopId":"1",
        }
    )
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
            # transaction = Transactions.objects.create(
            #     amount=amount,
            #     currency=currency,
            #     phone_number=account,
            #     status='COMPLETE',
            #     type=transaction_type,
            #     description=description,
            #     imageUrl=imageUrl,
            #     reference=reference,
            #     userId=userId,
            #     shopId=shopId,
            #     walletId=walletId,
            #     metadata=metadata,
            # )

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
    @generate_swagger_schema(
        operation_description="Wallet Card deposit endpoint",
        request_fields={
            'amount': {'type': openapi.TYPE_INTEGER,'description': "Amount to be deposited into the account"},
            'currency': {'type': openapi.TYPE_STRING,'description': "KES"},
            'transaction_type': {'type': openapi.TYPE_STRING,'description': "CARD-PAYMENT"},
            'description': {'type': openapi.TYPE_STRING, 'description': "Description / reason for example topup",},
            'shopId': {'type': openapi.TYPE_STRING, 'description': "User's ShopId",},
            'metadata': {
                'type': openapi.TYPE_ARRAY,
                'description': "An array of values for example transaction top up",
                'items': openapi.Items(type=openapi.TYPE_STRING),
            },
            'walletId': {'type': openapi.TYPE_STRING, 'description': "Users WalletId"},
            'userId': {'type': openapi.TYPE_STRING,'description': "Unique identification of the user"},
        },
        response_example={
            "id": 1,
            "amount": "5",
            "currency": "KES",
            "description":"Top Up",
            "invoiceId": "YSHGD67",
            "status":"COMPLETE",
            "metadata": {"transaction":"topup"},
            "transcation_type":"CARD_PAYMENT",
            "userId":"1",
            "walletId":"1",
            "shopId":"1",
        }
    )
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
            "metadata": metadata,
        }

        # Send request to IntaSend API
        response = requests.post("https://sandbox.intasend.com/api/v1/checkout/", json=intasend_data)

        if response.status_code == 201:
            data = response.json()
            checkout_id = data.get("id")
            invoice_id = data.get("signature")
            transaction_id = str(checkout_id)

            # Save to Django's database
            # transaction = Transactions.objects.create(
            #     id=transaction_id,
            #     amount=amount,
            #     status="PENDING",
            #     currency=currency,
            #     type=transaction_type,
            #     description=description,
            #     userId=userId,
            #     shopId=shopId,
            #     walletId=walletId,
            #     metadata=metadata,
            # )

            # Get the current timestamp in ISO format
            created_at_iso = datetime.now().isoformat()

            # Parse and format the timestamp
            created_at_datetime = datetime.fromisoformat(created_at_iso)
            formatted_created_at = created_at_datetime.strftime("%B %d, %Y at %I:%M:%S %p UTC%z")
            formatted_created_at = formatted_created_at.replace("+0300", "+3")

            # Save to Firestore
            firestore_client = apps.get_app_config('payments').firestore_client
            firestore_client.collection('mytransactions').document(transaction_id).set({
                'id': transaction_id,
                'amount': float(amount),
                'status': "PENDING",
                'currency': currency,
                'type': transaction_type,
                'description': description,
                'userId': userId,
                'shopId': shopId,
                'walletId': walletId,
                'invoiceId':invoice_id,
                'metadata': metadata,
                'createdAt': firestore.SERVER_TIMESTAMP,
                # 'updatedAt': firestore.SERVER_TIMESTAMP,
            })

            # Trigger Celery task to check transaction status
            # check_transaction_status.delay(checkout_id, invoice_id, walletId, amount)

            return Response(data, status=response.status_code)
        else:
            return Response({
                'status': 'Payment Initiation failed',
                'detail': response.json(),
                'response_text': response.text
            }, status=response.status_code)

class TransactionDetailView(FirebaseAuthenticationMixin, APIView):
    @generate_swagger_schema(
        operation_description="API endpoint to check a specific transaction of a user by its ID in detail",
        response_example={
            "id": 1,
            "transctionId":"1",
            "amount": "5",
            "currency": "KES",
            "description":"Top Up",
            "invoiceId": "YSHGD67",
            "phone_number":"25472345678",
            "status":"COMPLETE",
            "metadata": {"type":"pending"},
            "imageUrl":"https://image.com/",
            "transcation_type":"M-PESA",
            "userId":"1",
            "walletId":"1",
            "shopId":"1",
            "name":"James Doe",
            "orderId":"1",
            "customerId":"1",
            "statusType":"pending"
        }
    )
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
