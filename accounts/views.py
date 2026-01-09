from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
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
                ], 
                'user': user
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

# Manage Trainers page
def manage_trainer(request):
    trainers = User.objects.filter(role='trainer').order_by('-created_at')
    return render(request, 'dashboards/admin/admin_manage_trainers.html', {'trainers': trainers})

# Add Trainer
def add_trainer(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        specialization = request.POST.get('specialization')
        experience_years = request.POST.get('experience_years') or None
        profile_picture = request.FILES.get('profile_picture', None)
        password = request.POST.get('password') or 'trainer123'  # default password

        # Check for username/email conflicts
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('manage_trainers')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('manage_trainers')

        trainer = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name,
            phone=phone,
            gender=gender,
            specialization=specialization,
            experience_years=experience_years,
            profile_picture=profile_picture,
            role='trainer',
            is_active=True
        )

        messages.success(request, f'Trainer "{trainer.username}" added successfully.')
        return redirect('manage_trainers')
    messages.error(request, 'Invalid request.')
    return redirect('manage_trainers')


# Edit Trainer
def edit_trainer(request, trainer_id):
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')

    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        specialization = request.POST.get('specialization')
        experience_years = request.POST.get('experience_years') or None
        profile_picture = request.FILES.get('profile_picture', None)

        # Check for conflicts excluding this trainer
        if User.objects.filter(username=username).exclude(pk=trainer_id).exists():
            messages.error(request, 'Username already exists.')
            return redirect('manage_trainers')
        if User.objects.filter(email=email).exclude(pk=trainer_id).exists():
            messages.error(request, 'Email already registered.')
            return redirect('manage_trainers')

        trainer.username = username
        trainer.full_name = full_name
        trainer.email = email
        trainer.phone = phone
        trainer.gender = gender
        trainer.specialization = specialization
        trainer.experience_years = experience_years
        if profile_picture:
            trainer.profile_picture = profile_picture

        trainer.save()
        messages.success(request, f'Trainer "{trainer.username}" updated successfully.')
        return redirect('manage_trainers')

    messages.error(request, 'Invalid request.')
    return redirect('manage_trainers')


# Toggle Trainer Active/Inactive
def toggle_trainer_status(request, trainer_id):
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    trainer.is_active = not trainer.is_active
    trainer.save()
    status = 'activated' if trainer.is_active else 'deactivated'
    messages.success(request, f'Trainer "{trainer.username}" has been {status}.')
    return redirect('manage_trainers')