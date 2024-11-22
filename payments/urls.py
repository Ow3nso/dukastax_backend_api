# ----- 3rd Party Libraries -----
from django.urls import path

# ----- In-Built Libraries -----
from .views import *

urlpatterns = [
    path('deposit', DepositView.as_view(), name='deposit'),
    path('balance', BalanceView.as_view(), name='balance'),
    path('transactions', TransactionView.as_view(), name='transactions'),
    path('transaction/<str:transaction_id>', TransactionDetailView.as_view(), name="transactionDetailView"),
    path('withdraw', WithdrawalView.as_view(), name="withdraw"),
    path('card_deposit', CardDepositView.as_view(), name="CardDeposit"),
    path("checkout_status", CheckoutStatus.as_view(), name="checkoutStatus"),
    path("process_order_payment", ProcessOrderView.as_view(), name="processOrderPayment")
]