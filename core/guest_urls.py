from django.urls import path
from . import views

app_name = 'guest'

urlpatterns = [
    path('', views.guest_dashboard, name='dashboard'),
    path('reservations/', views.guest_reservations, name='reservations'),
    path('reservations/<int:reservation_id>/', views.guest_reservation_detail, name='reservation_detail'),
    path('reservations/create/', views.guest_create_reservation, name='create_reservation'),
    path('profile/', views.guest_profile, name='profile'),
]

