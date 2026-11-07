from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('bg-preview/', views.neon_bg_preview, name='neon_bg_preview'),
    path('home/', views.home, name='home'),
    path('profile/', views.profile, name='profile'),
    path('profile/avatar/', views.avatar_upload, name='avatar_upload'),
    path('profile/name/', views.profile_name, name='profile_name'),
    path('profile/bio/', views.profile_bio, name='profile_bio'),
    path('profile/codm/', views.profile_codm, name='profile_codm'),
    path('settings/', views.site_settings, name='settings'),
    path('invite/', views.invite, name='invite'),
    path('team/', views.team, name='team'),
    path('shop/', views.shop, name='shop'),
    path('live/', views.live_hub, name='live'),
    path('live/<slug:slug>/', views.live_hub, name='live_room'),
    path('live/<slug:slug>/chat/', views.live_chat, name='live_chat'),
    path('live/<slug:slug>/donate/', views.live_donate, name='live_donate'),
    path('live/<slug:slug>/feed/', views.live_feed, name='live_feed'),
    path('legal/about/', views.about, name='about'),
    path('legal/privacy/', views.privacy, name='privacy'),
    path('legal/terms/', views.terms, name='terms'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/otp/send/', views.otp_send, name='otp_send'),
    path('auth/otp/verify/', views.otp_verify, name='otp_verify'),
    path('auth/guest/', views.guest_enter, name='guest_enter'),
    path('auth/bale/start/', views.bale_start, name='bale_start'),
    path('auth/bale/status/', views.bale_status, name='bale_status'),
    path('auth/bale/webhook/<str:secret>/', views.bale_webhook, name='bale_webhook'),
    path('auth/telegram/start/', views.telegram_start, name='telegram_start'),
    path('auth/telegram/status/', views.telegram_status, name='telegram_status'),
    path(
        'auth/telegram/webhook/<str:secret>/',
        views.telegram_webhook,
        name='telegram_webhook',
    ),
]
