from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from classes.models import ClassBooking, ClassSession, PrivateClass
from pool.models import Pool

from .models import Payment

KHALTI_SECRET_KEY = getattr(settings, "KHALTI_SECRET_KEY", "").strip()
KHALTI_INITIATE_URL = getattr(
    settings,
    "KHALTI_INITIATE_URL",
    "https://a.khalti.com/api/v2/epayment/initiate/",
)
KHALTI_LOOKUP_URL = getattr(
    settings,
    "KHALTI_LOOKUP_URL",
    "https://a.khalti.com/api/v2/epayment/lookup/",
)


def khalti_request_json(url, payload):
    if not KHALTI_SECRET_KEY:
        return None, "Khalti secret key is not configured."

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=25,
            headers={
                "Authorization": f"Key {KHALTI_SECRET_KEY}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        return response.json(), None
    except requests.HTTPError as exc:
        try:
            body = exc.response.json()
        except ValueError:
            if exc.response is not None:
                body = exc.response.text 
            else:
                body = str(exc)
        return None, body
    except requests.RequestException as exc:
        return None, str(exc)


def khalti_return_url(request, payment):
    return request.build_absolute_uri(
        reverse("khalti_payment_verify", kwargs={"uid": payment.uid})
    )


def khalti_website_url(request):
    return f"{request.scheme}://{request.get_host()}"


def complete_group_payment(payment):
    class_session = payment.class_session

    if not class_session:
        return False, "Associated class session not found."

    if class_session.is_cancelled:
        return False, "This class session was cancelled."

    if class_session.end_date and class_session.end_date < datetime.now().date():
        return False, "This class session has already ended."

    if class_session.total_bookings >= class_session.seats:
        return False, "This class session is already full."

    existing_booking = ClassBooking.objects.filter(
        user=payment.user,
        class_session=class_session,
        is_cancelled=False,
    ).first()

    if existing_booking:
        payment.class_booking = existing_booking
        payment.payment_status = "Completed"
        payment.save(update_fields=["class_booking", "payment_status"])
        return True, None

    booking = ClassBooking.objects.create(
        user=payment.user,
        class_session=class_session,
    )
    payment.class_booking = booking
    payment.payment_status = "Completed"
    payment.save(update_fields=["class_booking", "payment_status"])

    class_session.total_bookings += 1
    class_session.save(update_fields=["total_bookings"])
    return True, None


def complete_private_payment(payment):
    checkout_data = payment.extra_payload or {}
    try:
        pool = get_object_or_404(Pool, pk=int(checkout_data["pool_id"]), is_closed=False)
        trainer = get_object_or_404(User, pk=int(checkout_data["trainer_id"]), role="trainer")
        start_date = datetime.strptime(checkout_data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(checkout_data["end_date"], "%Y-%m-%d").date()
        start_time = datetime.strptime(checkout_data["start_time"], "%H:%M").time()
        end_time = datetime.strptime(checkout_data["end_time"], "%H:%M").time()
    except (KeyError, TypeError, ValueError):
        return False, "Private class payment details are invalid."

    if payment.private_class:
        payment.payment_status = "Completed"
        payment.save(update_fields=["payment_status"])
        return True, None

    private_class = PrivateClass.objects.create(
        user=payment.user,
        trainer=trainer,
        pool=pool,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
    )

    payment.private_class = private_class
    payment.payment_status = "Completed"
    payment.save(update_fields=["private_class", "payment_status"])
    return True, None


@login_required
def group_class_payment_checkout(request, class_id):
    class_session = get_object_or_404(ClassSession, id=class_id)

    if class_session.is_cancelled:
        messages.error(request, "This class session has been cancelled. Payment cannot be processed.")
        return redirect("pool_classes", class_session.pool_id, class_session.class_type_id)

    if class_session.end_date and class_session.end_date < datetime.now().date():
        messages.error(request, "This class session has already ended. Payment cannot be processed.")
        return redirect("pool_classes", class_session.pool_id, class_session.class_type_id)

    if class_session.total_bookings >= class_session.seats:
        messages.error(request, "This class session is fully booked. Payment cannot be processed.")
        return redirect("pool_classes", class_session.pool_id, class_session.class_type_id)

    if class_session.start_date and class_session.start_date < datetime.now().date():
        messages.error(request, "This class session has already started. Payment cannot be processed.")
        return redirect("pool_classes", class_session.pool_id, class_session.class_type_id)

    if ClassBooking.objects.filter(
        user=request.user,
        class_session=class_session,
        is_cancelled=False,
    ).exists():
        messages.error(request, "You have already booked this class.")
        return redirect("my_bookings")

    base_amount = Decimal(class_session.total_price or 0)
    tax_amount = base_amount * Decimal("0.13")
    service_charge = Decimal("0.00")
    delivery_charge = Decimal("0.00")
    total_amount = base_amount + tax_amount + service_charge + delivery_charge

    Payment.objects.filter(
        user=request.user,
        purpose="group",
        class_session=class_session,
        payment_status="Pending",
    ).update(payment_status="Cancelled")

    payment = Payment.objects.create(
        uid=uuid4(),
        user=request.user,
        purpose="group",
        class_session=class_session,
        amount=base_amount,
        tax_amount=tax_amount,
        service_charge=service_charge,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        payment_method="Online",
        payment_status="Pending",
    )

    return render(
        request,
        "payments/group_class_payment.html",
        {
            "class_session": class_session,
            "base_amount": base_amount,
            "tax_amount": tax_amount,
            "service_charge": service_charge,
            "delivery_charge": delivery_charge,
            "total_amount": total_amount,
            "khalti_start_url": reverse("khalti_payment_start", kwargs={"uid": payment.uid}),
        },
    )


@login_required
def private_class_payment_checkout(request):
    checkout_data = request.session.get("private_class_checkout")
    if not checkout_data:
        messages.error(request, "No private class payment details were found.")
        return redirect("nearby_pools")

    try:
        pool_id = int(checkout_data["pool_id"])
        trainer_id = int(checkout_data["trainer_id"])
        start_date = datetime.strptime(checkout_data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(checkout_data["end_date"], "%Y-%m-%d").date()
        start_time = datetime.strptime(checkout_data["start_time"], "%H:%M").time()
        end_time = datetime.strptime(checkout_data["end_time"], "%H:%M").time()
        weekdays_count = int(checkout_data["weekdays_count"])
        price_per_day = Decimal(checkout_data["price_per_day"])
        base_amount = Decimal(checkout_data["base_amount"])
        tax_amount = Decimal(checkout_data["tax_amount"])
        total_amount = Decimal(checkout_data["total_amount"])
    except (KeyError, TypeError, ValueError):
        messages.error(request, "Private class payment data is invalid.")
        request.session.pop("private_class_checkout", None)
        return redirect("nearby_pools")

    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainer = get_object_or_404(User, pk=trainer_id, role="trainer")
    service_charge = Decimal("0.00")
    delivery_charge = Decimal("0.00")

    Payment.objects.filter(
        user=request.user,
        purpose="private",
        payment_status="Pending",
    ).update(payment_status="Cancelled")

    payment = Payment.objects.create(
        uid=uuid4(),
        user=request.user,
        purpose="private",
        amount=base_amount,
        tax_amount=tax_amount,
        service_charge=service_charge,
        delivery_charge=delivery_charge,
        total_amount=total_amount,
        payment_method="Online",
        payment_status="Pending",
        extra_payload={
            "pool_id": pool_id,
            "trainer_id": trainer_id,
            "start_date": checkout_data["start_date"],
            "end_date": checkout_data["end_date"],
            "start_time": checkout_data["start_time"],
            "end_time": checkout_data["end_time"],
        },
    )

    return render(
        request,
        "payments/private_class_payment.html",
        {
            "pool": pool,
            "trainer": trainer,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": start_time,
            "end_time": end_time,
            "weekdays_count": weekdays_count,
            "price_per_day": price_per_day,
            "base_amount": base_amount,
            "tax_amount": tax_amount,
            "service_charge": service_charge,
            "delivery_charge": delivery_charge,
            "total_amount": total_amount,
            "khalti_start_url": reverse("khalti_payment_start", kwargs={"uid": payment.uid}),
        },
    )


@login_required
def khalti_payment_start(request, uid):
    payment = get_object_or_404(Payment, uid=uid, user=request.user, payment_status="Pending")

    return_url = khalti_return_url(request, payment)
    payload = {
        "return_url": return_url,
        "website_url": khalti_website_url(request),
        "amount": int(payment.total_amount * 100),
        "purchase_order_id": str(payment.uid),
        "purchase_order_name": f"{payment.purpose.title()} Payment",
    }
    data, error = khalti_request_json(KHALTI_INITIATE_URL, payload)

    if error or not data or not data.get("payment_url"):
        messages.error(request, "Failed to start Khalti payment. Please try again.")
        payment.gateway_response = {"init_error": error, "response": data}
        payment.save(update_fields=["gateway_response"])

        if payment.purpose == "group" and payment.class_session:
            return redirect("group_class_payment_checkout", class_id=payment.class_session.id)
        return redirect("private_class_payment_checkout")

    payment.extra_payload = {
        **(payment.extra_payload or {}),
        "gateway": "khalti",
        "khalti_pidx": data.get("pidx"),
    }
    payment.gateway_response = data
    payment.save(update_fields=["extra_payload", "gateway_response"])
    return redirect(data["payment_url"])

@login_required
def khalti_payment_verify(request, uid):
    payment = get_object_or_404(Payment, uid=uid, user=request.user)
    pidx = request.GET.get("pidx")
    
    purchase_order_id = request.GET.get("purchase_order_id")
    if purchase_order_id and str(purchase_order_id) != str(payment.uid):
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        messages.error(request, "Purchase order ID mismatch. Payment verification failed.")
        return render(request, "payments/payment_failure.html", {"payment": payment})

    if payment.payment_status == "Completed":
        return render(request, "payments/payment_success.html", {"payment": payment})

    if not pidx:
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        messages.error(request, "Khalti payment verification failed.")
        return render(request, "payments/payment_failure.html", {"payment": payment})

    data, error = khalti_request_json(KHALTI_LOOKUP_URL, {"pidx": pidx})

    if error or not data:
        payment.payment_status = "Failed"
        payment.gateway_response = {"lookup_error": error, "response": data}
        payment.save(update_fields=["payment_status", "gateway_response"])
        messages.error(request, "Could not verify Khalti payment.")
        return render(request, "payments/payment_failure.html", {"payment": payment})

    payment.gateway_response = data
    payment.save(update_fields=["gateway_response"])

    if data.get("status") != "Completed":
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        messages.error(request, "Payment was not completed in Khalti.")
        return render(request, "payments/payment_failure.html", {"payment": payment})

    expected_amount = int(payment.total_amount * 100)
    if int(data.get("total_amount", 0)) != expected_amount:
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        messages.error(request, "Khalti verification mismatch detected.")
        return render(request, "payments/payment_failure.html", {"payment": payment})

    if payment.purpose == "group":
        ok, error_message = complete_group_payment(payment)
    else:
        ok, error_message = complete_private_payment(payment)

    if not ok:
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        messages.error(request, error_message)
        return render(request, "payments/payment_failure.html", {"payment": payment})

    return render(request, "payments/payment_success.html", {"payment": payment})

@login_required
def group_class_payment_cancel(request, class_id):
    class_session = get_object_or_404(ClassSession, id=class_id)
    Payment.objects.filter(
        user=request.user,
        purpose="group",
        class_session=class_session,
        payment_status="Pending",
    ).update(payment_status="Cancelled")
    return redirect("pool_classes", class_session.pool_id, class_session.class_type_id)


@login_required
def private_class_payment_cancel(request):
    Payment.objects.filter(
        user=request.user,
        purpose="private",
        payment_status="Pending",
    ).update(payment_status="Cancelled")
    request.session.pop("private_class_checkout", None)
    return redirect("nearby_pools")


@login_required
def user_payment_report(request):
    cutoff_time = timezone.now() - timedelta(minutes=15)

    Payment.objects.filter(
        user=request.user,
        payment_status="Pending",
        payment_date__lt=cutoff_time,
    ).update(payment_status="Cancelled")
    
    payments = Payment.objects.filter(user=request.user).order_by("-payment_date")
    
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status", "")).strip()
    purpose = (request.GET.get("purpose", "")).strip()
    method = (request.GET.get("method", "")).strip()
    date_from = (request.GET.get("date_from", "")).strip()
    date_to = (request.GET.get("date_to", "")).strip()

    if q:
        payments = payments.filter(
            Q(user__username__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__phone__icontains=q)
        )

    if status:
        payments = payments.filter(payment_status=status)
    
    if purpose:
        payments = payments.filter(purpose=purpose)

    if method:
        payments = payments.filter(payment_method=method)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            payments = payments.filter(payment_date__date__gte=date_from_obj)
        except ValueError:
            messages.warning(request, "Invalid date format for 'From' date. Use YYYY-MM-DD.")

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            payments = payments.filter(payment_date__date__lte=date_to_obj)
        except ValueError:
            messages.warning(request, "Invalid date format for 'To' date. Use YYYY-MM-DD.")

    summary = payments.aggregate(
        total_records=Count("id"),
        completed_count=Count("id", filter=Q(payment_status="Completed")),
        pending_count=Count("id", filter=Q(payment_status="Pending")),
        cancelled_count=Count("id", filter=Q(payment_status="Cancelled")),
        failed_count=Count("id", filter=Q(payment_status="Failed")),
        total_spend=Sum("total_amount", filter=Q(payment_status="Completed")),
    )

    return render(
        request,
        "dashboards/user/payments/payment_report.html",
        {
            "payments": payments,
            "summary": summary,
        },
    )


@login_required
def admin_payment_report(request):
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("index")

    cutoff_time = timezone.now() - timedelta(minutes=15)
    Payment.objects.filter(
        payment_status="Pending",
        payment_date__lt=cutoff_time,
    ).update(payment_status="Cancelled")

    payments = Payment.objects.select_related("user").all().order_by("-payment_date")

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status", "")).strip()
    purpose = (request.GET.get("purpose", "")).strip()
    method = (request.GET.get("method", "")).strip()
    date_from = (request.GET.get("date_from", "")).strip()
    date_to = (request.GET.get("date_to", "")).strip()

    if q:
        payments = payments.filter(
            Q(user__username__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__email__icontains=q) |
            Q(user__phone__icontains=q)
        )

    if status:
        payments = payments.filter(payment_status=status)
    
    if purpose:
        payments = payments.filter(purpose=purpose)

    if method:
        payments = payments.filter(payment_method=method)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d")
            payments = payments.filter(payment_date__date__gte=date_from_obj)
        except ValueError:
            messages.warning(request, "Invalid date format for 'From' date. Use YYYY-MM-DD.")

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d")
            payments = payments.filter(payment_date__date__lte=date_to_obj)
        except ValueError:
            messages.warning(request, "Invalid date format for 'To' date. Use YYYY-MM-DD.")


    summary = payments.aggregate(
        total_records=Count("id"),
        completed_count=Count("id", filter=Q(payment_status="Completed")),
        pending_count=Count("id", filter=Q(payment_status="Pending")),
        cancelled_count=Count("id", filter=Q(payment_status="Cancelled")),
        failed_count=Count("id", filter=Q(payment_status="Failed")),
        collected_total=Sum("total_amount", filter=Q(payment_status="Completed")),
    )

    return render(
        request,
        "dashboards/admin/payments/admin_payment_report.html",
        {
            "payments": payments,
            "summary": summary,
        },
    )
