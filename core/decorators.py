from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def employee_required(view_func):
    """Dekorator wymagający, aby użytkownik był pracownikiem lub superuserem"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.')
            return redirect('login')
        
        # Superuser ma dostęp do wszystkich widoków
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not hasattr(request.user, 'employee_profile'):
            messages.error(request, 'Brak uprawnień. Ta strona jest dostępna tylko dla pracowników.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def guest_required(view_func):
    """Dekorator wymagający, aby użytkownik był gościem lub superuserem"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.')
            return redirect('login')
        
        # Superuser ma dostęp do wszystkich widoków
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not hasattr(request.user, 'guest_profile'):
            messages.error(request, 'Brak uprawnień. Ta strona jest dostępna tylko dla gości.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def manager_required(view_func):
    """Dekorator wymagający roli menedżera lub administratora"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Musisz być zalogowany, aby uzyskać dostęp do tej strony.')
            return redirect('login')
        
        if not hasattr(request.user, 'employee_profile'):
            messages.error(request, 'Brak uprawnień.')
            return redirect('home')
        
        employee = request.user.employee_profile
        if employee.role not in ['manager', 'admin']:
            messages.error(request, 'Brak uprawnień. Ta funkcja jest dostępna tylko dla menedżerów.')
            return redirect('employee:dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

