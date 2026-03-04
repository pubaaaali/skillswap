"""URL patterns for the SkillSwap core app."""

from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Auth
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),

    # Profile (edit must come before <str:username> to avoid conflict)
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('skills/add/', views.skill_add, name='skill_add'),
    path('skills/<int:pk>/edit/', views.skill_edit, name='skill_edit'),
    path('skills/<int:pk>/delete/', views.skill_delete, name='skill_delete'),

    # Marketplace & Requests
    path('marketplace/', views.marketplace, name='marketplace'),
    path('requests/new/', views.request_create, name='request_create'),
    path('requests/mine/', views.my_requests, name='my_requests'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),
    path('requests/<int:pk>/edit/', views.request_edit, name='request_edit'),
    path('requests/<int:pk>/bid/', views.bid_submit, name='bid_submit'),
    path('requests/<int:pk>/bid/<int:bid_id>/accept/', views.bid_accept, name='bid_accept'),
    path('requests/<int:pk>/message/', views.message_send, name='message_send'),

    # My bids
    path('bids/mine/', views.my_bids, name='my_bids'),

    # Exchanges
    path('exchanges/mine/', views.my_exchanges, name='my_exchanges'),
    path('exchanges/<int:pk>/', views.exchange_detail, name='exchange_detail'),
    path('exchanges/<int:pk>/confirm/', views.exchange_confirm, name='exchange_confirm'),
    path('exchanges/<int:pk>/dispute/', views.exchange_dispute, name='exchange_dispute'),

    # Reviews
    path('exchanges/<int:exchange_pk>/review/', views.review_submit, name='review_submit'),

    # Ledger
    path('ledger/', views.ledger, name='ledger'),
]
