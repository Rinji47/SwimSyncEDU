from django.shortcuts import get_object_or_404, render
from classes.models import CompletionCertificate
from .models import Review
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

# Create your views here.

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
def select_trainer_from_certificate(request):
    certificates = CompletionCertificate.objects.filter(user=request.user)

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
    return render(request, 'reviews/select_trainer_from_certificate.html', context)


@login_required
def review_trainer(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    existing_review = Review.objects.filter(user=request.user, certificate=certificate).first()
    if existing_review:
        return redirect('view_review', certificate_id=certificate_id)

    return redirect('create_review', certificate_id=certificate_id)


@login_required
def create_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    existing_review = Review.objects.filter(user=request.user, certificate=certificate).first()
    if existing_review:
        return redirect('view_review', certificate_id=certificate_id)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
        except (TypeError, ValueError):
            messages.error(request, "Please provide a valid rating.")
            return redirect('create_review', certificate_id=certificate_id)
        comment = request.POST.get('comment', '').strip()

        if rating < 1 or rating > 5:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect('create_review', certificate_id=certificate_id)

        Review.objects.create(
            user=request.user,
            certificate=certificate,
            rating=rating,
            comment=comment
        )
        messages.success(request, "Your review has been submitted.")
        return redirect('view_review', certificate_id=certificate_id)

    context = {
        'certificate': certificate,
        'trainer': trainer,
    }
    return render(request, 'reviews/review_trainer.html', context)


@login_required
def view_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)
    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'reviews/view_review.html', context)


@login_required
def edit_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating'))
        except (TypeError, ValueError):
            messages.error(request, "Please provide a valid rating.")
            return redirect('edit_review', certificate_id=certificate_id)

        comment = request.POST.get('comment', '').strip()

        if rating < 1 or rating > 5:
            messages.error(request, "Rating must be between 1 and 5.")
            return redirect('edit_review', certificate_id=certificate_id)

        review.rating = rating
        review.comment = comment
        review.save(update_fields=['rating', 'comment', 'updated_at'])

        messages.success(request, "Your review has been updated.")
        return redirect('view_review', certificate_id=certificate_id)

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'reviews/review_trainer.html', context)


def render_to_pdf(template_src, context_dict):
    template = get_template(template_src)
    html = template.render(context_dict)
    response = HttpResponse(content_type='application/pdf')
    result = pisa.CreatePDF(html, dest=response)
    if result.err:
        return None
    return response

@login_required
def export_certificate_pdf(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    context = {
        'certificate': certificate,
        'trainer': trainer
    }

    pdf_response = render_to_pdf('reviews/view_certificate_pdf.html', context)
    if pdf_response is None:
        messages.error(request, "Error generating PDF.")
        return redirect('view_certificate', certificate_id=certificate_id)
    
    pdf_response['Content-Disposition'] = f'attachment; filename="certificate_{certificate_id}.pdf"'
    return pdf_response

@login_required
def view_certificate(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    context = {
        'certificate': certificate,
        'trainer': trainer
    }
    return render(request, 'reviews/view_certificate.html', context)


@login_required
def delete_review(request, certificate_id):
    certificate, trainer = get_certificate_and_trainer(request, certificate_id)
    if not trainer:
        messages.error(request, "Invalid certificate.")
        return redirect('select_trainer_from_certificate')

    review = get_object_or_404(Review, user=request.user, certificate=certificate)

    if request.method == 'POST':
        review.delete()
        messages.success(request, "Your review has been deleted.")
        return redirect('select_trainer_from_certificate')

    context = {
        'certificate': certificate,
        'trainer': trainer,
        'review': review,
    }
    return render(request, 'reviews/confirm_delete_review.html', context)