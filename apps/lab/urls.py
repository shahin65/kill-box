from django.urls import path

from . import views

app_name = 'lab'

urlpatterns = [
    path('', views.index, name='index'),
    path('uid-lookup/', views.uid_lookup, name='uid_lookup'),
    path('otp/send/', views.otp_send, name='otp_send'),
    path('otp/verify/', views.otp_verify, name='otp_verify'),
]
