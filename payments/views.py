import base64
import hashlib
import hmac
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from classes.models import ClassBooking, ClassSession, PrivateClass
from pool.models import Pool

from .models import Payment

import json


ESEWA_PRODUCT_CODE = getattr(settings, "ESEWA_PRODUCT_CODE", "EPAYTEST")
ESEWA_SECRET_KEY = getattr(settings, "ESEWA_SECRET_KEY", "8gBm/:&EnhH.1/q")
ESEWA_FORM_URL = getattr(
    settings,
    "ESEWA_FORM_URL",
    "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
)


def sign_esewa_payment(total_amount, transaction_uuid, product_code):
    message = (
        f"total_amount={total_amount},transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )
    digest = hmac.new(
        ESEWA_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode()


def build_esewa_fields(payment, success_url, failure_url):
    amount = str(payment.amount)
    tax_amount = str(payment.tax_amount)
    total_amount = str(payment.total_amount)
    service_charge = str(payment.service_charge)
    delivery_charge = str(payment.delivery_charge)
    transaction_uuid = str(payment.uid)

    return {
        "amount": amount,
        "tax_amount": tax_amount,
        "total_amount": total_amount,
        "transaction_uuid": transaction_uuid,
        "product_code": ESEWA_PRODUCT_CODE,
        "product_service_charge": service_charge,
        "product_delivery_charge": delivery_charge,
        "success_url": success_url,
        "failure_url": failure_url,
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": sign_esewa_payment(
            total_amount,
            transaction_uuid,
            ESEWA_PRODUCT_CODE,
        ),
    }


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

    success_url = request.build_absolute_uri(
        reverse("group_class_payment_success", kwargs={"uid": payment.uid})
    )
    failure_url = request.build_absolute_uri(
        reverse("group_class_payment_failure", kwargs={"uid": payment.uid})
    )
    esewa_fields = build_esewa_fields(payment, success_url, failure_url)

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
            "esewa_form_url": ESEWA_FORM_URL,
            "esewa_fields": esewa_fields,
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

    success_url = request.build_absolute_uri(
        reverse("private_class_payment_success", kwargs={"uid": payment.uid})
    )
    failure_url = request.build_absolute_uri(
        reverse("private_class_payment_failure", kwargs={"uid": payment.uid})
    )
    esewa_fields = build_esewa_fields(payment, success_url, failure_url)

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
            "esewa_form_url": ESEWA_FORM_URL,
            "esewa_fields": esewa_fields,
        },
    )


@login_required
def group_class_payment_success(request, uid):
    payment = get_object_or_404(Payment, uid=uid, purpose="group", user=request.user)
    class_session = payment.class_session

    data = request.GET.get("data")
    if not data:
        messages.error(request, "Payment verification failed. No data received.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")
    
    try:
        decoded_data = base64.b64decode(data).decode()
        payment_data = json.loads(decoded_data)
    except (base64.binascii.Error, ValueError):
        messages.error(request, "Payment verification failed. Invalid data format.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")


    if str(payment_data.get("transaction_uuid")) != str(payment.uid):
        messages.error(request, "Payment verification failed. Transaction ID mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if str(payment_data.get("total_amount")) != str(payment.total_amount):
        messages.error(request, "Payment verification failed. Amount mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if str(payment_data.get("product_code")) != ESEWA_PRODUCT_CODE:
        messages.error(request, "Payment verification failed. Product code mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if payment_data.get("status") != "COMPLETE":
        messages.error(request, "Payment was not completed.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")



    if not class_session:
        messages.error(request, "Associated class session not found.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if class_session.is_cancelled:
        messages.error(request, "This class session was cancelled.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if class_session.end_date and class_session.end_date < datetime.now().date():
        messages.error(request, "This class session has already ended.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    if class_session.total_bookings >= class_session.seats:
        messages.error(request, "This class session is already full.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("my_bookings")

    existing_booking = ClassBooking.objects.filter(
        user=request.user,
        class_session=class_session,
        is_cancelled=False,
    ).first()

    if existing_booking:
        payment.class_booking = existing_booking
        payment.payment_status = "Completed"
        payment.save(update_fields=["class_booking", "payment_status"])
        return render(request, "payments/payment_success.html", {"payment": payment})

    booking = ClassBooking.objects.create(
        user=request.user,
        class_session=class_session,
    )
    payment.class_booking = booking
    payment.payment_status = "Completed"
    payment.save(update_fields=["class_booking", "payment_status"])

    class_session.total_bookings += 1
    class_session.save(update_fields=["total_bookings"])

    return render(request, "payments/payment_success.html", {"payment": payment})


@login_required
def group_class_payment_failure(request, uid):
    payment = get_object_or_404(Payment, uid=uid, purpose="group", user=request.user)
    if payment.payment_status == "Pending":
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
    return render(request, "payments/payment_failure.html", {"payment": payment})


@login_required
def private_class_payment_success(request, uid):
    payment = get_object_or_404(Payment, uid=uid, purpose="private", user=request.user)
    data = request.GET.get("data")
    if not data:
        messages.error(request, "Payment verification failed. No data received.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    try:
        decoded_data = base64.b64decode(data).decode()
        payment_data = json.loads(decoded_data)
    except (base64.binascii.Error, ValueError):
        messages.error(request, "Payment verification failed. Invalid data format.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    if str(payment_data.get("transaction_uuid")) != str(payment.uid):
        messages.error(request, "Payment verification failed. Transaction ID mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    if str(payment_data.get("total_amount")) != str(payment.total_amount):
        messages.error(request, "Payment verification failed. Amount mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    if str(payment_data.get("product_code")) != ESEWA_PRODUCT_CODE:
        messages.error(request, "Payment verification failed. Product code mismatch.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    if payment_data.get("status") != "COMPLETE":
        messages.error(request, "Payment was not completed.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    checkout_data = payment.extra_payload or {}
    try:
        pool = get_object_or_404(Pool, pk=int(checkout_data["pool_id"]), is_closed=False)
        trainer = get_object_or_404(User, pk=int(checkout_data["trainer_id"]), role="trainer")
        start_date = datetime.strptime(checkout_data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(checkout_data["end_date"], "%Y-%m-%d").date()
        start_time = datetime.strptime(checkout_data["start_time"], "%H:%M").time()
        end_time = datetime.strptime(checkout_data["end_time"], "%H:%M").time()
    except (KeyError, TypeError, ValueError):
        messages.error(request, "Private class payment details are invalid.")
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
        return redirect("private_class_payment_failure", uid=payment.uid)

    if payment.private_class:
        payment.payment_status = "Completed"
        payment.save(update_fields=["payment_status"])
        return render(request, "payments/payment_success.html", {"payment": payment})

    private_class = PrivateClass.objects.create(
        user=request.user,
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
    return render(request, "payments/payment_success.html", {"payment": payment})


@login_required
def private_class_payment_failure(request, uid):
    payment = get_object_or_404(Payment, uid=uid, purpose="private", user=request.user)
    if payment.payment_status == "Pending":
        payment.payment_status = "Failed"
        payment.save(update_fields=["payment_status"])
    return render(request, "payments/payment_failure.html", {"payment": payment})


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
def payment_report(request):
    cutoff_time = timezone.now() - timedelta(minutes=15)
    Payment.objects.filter(
        user=request.user,
        payment_status="Pending",
        payment_date__lt=cutoff_time,
    ).update(payment_status="Cancelled")

    payments = Payment.objects.filter(user=request.user).order_by("-payment_date")
    return render(request, "payments/payment_report.html", {"payments": payments})


@login_required
def admin_payment_report(request):
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("home")

    cutoff_time = timezone.now() - timedelta(minutes=15)
    Payment.objects.filter(
        payment_status="Pending",
        payment_date__lt=cutoff_time,
    ).update(payment_status="Cancelled")

    payments = Payment.objects.all().order_by("-payment_date")
    return render(request, "payments/admin_payment_report.html", {"payments": payments})
