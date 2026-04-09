from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from certificate.models import CompletionCertificate
from classes.models import ClassBooking, ClassSession, PrivateClass

AUTHORIZED_SIGNATURE_PATH = 'authorized_signatures/img.png'


@login_required
def issue_group_class_completion_certificate(request, booking_id):
    booking = get_object_or_404(ClassBooking, pk=booking_id, is_cancelled=False)

    if booking.class_session.trainer != request.user and booking.class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only issue certificates for your own classes or substitute class.')
        return redirect('manage_trainer_class_session')

    if booking.class_session.end_date >= datetime.now().date():
        messages.error(request, 'Cannot issue certificates for a class session that has not ended yet.')
        return redirect('manage_trainer_class_session')

    if hasattr(booking, 'completion_certificate'):
        messages.error(request, 'Certificate has already been issued for this booking.')
        return redirect('manage_trainer_class_session')

    CompletionCertificate.objects.create(
        user=booking.user,
        trainer=request.user,
        class_booking=booking,
    )
    messages.success(request, 'Completion certificate issued successfully.')
    return redirect('select_student_for_group_certificate', class_session_id=booking.class_session_id)


@login_required
def issue_private_class_completion_certificate(request, private_class_id):
    private_class = get_object_or_404(PrivateClass, pk=private_class_id, is_cancelled=False)

    if private_class.trainer != request.user and private_class.substitute_trainer != request.user:
        messages.error(request, 'You can only issue certificates for your own classes or substitute class.')
        return redirect('manage_trainer_private_classes')

    if private_class.end_date >= datetime.now().date():
        messages.error(request, 'Cannot issue certificates for a private class that has not ended yet.')
        return redirect('manage_trainer_private_classes')

    if hasattr(private_class, 'completion_certificate'):
        messages.error(request, 'Certificate has already been issued for this private class.')
        return redirect('manage_trainer_private_classes')

    CompletionCertificate.objects.create(
        user=private_class.user,
        trainer=request.user,
        private_class=private_class,
    )
    messages.success(request, 'Completion certificate issued successfully.')
    return redirect('pending_private_certificates')


@login_required
def pending_group_certificate_sessions(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = datetime.now().date()
    completed_sessions = ClassSession.objects.filter(
        is_cancelled=False,
        end_date__lt=today,
    ).filter(
        Q(trainer=request.user) | Q(substitute_trainer=request.user)
    ).select_related('pool', 'class_type').order_by('-end_date')
    q = (request.GET.get('q') or '').strip()
    if q:
        completed_sessions = completed_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )

    pending_sessions = []
    for class_session in completed_sessions:
        bookings = ClassBooking.objects.filter(
            class_session=class_session,
            is_cancelled=False,
        )

        has_uncertified_students = False
        for booking in bookings:
            if not hasattr(booking, 'completion_certificate'):
                has_uncertified_students = True
                break

        if has_uncertified_students:
            pending_sessions.append(class_session)

    return render(
        request,
        'dashboards/trainer/pending_group_certificate_sessions.html',
        {'pending_sessions': pending_sessions},
    )


@login_required
def pending_private_certificates(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = datetime.now().date()
    completed_private_classes = PrivateClass.objects.filter(
        is_cancelled=False,
        end_date__lt=today,
    ).filter(
        Q(trainer=request.user) | Q(substitute_trainer=request.user)
    ).select_related('user', 'pool').order_by('-end_date')
    q = (request.GET.get('q') or '').strip()
    if q:
        completed_private_classes = completed_private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    pending_private_classes = []
    for private_class in completed_private_classes:
        if not hasattr(private_class, 'completion_certificate'):
            pending_private_classes.append(private_class)

    return render(
        request,
        'dashboards/trainer/pending_private_certificates.html',
        {'pending_private_classes': pending_private_classes},
    )


@login_required
def select_student_for_group_certificate(request, class_session_id):
    class_session = get_object_or_404(ClassSession, pk=class_session_id, is_cancelled=False)

    if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only issue certificates for your own classes or substitute class.')
        return redirect('manage_trainer_class_session')

    if class_session.end_date >= datetime.now().date():
        messages.error(request, 'This class session has not been completed yet.')
        return redirect('pending_group_certificate_sessions')

    bookings = ClassBooking.objects.filter(
        class_session=class_session,
        is_cancelled=False,
    ).select_related('user')
    q = (request.GET.get('q') or '').strip()

    if q:
        bookings = bookings.filter(
            Q(user__username__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__email__icontains=q)
        )

    pending_bookings = []
    for booking in bookings:
        if not hasattr(booking, 'completion_certificate'):
            pending_bookings.append(booking)

    return render(
        request,
        'dashboards/trainer/select_students_for_group_certificate.html',
        {
            'class_session': class_session,
            'pending_bookings': pending_bookings,
        },
    )


@login_required
def certificate_granted_list(request):
    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    certificates = CompletionCertificate.objects.select_related(
        'user', 'trainer', 'class_booking__class_session', 'private_class'
    ).order_by('-id')
    q = (request.GET.get('q') or '').strip()
    cert_type = (request.GET.get('type') or '').strip()

    if q:
        certificates = certificates.filter(
            Q(user__username__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(class_booking__class_session__class_name__icontains=q) |
            Q(private_class__pool__name__icontains=q)
        )

    if cert_type == 'group':
        certificates = certificates.filter(class_booking__isnull=False)
    elif cert_type == 'private':
        certificates = certificates.filter(private_class__isnull=False)

    if request.user.role == 'trainer':
        certificates = certificates.filter(trainer=request.user)
        return render(
            request,
            'dashboards/trainer/certificates/certificate_granted_list.html',
            {'certificates': certificates},
        )

    return render(
        request,
        'dashboards/admin/certificates/certificate_granted_list.html',
        {'certificates': certificates},
    )


@login_required
def trainer_view_certificate(request, certificate_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    certificate = get_object_or_404(CompletionCertificate, id=certificate_id, trainer=request.user)

    if certificate.class_booking:
        trainer = certificate.class_booking.class_session.trainer
    elif certificate.private_class:
        trainer = certificate.private_class.trainer
    else:
        trainer = None

    if User.objects.filter(role='admin').exists():
        admin_signatre = User.objects.filter(role='admin').first().digital_signature
    else:
        admin_signatre = None

    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('certificate_granted_list')

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'authorized_signature_path': admin_signatre,
    }
    return render(request, 'dashboards/trainer/certificates/trainer_view_certificate.html', context)


@login_required
def user_view_certificate(request, certificate_id):
    certificate = get_object_or_404(CompletionCertificate, id=certificate_id, user=request.user)

    if certificate.class_booking:
        trainer = certificate.class_booking.class_session.trainer
    elif certificate.private_class:
        trainer = certificate.private_class.trainer
    else:
        trainer = None

    if User.objects.filter(role='admin').exists():
        admin_signatre = User.objects.filter(role='admin').first().digital_signature
    else:
        admin_signatre = None

    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'authorized_signature_path': admin_signatre,
    }
    return render(request, 'dashboards/user/reviews/user_view_certificate.html', context)

@login_required
def admin_view_certificate(request, certificate_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    certificate = get_object_or_404(CompletionCertificate, id=certificate_id)

    if certificate.class_booking:
        trainer = certificate.class_booking.class_session.trainer
    elif certificate.private_class:
        trainer = certificate.private_class.trainer
    else:
        trainer = None

    if User.objects.filter(role='admin').exists():
        admin_signatre = User.objects.filter(role='admin').first().digital_signature
    else:
        admin_signatre = None

    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('certificate_granted_list')

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'authorized_signature_path': admin_signatre,
    }
    return render(request, 'dashboards/admin/reviews/admin_view_certificate.html', context)
