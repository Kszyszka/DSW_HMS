from django.urls import path
from . import views

app_name = 'guest'  # To jest kluczowe dla działania {% url 'guest:...' %}

urlpatterns = [
    path('dashboard/', views.guest_dashboard, name='dashboard'),
    path('reservations/', views.guest_reservations, name='reservations'),
    path('reservations/create/', views.guest_create_reservation, name='create_reservation'),
    # Publiczna rezerwacja (dostępna pod guest:create_reservation_public)
    path('reservations/public/', views.public_create_reservation, name='create_reservation_public'),
    
    path('reservations/<int:pk>/', views.guest_reservation_detail, name='reservation_detail'),
    path('reservations/<int:pk>/cancel/', views.guest_cancel_reservation, name='cancel_reservation'),
    
    path('profile/', views.guest_profile, name='profile'),
    path('register/', views.register_view, name='register'),
]