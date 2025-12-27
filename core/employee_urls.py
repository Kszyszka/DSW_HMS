from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [
    path('', views.employee_dashboard, name='dashboard'),
    path('rooms/', views.employee_rooms, name='rooms'),
    path('rooms/create/', views.employee_room_create, name='room_create'),
    path('pricing/', views.employee_pricing, name='pricing'),
    path('housekeeping/', views.housekeeping_dashboard, name='housekeeping'),
    path('reservations/', views.employee_reservations, name='reservations'),
    path('reservations/create/', views.employee_create_reservation, name='reservation_create'),
    path('reservations/<int:reservation_id>/', views.employee_reservation_detail, name='reservation_detail'),
    path('guests/', views.employee_guests, name='guests'),
    path('guests/<int:guest_id>/', views.employee_guest_detail, name='guest_detail'),
]

