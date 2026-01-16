from django.urls import path
from . import views

app_name = 'employee'  # Kluczowe dla {% url 'employee:...' %}

urlpatterns = [
    path('dashboard/', views.employee_dashboard, name='dashboard'),
    
    path('rooms/', views.employee_rooms, name='rooms'),
    path('rooms/create/', views.employee_room_create, name='room_create'),
    
    path('reservations/', views.employee_reservations, name='reservations'),
    path('reservations/create/', views.employee_create_reservation, name='reservation_create'),
    path('reservations/<int:pk>/', views.employee_reservation_detail, name='reservation_detail'),
    
    path('guests/', views.employee_guests, name='guests'),
    path('guests/<int:pk>/', views.employee_guest_detail, name='guest_detail'),
    
    path('housekeeping/', views.employee_housekeeping, name='housekeeping'),
    path('maintenance/', views.employee_maintenance, name='maintenance'),
    path('pricing/', views.employee_pricing, name='pricing'),
    
    path('manager/employees/', views.manager_employees, name='manager_employees'),
    path('manager/reports/', views.manager_reports, name='manager_reports'),
    path('manager/reports/pdf/', views.manager_report_pdf, name='manager_report_pdf'), # Generowanie PDF
]