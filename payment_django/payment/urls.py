from django.urls import path
from . import views

urlpatterns = [
    path('pay/', views.process_payment)
]
