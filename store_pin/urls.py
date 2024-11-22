# ----- 3rd Party Libraries -----
from django.urls import path

# ----- In-Built Libraries -----
from .views import *

urlpatterns = [
    path('save-pin/', SavePinView.as_view(), name='save_pin'),
    path('confirm-pin/', ConfirmPinView.as_view(), name='confirm_pin'),
    path('check-pin/<str:user_id>/', CheckPinStatusView.as_view(), name='check-pin'),
]