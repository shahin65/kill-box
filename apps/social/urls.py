from django.urls import path

from . import views

app_name = 'social'

urlpatterns = [
    path('explore/', views.explore, name='explore'),
    path('stories/', views.stories, name='stories'),
    path('stories/create/', views.story_create, name='story_create'),
    path('stories/<int:pk>/like/', views.story_like, name='story_like'),
    path('stories/<int:pk>/comment/', views.story_comment, name='story_comment'),
    path('stories/<int:pk>/seen/', views.story_seen, name='story_seen'),
    path('stories/<int:pk>/viewers/', views.story_viewers, name='story_viewers'),
    path('posts/', views.posts, name='posts'),
    path('posts/create/', views.post_create, name='post_create'),
    path('saved/', views.saved_posts, name='saved'),
    path('gifs/', views.gif_search, name='gifs'),
    path('posts/<int:pk>/', views.post_detail, name='post_detail'),
    path('posts/<int:pk>/like/', views.post_like, name='post_like'),
    path('posts/<int:pk>/view/', views.post_view, name='post_view'),
    path('posts/<int:pk>/save/', views.post_save, name='post_save'),
    path('posts/<int:pk>/comment/', views.post_comment, name='post_comment'),
    path('comments/<int:pk>/delete/', views.comment_delete, name='comment_delete'),
    path('messages/', views.inbox, name='inbox'),
    path('messages/<int:user_id>/', views.thread, name='thread'),
    path('messages/<int:user_id>/send/', views.message_send, name='message_send'),
    path('messages/<int:user_id>/accept/', views.message_accept, name='message_accept'),
    path('messages/<int:user_id>/reject/', views.message_reject, name='message_reject'),
    path('messages/<int:user_id>/block/', views.message_block, name='message_block'),
    path('follow/<int:user_id>/', views.follow_toggle, name='follow'),
    path('followers/', views.people, {'kind': 'followers'}, name='followers'),
    path('following/', views.people, {'kind': 'following'}, name='following'),
    path('friends/', views.friends, name='friends'),
    path('friends/requests/', views.friend_requests, name='friend_requests'),
    path('friends/<int:user_id>/request/', views.friend_request_send, name='friend_request'),
    path('friends/<int:user_id>/accept/', views.friend_request_accept, name='friend_accept'),
    path('friends/<int:user_id>/reject/', views.friend_request_reject, name='friend_reject'),
]
