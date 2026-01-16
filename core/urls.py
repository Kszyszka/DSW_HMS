from django.urls import path, include
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
    
    # Import ścieżek dla pod-modułów
    path('guest/', include('core.guest_urls')),
    path('employee/', include('core.employee_urls')),
]