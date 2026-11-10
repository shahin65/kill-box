from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.hub, name='hub'),
    path('wallet/', views.wallet, name='wallet'),
    path('wallet/topup/', views.wallet_topup, name='wallet_topup'),
    path('pay/mock/<str:token>/', views.mock_pay, name='mock_pay'),
    path('gems/', views.gems, name='gems'),
    path('gems/buy/', views.gem_buy, name='gem_buy'),
    path('digital/', views.digital, name='digital'),
    path('digital/<int:pk>/', views.digital_detail, name='digital_detail'),
    path('accounts/', views.listings, name='listings'),
    path('accounts/new/', views.listing_create, name='listing_create'),
    path('accounts/<int:pk>/', views.listing_detail, name='listing_detail'),
    path('gear/', views.physical, name='physical'),
    path('gear/<int:pk>/', views.physical_detail, name='physical_detail'),
    path('orders/', views.orders, name='orders'),
    path('orders/digital/<int:pk>/', views.digital_order_detail, name='digital_order'),
]
