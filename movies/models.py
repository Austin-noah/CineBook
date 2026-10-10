
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Movie(models.Model):
    class Status(models.TextChoices):
        NOW_SHOWING = "now_showing", "Now showing"
        UPCOMING = "upcoming", "Upcoming"
        CATALOGUE = "catalogue", "Catalogue"

    title = models.CharField(max_length=200)
    genre = models.CharField(max_length=100)
    duration = models.PositiveIntegerField(help_text="Duration in minutes")
    release_date = models.DateField()
    language = models.CharField(max_length=40, default="English")
    poster_url = models.URLField(blank=True)
    backdrop_url = models.URLField(blank=True)
    description = models.TextField()
    catalogue_rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        blank=True,
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text="Optional external catalogue rating out of 10.",
    )
    catalogue_rating_source = models.CharField(max_length=100, blank=True)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CATALOGUE,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return self.title


class MoviePerson(models.Model):
    class Role(models.TextChoices):
        DIRECTOR = "director", "Director"
        MAIN_CAST = "main_cast", "Main cast"
        SUPPORTING_CAST = "supporting_cast", "Supporting cast"
        MUSIC_DIRECTOR = "music_director", "Music director"
        CINEMATOGRAPHER = "cinematographer", "Cinematographer"

    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="cast_and_crew",
    )
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=24, choices=Role.choices)
    character_name = models.CharField(max_length=150, blank=True)
    profile_image_url = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "name")

    def __str__(self):
        if self.character_name:
            return f"{self.name} as {self.character_name}"
        return f"{self.name} — {self.get_role_display()}"


class Showtime(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="showtimes"
    )
    screen = models.ForeignKey(
        "Screen",
        on_delete=models.PROTECT,
        related_name="showtimes",
    )
    show_date = models.DateField()
    show_time = models.TimeField()
    ticket_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[MinValueValidator(0.01)],
    )
    upper_ticket_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        default=Decimal("250.00"),
        validators=[MinValueValidator(0.01)],
    )
    middle_ticket_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        default=Decimal("150.00"),
        validators=[MinValueValidator(0.01)],
    )
    ground_ticket_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
        default=Decimal("100.00"),
        validators=[MinValueValidator(0.01)],
    )
    demo_seed_key = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        unique=True,
        editable=False,
    )
    language = models.CharField(max_length=40, blank=True)
    subtitle_languages = models.CharField(
        max_length=150,
        blank=True,
        help_text="Comma-separated subtitle languages configured for this show.",
    )
    format = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    booking_open = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("screen", "show_date", "show_time"),
                name="unique_screen_showtime_start",
            ),
            models.CheckConstraint(
                condition=Q(ticket_price__gt=0),
                name="showtime_ticket_price_positive",
            ),
        ]

    @property
    def city(self):
        return self.screen.theatre.city

    @property
    def screen_number(self):
        return self.screen.name

    @property
    def end_time(self):
        start = datetime.combine(self.show_date, self.show_time)
        return (start + timedelta(minutes=self.movie.duration)).time()

    def price_for_seat(self, seat_number):
        section = seat_number[:1]
        section_price = {
            "U": self.upper_ticket_price,
            "M": self.middle_ticket_price,
            "G": self.ground_ticket_price,
        }.get(section)
        return section_price if section_price is not None else self.ticket_price

    def clean(self):
        super().clean()
        if not (
            self.screen_id
            and self.movie_id
            and self.show_date
            and self.show_time
        ):
            return

        start = datetime.combine(self.show_date, self.show_time)
        end = start + timedelta(minutes=self.movie.duration + 20)
        other_shows = (
            Showtime.objects.filter(
                screen_id=self.screen_id,
                show_date__range=(
                    self.show_date - timedelta(days=1),
                    self.show_date + timedelta(days=1),
                ),
            )
            .exclude(pk=self.pk)
            .select_related("movie")
        )
        for other in other_shows:
            other_start = datetime.combine(other.show_date, other.show_time)
            other_end = other_start + timedelta(
                minutes=other.movie.duration + 20
            )
            if start < other_end and other_start < end:
                raise ValidationError(
                    {
                        "show_time": (
                            f"This screen is already scheduled for "
                            f"{other.movie.title} at "
                            f"{other.show_time:%H:%M}."
                        )
                    }
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.movie.title} - {self.show_date} {self.show_time}"


class Theatre(models.Model):
    class CinemaType(models.TextChoices):
        SINGLE_SCREEN = "single_screen", "Single screen"
        MULTIPLEX = "multiplex", "Multiplex"

    class SeatLayout(models.TextChoices):
        CLASSIC = "classic", "Classic"
        WIDE = "wide", "Wide"
        STADIUM = "stadium", "Stadium"
        COMPACT = "compact", "Compact"

    name = models.CharField(max_length=150)
    city = models.CharField(max_length=100, default="Hyderabad")
    cinema_type = models.CharField(
        max_length=20,
        choices=CinemaType.choices,
        default=CinemaType.MULTIPLEX,
    )
    seat_layout_style = models.CharField(
        max_length=12,
        choices=SeatLayout.choices,
        default=SeatLayout.CLASSIC,
        help_text="The fixed seating arrangement used by every screen here.",
    )
    address = models.CharField(max_length=250, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    is_demo = models.BooleanField(
        default=False,
        help_text="Mark sample listings so visitors know they are demonstrations.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("name", "city"),
                name="unique_theatre_name_per_city",
            )
        ]
        ordering = ("city", "name")

    def __str__(self):
        return f"{self.name} — {self.city}"


class Screen(models.Model):
    class ScreenType(models.TextChoices):
        STANDARD = "standard", "Standard"
        PREMIUM = "premium", "Premium"
        IMAX = "imax", "IMAX"

    theatre = models.ForeignKey(
        Theatre,
        on_delete=models.CASCADE,
        related_name="screens",
    )
    name = models.CharField(max_length=80)
    screen_type = models.CharField(
        max_length=20,
        choices=ScreenType.choices,
        default=ScreenType.STANDARD,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("theatre", "name"),
                name="unique_screen_name_per_theatre",
            ),
        ]
        ordering = ("theatre", "name")

    def seat_numbers(self):
        return tuple(
            seat
            for section in self.seat_layout
            for row in section["rows"]
            for seat in row
        )

    @property
    def seat_layout(self):
        row_widths = {
            Theatre.SeatLayout.CLASSIC: {
                "G": (10, 10, 10),
                "M": (10, 10, 10, 10, 10),
                "U": (10, 10),
            },
            Theatre.SeatLayout.WIDE: {
                "G": (10, 10, 10),
                "M": (10, 10, 10, 10, 10),
                "U": (10, 10),
            },
            Theatre.SeatLayout.STADIUM: {
                "G": (10, 10, 10),
                "M": (10, 10, 10, 10, 10),
                "U": (10, 10),
            },
            Theatre.SeatLayout.COMPACT: {
                "G": (10, 10, 10),
                "M": (10, 10, 10, 10, 10),
                "U": (10, 10),
            },
        }[self.theatre.seat_layout_style]
        section_names = {
            "G": "Ground (closest to screen)",
            "M": "Middle",
            "U": "Upper (rear)",
        }
        sections = []
        for code in ("G", "M", "U"):
            next_number = 1
            rows = []
            for width in row_widths[code]:
                rows.append(
                    tuple(
                        f"{code}{number:02d}"
                        for number in range(next_number, next_number + width)
                    )
                )
                next_number += width
            sections.append(
                {
                    "code": code,
                    "name": section_names[code],
                    "count": next_number - 1,
                    "rows": tuple(rows),
                }
            )
        return tuple(sections)

    @property
    def seat_capacity(self):
        return 100

    def __str__(self):
        return f"{self.theatre.name} — {self.name}"


class SeatBooking(models.Model):
    showtime = models.ForeignKey(
        Showtime,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30, blank=True)
    selected_seats = models.JSONField()
    total_paid = models.DecimalField(
        "total due",
        max_digits=10,
        decimal_places=2,
    )
    confirmation_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    verification_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    confirmation_email_sent = models.BooleanField(default=False)
    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.customer_name} - {self.showtime}"


class SeatReservation(models.Model):
    booking = models.ForeignKey(
        SeatBooking,
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    showtime = models.ForeignKey(
        Showtime,
        on_delete=models.CASCADE,
        related_name="seat_reservations",
    )
    seat_number = models.CharField(
        max_length=4,
        validators=[
            RegexValidator(
                regex=r"^(?:[GMU]\d{2}|[A-Z](?:[1-9]|[1-9][0-9]))$",
                message="Enter a section seat such as G01, M01 or U01.",
            )
        ],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("showtime", "seat_number"),
                name="unique_seat_per_showtime",
            )
        ]
        ordering = ("seat_number",)

    def __str__(self):
        return f"{self.showtime} - {self.seat_number}"


class MovieReview(models.Model):
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="reviews"
    )
    reviewer_name = models.CharField(max_length=100)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.movie.title} - {self.rating}/5"

    def clean(self):
        from django.core.exceptions import ValidationError

        if not 1 <= self.rating <= 5:
            raise ValidationError("Rating must be between 1 and 5.")
