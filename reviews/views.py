import datetime

from django.shortcuts import get_object_or_404, render
from django.db.models import Q
from certificate.models import CompletionCertificate
from .models import Review
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

# Create your views here.


def get_review_trainer(review):
    if review.certificate.class_booking:
        return review.certificate.class_booking.class_session.trainer
    if review.certificate.private_class:
        return review.certificate.private_class.trainer
    return None


def get_review_source_label(review):
    if review.certificate.class_booking:
        class_name = review.certificate.class_booking.class_session.class_name
        return f'Group Class: {class_name}'
    if review.certificate.private_class:
        return 'Private Class'
    return 'Unknown'

def get_certificate_and_trainer(request, certificate_id):
    certificate = get_object_or_404(CompletionCertificate, id=certificate_id, user=request.user)

    if certificate.class_booking:
        trainer = certificate.class_booking.class_session.trainer
    elif certificate.private_class:
        trainer = certificate.private_class.trainer
    else:
        trainer = None

    return certificate, trainer

@login_required
def user_select_trainer_from_certificate(request):
    certificates = CompletionCertificate.objects.filter(user=request.user)

    q = (request.GET.get('q') or '').strip().lower()
    if q:
        certificates = certificates.filter(
            Q(class_booking__class_session__trainer__full_name__icontains=q) |
            Q(class_booking__class_session__trainer__username__icontains=q) |
            Q(private_class__trainer__full_name__icontains=q) |
            Q(private_class__trainer__username__icontains=q)
        )
    
    reviewd_certificates = (request.GET.get('reviewed') or '').strip().lower()
    if reviewd_certificates == 'true':
        review=Review.objects.filter(user=request.user).values_list('certificate_id', flat=True)
        certificates = certificates.filter(id__in=review)
    elif reviewd_certificates == 'false':
        review=Review.objects.filter(user=request.user).values_list('certificate_id', flat=True)
        certificates = certificates.exclude(id__in=review)

    issued_date_from = request.GET.get('date_from')
    issued_date_to = request.GET.get('date_to')
    if issued_date_from:
        certificates = certificates.filter(issued_at__date__gte=issued_date_from)
    if issued_date_to:
        certificates = certificates.filter(issued_at__date__lte=issued_date_to)

    reviewed_created_date_from = request.GET.get('reviewed_date_from')
    reviewed_created_date_to = request.GET.get('reviewed_date_to')
    if reviewed_created_date_from:
        reviews = Review.objects.filter(user=request.user, created_at__date__gte=reviewed_created_date_from).values_list('certificate_id', flat=True)
        certificates = certificates.filter(id__in=reviews)
    if reviewed_created_date_to:
        reviews = Review.objects.filter(user=request.user, created_at__date__lte=reviewed_created_date_to).values_list('certificate_id', flat=True)
        certificates = certificates.filter(id__in=reviews)

    certificate_card = []
    for certificate in certificates:
        if certificate.class_booking:
            trainer = certificate.class_booking.class_session.trainer
        elif certificate.private_class:
            trainer = certificate.private_class.trainer
        else:
            continue

        review = Review.objects.filter(user=request.user, certificate=certificate).first()

        certificate_card.append({
            'certificate': certificate,
            'trainer': trainer,
            'review': review,
        })

    context = {
        'certificate_card': certificate_card
    }
    return render(request, 'dashboards/user/reviews/user_select_trainer_from_certificate.html', context)


@login_required
def public_select_trainer_for_reviews(request):
    reviews = Review.objects.select_related(
        'user',
        'certificate',
        'certificate__class_booking__class_session__trainer',
        'certificate__private_class__trainer',
    ).order_by('-created_at')
    q = (request.GET.get('q') or '').strip().lower()

    trainer_map = {}

    for review in reviews:
        trainer = get_review_trainer(review)
        if not trainer:
            continue

        if trainer.pk not in trainer_map:
            trainer_map[trainer.pk] = {
                'trainer': trainer,
                'review_count': 0,
                'total_rating': 0,
            }

        trainer_map[trainer.pk]['review_count'] += 1
        trainer_map[trainer.pk]['total_rating'] += review.rating

    trainer_cards = []
    for row in trainer_map.values():
        if q:
            searchable = ' '.join([
                row['trainer'].username or '',
                row['trainer'].full_name or '',
                row['trainer'].specialization or '',
            ]).lower()
            if q not in searchable:
                continue

        trainer_cards.append({
            'trainer': row['trainer'],
            'review_count': row['review_count'],
            'average_rating': round(row['total_rating'] / row['review_count'], 1),
        })

    return render(request, 'reviews/public_select_trainer_for_reviews.html', {
        'trainer_cards': trainer_cards,
    })


@login_required
def public_trainer_review_list(request, trainer_id):
    reviews = Review.objects.select_related(
        'user',
        'certificate',
        'certificate__class_booking__class_session__trainer',
        'certificate__class_booking__class_session__pool',
        'certificate__private_class__trainer',
        'certificate__private_class__pool',
    ).order_by('-created_at')

    trainer = None
    review_rows = []

    rating = request.GET.get('rating')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    for review in reviews:
        review_trainer = get_review_trainer(review)
        if not review_trainer or review_trainer.pk != trainer_id:
            continue
        
        if rating:
            try:
                if review.rating != int(rating):
                    continue
            except ValueError:
                pass
        
        if date_from:
            try:
                date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                if review.created_at.date() < date_from_parsed:
                    continue
            except ValueError:
                pass
        if date_to:
            try:
                date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                if review.created_at.date() > date_to_parsed:
                    continue
            except ValueError:
                pass

        trainer = review_trainer
        review_rows.append({
            'review': review,
            'source_label': get_review_source_label(review),
        })

    if not trainer:
        messages.error(request, 'Trainer not found or no reviews available.')
        return redirect('public_select_trainer_for_reviews')

    total_reviews = len(review_rows)
    if total_reviews:
        total_rating = 0
        for row in review_rows:
            total_rating += row['review'].rating
        average_rating = round(total_rating / total_reviews, 1)
    else:
        average_rating = None

    return render(request, 'reviews/public_trainer_review_list.html', {
        'trainer': trainer,
        'review_rows': review_rows,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
    })


@login_required
def trainer_my_reviews(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    reviews = Review.objects.select_related(
        'user',
        'certificate',
        'certificate__class_booking__class_session__trainer',
        'certificate__class_booking__class_session__pool',
        'certificate__private_class__trainer',
        'certificate__private_class__pool',
    ).order_by('-created_at')
    q = (request.GET.get('q') or '').strip().lower()
    rating = (request.GET.get('rating') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    review_rows = []
    for review in reviews:
        review_trainer = get_review_trainer(review)
        if review_trainer and review_trainer.pk == request.user.pk:
            if rating:
                try:
                    if review.rating != int(rating):
                        continue
                except ValueError:
                    pass
            if date_from:
                try:
                    date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
                    if review.created_at.date() < date_from_parsed:
                        continue
                except ValueError:
                    pass
            if date_to:
                try:
                    date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
                    if review.created_at.date() > date_to_parsed:
                        continue
                except ValueError:
                    pass
            if q:
                username = (review.user.username or '').lower()
                full_name = (review.user.full_name or '').lower()
                comment = (review.comment or '').lower()
                source_label = get_review_source_label(review).lower()

                if q not in username and q not in full_name and q not in comment and q not in source_label:
                    continue
            review_rows.append({
                'review': review,
                'source_label': get_review_source_label(review),
            })

    total_reviews = len(review_rows)
    if total_reviews:
        total_rating = 0
        for row in review_rows:
            total_rating += row['review'].rating
        average_rating = round(total_rating / total_reviews, 1)
    else:
        average_rating = None

    return render(request, 'dashboards/trainer/reviews/trainer_my_reviews.html', {
        'review_rows': review_rows,
        'total_reviews': total_reviews,
        'average_rating': average_rating,
    })


@login_required
def admin_all_trainer_reviews(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    reviews = Review.objects.select_related(
        'user',
        'certificate',
        'certificate__class_booking__class_session__trainer',
        'certificate__class_booking__class_session__pool',
        'certificate__private_class__trainer',
        'certificate__private_class__pool',
    ).order_by('-created_at')

    rating = request.GET.get('rating')
    review_type = (request.GET.get('type') or '').strip().lower()

    review_rows = []

    q = (request.GET.get('q') or '').strip().lower()
    rating = request.GET.get('rating')
    review_type = (request.GET.get('type') or '').strip().lower()


    for review in reviews:
        trainer = get_review_trainer(review)
        if not trainer:
            continue

        source_label = get_review_source_label(review)
        source_type = 'group' if source_label.startswith('Group Class:') else 'private'

        if q:
            user_name =  ' '.join([review.user.username or '' or '', review.user.full_name or '']).lower()
            trainer_name = ' '.join([trainer.username or '', trainer.full_name or '']).lower()
            comment = (review.comment or '').lower()

            if q not in user_name and q not in trainer_name and q not in comment:
                continue

        if rating:
            try:
                if review.rating != int(rating):
                    continue
            except ValueError:
                pass

        if review_type and review_type != source_type:
            continue

        review_rows.append({
            'review': review,
            'trainer': trainer,
            'source_label': source_label,
            'source_type': source_type,
        })

    return render(request, 'dashboards/admin/reviews/admin_all_trainer_reviews.html', {
        'review_rows': review_rows,
        'q': q,
        'selected_rating': rating,
        'selected_type': review_type,
    })


@login_required
def user_review_trainer(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    existing_review = Review.objects.filter(user=request.user, certificate=certificate).first()
    if existing_review:
        return redirect('user_view_review', certificate_id=certificate_id)

    return redirect('user_create_review', certificate_id=certificate_id)


@login_required
def user_create_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    existing_review = Review.objects.filter(user=request.user, certificate=certificate).first()
    if existing_review:
        return redirect('user_view_review', certificate_id=certificate_id)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
        except (TypeError, ValueError):
            messages.error(request, "Please provide a valid rating.")
            return redirect('user_create_review', certificate_id=certificate_id)
        comment = request.POST.get('comment', '').strip()

        if rating < 1 or rating > 5:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect('user_create_review', certificate_id=certificate_id)

        Review.objects.create(
            user=request.user,
            certificate=certificate,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Your review has been submitted.")
        return redirect('user_view_review', certificate_id=certificate_id)

    context = {
        'certificate': certificate,
        'trainer': trainer,
    }
    return render(request, 'dashboards/user/reviews/user_review_trainer.html', context)


@login_required
def user_view_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)
    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'dashboards/user/reviews/user_view_review.html', context)


@login_required
def user_edit_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
        except (TypeError, ValueError):
            messages.error(request, "Please provide a valid rating.")
            return redirect('user_edit_review', certificate_id=certificate_id)

        comment = request.POST.get('comment', '').strip()

        if rating < 1 or rating > 5:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect('user_edit_review', certificate_id=certificate_id)

        review.rating = rating
        review.comment = comment
        review.save(update_fields=['rating', 'comment', 'updated_at'])

        messages.success(request, "Your review has been updated.")
        return redirect('user_view_review', certificate_id=certificate_id)

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'dashboards/user/reviews/user_review_trainer.html', context)


@login_required
def user_delete_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('user_select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)

    if request.method == 'POST':
        review.delete()
        messages.success(request, "Your review has been deleted.")
        return redirect('user_select_trainer_from_certificate')

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'dashboards/user/reviews/user_confirm_delete_review.html', context)
