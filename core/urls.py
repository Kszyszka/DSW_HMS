from django.urls import path
from . import views

urlpatterns = [
    # Widoki ogólne (Publiczne)
    path('', views.home_view, name='home'),  # Zmieniono views.home na views.home_view
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('reservation/start/', views.public_create_reservation, name='public_create_reservation'),
    
    # API
    path('api/rooms-availability/', views.room_availability_api, name='room_availability_api'),
    
    # PDF
    path('invoice/<int:pk>/pdf/', views.reservation_invoice_pdf, name='reservation_invoice_pdf'),
    
    # Uwaga: Import ścieżek dla pod-modułów jest w config/urls.py, aby uniknąć duplikacji namespace'ów
]