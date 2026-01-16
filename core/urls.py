from django.urls import path
from . import views

# Brak app_name - główne URL-e nie są w namespace
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('reservations/<int:reservation_id>/', views.public_reservation_detail, name='public_reservation_detail'),
    path('reservations/<int:reservation_id>/precheckin/', views.pre_checkin, name='pre_checkin'),
    path('reservations/<int:reservation_id>/pay/', views.online_payment_test, name='online_payment_test'),
    path('api/rooms-availability/', views.rooms_availability_api, name='rooms_availability_api'),
]

