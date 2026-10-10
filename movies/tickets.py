import base64
from io import BytesIO
from email.mime.image import MIMEImage

import qrcode
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


def verification_url(request, booking):
    path = reverse(
        "verify_ticket",
        kwargs={"verification_token": booking.verification_token},
    )
    return request.build_absolute_uri(path)


def qr_png_bytes(url):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=7,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#10151d", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def qr_data_uri(url):
    image = base64.b64encode(qr_png_bytes(url)).decode("ascii")
    return f"data:image/png;base64,{image}"


def send_booking_confirmation(request, booking):
    if settings.EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        raise OSError(
            "Email is configured for console output, not delivery. "
            "Set EMAIL_HOST and the SMTP credentials in .env."
        )

    showtime = booking.showtime
    verify_url = verification_url(request, booking)
    email_context = {
        "booking": booking,
        "showtime": showtime,
        "theatre": showtime.screen.theatre,
        "verification_url": verify_url,
        "ticket_breakdown": [
            {
                "seat": seat,
                "price": showtime.price_for_seat(seat),
            }
            for seat in booking.selected_seats
        ],
    }
    message = EmailMultiAlternatives(
        subject=f"CineBook reservation {booking.confirmation_token}",
        body=render_to_string(
            "movies/emails/booking_confirmation.txt",
            email_context,
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[booking.customer_email],
    )
    message.attach_alternative(
        render_to_string(
            "movies/emails/booking_confirmation.html",
            email_context,
        ),
        "text/html",
    )
    qr_image = MIMEImage(qr_png_bytes(verify_url), _subtype="png")
    qr_image.add_header("Content-ID", "<cinebook-ticket-qr>")
    qr_image.add_header(
        "Content-Disposition",
        "inline",
        filename="cinebook-ticket-qr.png",
    )
    message.attach(qr_image)
    sent = message.send(fail_silently=False)
    if sent != 1:
        raise OSError("The configured email backend did not send the message.")
    booking.confirmation_email_sent = True
    booking.save(update_fields=["confirmation_email_sent"])
