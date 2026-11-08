from django.urls import path

from . import views

app_name = 'alliances'

urlpatterns = [
    path('', views.hub, name='hub'),
    path('search/', views.search, name='search'),
    path('create/', views.create, name='create'),
    path('invites/<int:pk>/accept/', views.accept_invite, name='accept_invite'),
    path('invites/<int:pk>/reject/', views.reject_invite, name='reject_invite'),
    path('requests/<int:pk>/review/', views.review_request, name='review_request'),
    path('<slug:slug>/', views.detail, name='detail'),
    path('<slug:slug>/manage/', views.manage, name='manage'),
    path('<slug:slug>/join/', views.join, name='join'),
    path('<slug:slug>/request/', views.request_to_join, name='request_join'),
    path('<slug:slug>/leave/', views.leave, name='leave'),
    path('<slug:slug>/invite/', views.invite, name='invite'),
    path('<slug:slug>/members/<int:member_id>/role/', views.set_role, name='set_role'),
    path('<slug:slug>/members/<int:member_id>/kick/', views.kick, name='kick'),
    path('<slug:slug>/blacklist/', views.blacklist, name='blacklist'),
    path('<slug:slug>/blacklist/<int:user_id>/remove/', views.unblacklist, name='unblacklist'),
    path('<slug:slug>/messages/', views.messages, name='messages'),
    path('<slug:slug>/presence/', views.presence_view, name='presence'),
]
