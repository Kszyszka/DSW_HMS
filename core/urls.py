from django.urls import path
from . import views

# Brak app_name - główne URL-e nie są w namespace
urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]

