from django.shortcuts import render
from django.contrib.auth import logout
from .models import User

# Create your views here.
def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = User.objects.filter(username=username).first()
        if user and user.check_password(password):
            context = {
                'messages': [
                    {'tags': 'success', 'message': 'Login successful.'}
                ]
            }

            if user.role == 'admin':
                return render(request, 'dashboards/admin/admin_dashboard.html', context)
            elif user.role == 'trainer':
                return render(request, 'dashboards/trainer/trainer_dashboard.html', context)
            else:
                return render(request, 'dashboards/user/user_dashboard.html', context)
        else:
            context = {
                'messages': [
                    {'tags': 'error', 'message': 'Invalid username or password.'}
                ]
            }
            return render(request, 'auth/login.html', context)
    return render(request, 'auth/login.html')

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth', None)
        profile_picture = request.FILES.get('profile_picture', None)

        if date_of_birth == '':
            date_of_birth = None

        if password != confirm_password:
            context = {
                'messages': [
                    {'tags': 'error', 'message': 'Passwords do not match.'}
                ]
            }
            return render(request, 'auth/signup.html', context)
        
        if User.objects.filter(username=username).exists():
            context = {
                'messages': [
                    {'tags': 'error', 'message': 'Username already taken.'}
                ]
            }
            return render(request, 'auth/signup.html', context)
        
        if User.objects.filter(email=email).exists():
            context = {
                'messages': [
                    {'tags': 'error', 'message': 'Email already registered.'}
                ]
            }
            return render(request, 'auth/signup.html', context)
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            gender=gender,
            date_of_birth=date_of_birth,
            profile_picture=profile_picture,
            role='user'   # always member
        )

        context = {
            'messages': [
                {'tags': 'success', 'message': 'Account created successfully. Please log in.'}
            ]
        }
        return render(request, 'auth/login.html', context)
    return render(request, 'auth/signup.html')

def logout_view(request):
    logout(request)
    context = {
        'messages': [
            {'tags': 'success', 'message': 'Logged out successfully.'}
        ]
    }
    return render(request, 'auth/login.html', context)

#Users dashboards
def user_dashboard(request):
    return render(request, 'dashboards/user/user_dashboard.html')

def trainer_dashboard(request):
    return render(request, 'dashboards/trainer/trainer_dashboard.html')

def admin_dashboard(request):
    return render(request, 'dashboards/admin/admin_dashboard.html')