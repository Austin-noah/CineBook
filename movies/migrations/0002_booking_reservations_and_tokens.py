import re
import uuid

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def populate_booking_data(apps, schema_editor):
    SeatBooking = apps.get_model("movies", "SeatBooking")
    SeatReservation = apps.get_model("movies", "SeatReservation")
    database = schema_editor.connection.alias
    reservations = []

    for booking in SeatBooking.objects.using(database).order_by("pk").iterator():
        if not booking.confirmation_token:
            booking.confirmation_token = uuid.uuid4()
            booking.save(using=database, update_fields=["confirmation_token"])

        if not isinstance(booking.selected_seats, list):
            continue

        for seat in booking.selected_seats:
            if isinstance(seat, str) and re.fullmatch(r"[A-E][1-8]", seat):
                reservations.append(
                    SeatReservation(
                        booking_id=booking.pk,
                        showtime_id=booking.showtime_id,
                        seat_number=seat,
                    )
                )

    SeatReservation.objects.using(database).bulk_create(
        reservations,
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("movies", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="seatbooking",
            name="confirmation_token",
            field=models.UUIDField(
                editable=False,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="SeatReservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "seat_number",
                    models.CharField(
                        max_length=2,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a seat from A1 through E8.",
                                regex="^[A-E][1-8]$",
                            )
                        ],
                    ),
                ),
                (
                    "booking",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to="movies.seatbooking",
                    ),
                ),
                (
                    "showtime",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="seat_reservations",
                        to="movies.showtime",
                    ),
                ),
            ],
            options={
                "ordering": ("seat_number",),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("showtime", "seat_number"),
                        name="unique_seat_per_showtime",
                    )
                ],
            },
        ),
        migrations.RunPython(
            populate_booking_data,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="seatbooking",
            name="confirmation_token",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="moviereview",
            name="rating",
            field=models.PositiveSmallIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
            ),
        ),
    ]
