from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import User
from django.contrib.auth import login, logout, authenticate

from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.utils import timezone

from classes.models import ClassBooking, ClassSession, PrivateClass
from payments.models import Payment
from pool.models import PoolQuality


# Create your views here.
def index(request):
    print("is_authenticated:", request.user.is_authenticated)
    print("is_superuser:", request.user.is_superuser)
    print("role:", getattr(request.user, 'role', None))
    return render(request, 'index.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user and user.check_password(password):
            login(request, user)
            messages.success(request, f'Welcome back, {user.full_name}!')

            if user.role == 'admin':
                return redirect('admin_dashboard')
            elif user.role == 'trainer':
                return redirect('trainer_dashboard')
            else:
                return redirect('user_dashboard')

        else:
            messages.error(request, 'Invalid username or password.')
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
        date_of_birth = request.POST.get('date_of_birth')
        profile_picture = request.FILES.get('profile_picture', None)

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('signup')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('signup')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('signup')

        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                phone=phone,
                gender=gender,
                date_of_birth=date_of_birth,
                profile_picture=profile_picture,
                role='user'
            )

            messages.success(request, 'Account created successfully. Please log in.')
            return render(request, 'auth/login.html')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('signup')
        except Exception:
            messages.error(request, 'An error occurred while creating the account. Please try again')
            return redirect('signup')
    return render(request, 'auth/signup.html')

def logout_view(request):
    logout(request)
    messages.success(request, 'You have logged out successfully')
    return render(request, 'auth/login.html')

# Manage Members page (placeholder)
def manage_members(request):
    members = User.objects.filter(role='user').order_by('-created_at')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    joined_from = request.GET.get('joined_from')
    joined_to = request.GET.get('joined_to')

    if q:
        members = members.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )
    if status == 'active':
        members = members.filter(is_active=True)
    elif status == 'inactive':
        members = members.filter(is_active=False)

    if joined_from:
        members = members.filter(created_at__date__gte=joined_from)
    if joined_to:
        members = members.filter(created_at__date__lte=joined_to)
    return render(request, 'dashboards/admin/admin_manage_members.html', {'members': members})

# Manage Trainers page
def manage_trainer(request):
    trainers = User.objects.filter(role='trainer').order_by('-created_at')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    specialization = (request.GET.get('specialization') or '').strip()
    min_exp = request.GET.get('min_exp')

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )
    if specialization:
        trainers = trainers.filter(specialization__icontains=specialization)

    if status == 'active':
        trainers = trainers.filter(is_active=True)
    elif status == 'inactive':
        trainers = trainers.filter(is_active=False)

    if min_exp:
        try:
            trainers = trainers.filter(experience_years__gte=int(min_exp))
        except ValueError:
            pass
    return render(request, 'dashboards/admin/admin_manage_trainers.html', {'trainers': trainers})

# Add Trainer
def add_trainer(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        digital_signature = request.FILES.get('digital_signature', None)
        specialization = request.POST.get('specialization')
        experience_years = request.POST.get('experience_years') or None
        profile_picture = request.FILES.get('profile_picture', None)
        password = request.POST.get('password') or 'trainer123'

        # Check for username/email conflicts
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return redirect('manage_trainers')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('manage_trainers')
        if not digital_signature:
            messages.error(request, 'Digital signature is required for trainers.')
            return redirect('manage_trainers')
        if experience_years is not None:
            try:
                experience_years = int(experience_years)
            except:
                messages.error(request, 'Experience years must be a valid integer.')
                return redirect('manage_trainers')
    
        try:
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
                digital_signature=digital_signature,
                role='trainer',
                is_active=True
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('manage_trainers')
        except Exception:
            messages.error(request, 'An error occurred while creating the trainer. Please try again.')
            return redirect('manage_trainers')

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
        digital_signature = request.FILES.get('digital_signature', None)
        
        # Check for conflicts excluding this trainer
        if User.objects.filter(username=username).exclude(pk=trainer_id).exists():
            messages.error(request, 'Username already exists.')
            return redirect('manage_trainers')
        if User.objects.filter(email=email).exclude(pk=trainer_id).exists():
            messages.error(request, 'Email already registered.')
            return redirect('manage_trainers')
        
        if not full_name:
            messages.error(request, 'Full name is required.')
            return redirect('manage_trainers')

        if not gender:
            messages.error(request, 'Gender is required.')
            return redirect('manage_trainers')

        if not trainer.digital_signature and not digital_signature:
            messages.error(request, 'Digital signature is required for trainers.')
            return redirect('manage_trainers')

        if experience_years is None:
            try:
                experience_years = int(experience_years)
            except:
                messages.error(request, 'Experience years must be a valid integer.')
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
        if digital_signature:
            trainer.digital_signature = digital_signature

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


# Edit Member (placeholder)
def edit_member(request, member_id):
    user = get_object_or_404(User, pk=member_id, role='user')

    if request.method == 'POST':
        username = request.POST.get('username')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')
        profile_picture = request.FILES.get('profile_picture', None)
        
        if User.objects.filter(username=username).exclude(pk=member_id).exists():
            messages.error(request, 'Username already exists.')
            return redirect('manage_members')
        if User.objects.filter(email=email).exclude(pk=member_id).exists():
            messages.error(request, 'Email already registered.')
            return redirect('manage_members')
        
        
        user.username = username
        user.full_name = full_name
        user.email = email
        user.phone = phone
        user.gender = gender
        user.date_of_birth = date_of_birth
        if profile_picture:
            user.profile_picture = profile_picture 
        user.save()
        messages.success(request, f'Member "{user.username}" updated successfully.')
        return redirect('manage_members')
    
    messages.error(request, 'Invalid request.')
    return redirect('manage_members')

@login_required
def admin_dashboard(request):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Admins only.')
        return redirect('index')
    
    today = date.today()
    now = timezone.now()

    total_users = User.objects.filter(role='user').count()
    total_trainers = User.objects.filter(role='trainer').count()

    active_classes = ClassSession.objects.filter(start_date__lte=today, end_date__gte=today).count()
    active_private_classes = PrivateClass.objects.filter(start_date__lte=today, end_date__gte=today).count()

    monthly_revenue = Payment.objects.filter(
        payment_status='completed',
        payment_date__year=now.year,
        payment_date__month=now.month
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    total_revenue = Payment.objects.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    pending_payments = Payment.objects.filter(payment_status='pending').count()
    pool_quality = PoolQuality.objects.order_by('-created_at')[:5]

    if pool_quality is None:
        pool_quality = "No pool quality records found."

    recent_bookings = ClassBooking.objects.select_related("user", "class_session", "class_session__trainer", "class_session__pool").order_by('-booking_date')[:5]

    context = {
        'total_users': total_users,
        'total_trainers': total_trainers,
        'active_classes': active_classes,
        'active_private_classes': active_private_classes,
        'monthly_revenue': monthly_revenue,
        'total_revenue': total_revenue,
        'pending_payments': pending_payments,
        'recent_pool_quality': pool_quality,
        'recent_bookings': recent_bookings,
    }
    return render(request, 'dashboards/admin/admin_dashboard.html', context)

@login_required
def trainer_dashboard(request):
    if request.user.role != 'trainer':
        messages.error(request, 'Access denied. Trainers only.')
        return redirect('index')
    
    trainer = request.user
    today = date.today()

    upcoming_classes = ClassSession.objects.filter(
        trainer=trainer,
        end_date__gte=today
    ).order_by('start_date', 'start_time')[:5]

    upcoming_private_classes = PrivateClass.objects.filter(
        trainer=trainer,
        end_date__gte=today
    ).order_by('start_date', 'start_time')[:5]

    is_weekend = today.weekday() >= 5
    if is_weekend:
        today_group_classes = "No group classes scheduled for today (weekends)."
    else:
        today_group_classes = ClassSession.objects.filter(trainer=trainer, start_date__lte=today, end_date__gte=today)[:5]

    context = {
        'upcoming_classes': upcoming_classes,
        'upcoming_private_classes': upcoming_private_classes,
        'today_group_classes': today_group_classes,
    }
    return render(request, 'dashboards/trainer/trainer_dashboard.html', context)

@login_required
def user_dashboard(request):
    if request.user.role != 'user':
        messages.error(request, 'Access denied. Members only.')
        return redirect('index')
    
    user = request.user
    today = date.today()

    upcoming_bookings = ClassBooking.objects.filter(
        user=user,
        class_session__end_date__gte=today,
        is_cancelled=False
    ).select_related('class_session', 'class_session__trainer', 'class_session__pool').order_by('class_session__start_date', 'class_session__start_time')[:5]

    upcoming_private_bookings = PrivateClass.objects.filter(
        user=user,
        end_date__gte=today,
        is_cancelled=False
    ).select_related('trainer', 'pool').order_by('start_date', 'start_time')[:5]

    context = {
        'upcoming_bookings': upcoming_bookings,
        'upcoming_private_bookings': upcoming_private_bookings,
    }
    return render(request, 'dashboards/user/user_dashboard.html', context)

@login_required
def user_profile(request):
    if request.user.role != 'user':
        messages.error(request, 'Access denied. Members only.')
        return redirect('index')
    
    user = request.user
    if request.method == 'POST':
        profile_picture = request.FILES.get('profile_picture', None)
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')

        if not full_name:
            messages.error(request, 'Full name is required.')
            return redirect('user_profile')

        if not email:
            messages.error(request, 'Email is required.')
            return redirect('user_profile')

        if not gender:
            messages.error(request, 'Gender is required.')
            return redirect('user_profile')

        if not date_of_birth:
            messages.error(request, 'Date of birth is required.')
            return redirect('user_profile')

        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, 'Email already registered.')
            return redirect('user_profile')
        
        if profile_picture:
            user.profile_picture = profile_picture
        user.full_name = full_name
        user.email = email
        user.phone = phone
        user.gender = gender
        user.date_of_birth = date_of_birth

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('user_profile')
    
    return render(request, 'dashboards/user/user_profile.html')

@login_required
def trainer_profile(request):
    if request.user.role != 'trainer':
        messages.error(request, 'Access denied. Trainers only.')
        return redirect('index')
    
    user = request.user
    if request.method == 'POST':
        profile_picture = request.FILES.get('profile_picture', None)
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')
        specialization = request.POST.get('specialization') or None
        experience_years = request.POST.get('experience_years') or None

        if not full_name:
            messages.error(request, 'Full name is required.')
            return redirect('trainer_profile')

        if not email:
            messages.error(request, 'Email is required.')
            return redirect('trainer_profile')

        if not gender:
            messages.error(request, 'Gender is required.')
            return redirect('trainer_profile')

        if not date_of_birth:
            messages.error(request, 'Date of birth is required.')
            return redirect('trainer_profile')

        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, 'Email already registered.')
            return redirect('trainer_profile')
        
        if profile_picture:
            user.profile_picture = profile_picture
        user.full_name = full_name
        user.email = email
        user.phone = phone
        user.gender = gender
        user.date_of_birth = date_of_birth
        user.specialization = specialization
        user.experience_years = experience_years

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('trainer_profile')
    return render(request, 'dashboards/trainer/trainer_profile.html')

@login_required
def admin_profile(request):
    if request.user.role != 'admin':
        messages.error(request, 'Access denied. Admins only.')
        return redirect('index')
    
    user = request.user
    if request.method == 'POST':
        profile_picture = request.FILES.get('profile_picture', None)
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        gender = request.POST.get('gender')
        date_of_birth = request.POST.get('date_of_birth')

        if not full_name:
            messages.error(request, 'Full name is required.')
            return redirect('admin_profile')

        if not email:
            messages.error(request, 'Email is required.')
            return redirect('admin_profile')

        if not gender:
            messages.error(request, 'Gender is required.')
            return redirect('admin_profile')

        if not date_of_birth:
            messages.error(request, 'Date of birth is required.')
            return redirect('admin_profile')

        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            messages.error(request, 'Email already registered.')
            return redirect('admin_profile')
        
        if profile_picture:
            user.profile_picture = profile_picture
        user.full_name = full_name
        user.email = email
        user.phone = phone
        user.gender = gender
        user.date_of_birth = date_of_birth

        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('admin_profile')
    return render(request, 'dashboards/admin/admin_profile.html')

def _role_check_for_change_password(user):
    if user.role == 'admin':
        return redirect('admin_dashboard')
    elif user.role == 'trainer':
        return redirect('trainer_dashboard')
    return redirect('user_profile')

@login_required
def change_password(request):
    user = request.user
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return _role_check_for_change_password(user)
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return _role_check_for_change_password(user)
        
        if not new_password:
            messages.error(request, 'New password cannot be empty.')
            return _role_check_for_change_password(user)
        
        user.set_password(new_password)
        user.save()

        logout(request)
        messages.success(request, 'Password changed successfully. Please login again.')
        return redirect('login')
    return _role_check_for_change_password(user)