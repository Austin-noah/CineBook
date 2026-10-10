
from django.contrib import admin

from .models import (
    Movie,
    MoviePerson,
    MovieReview,
    Screen,
    SeatBooking,
    SeatReservation,
    Showtime,
    Theatre,
)


class MoviePersonInline(admin.TabularInline):
    model = MoviePerson
    extra = 0


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    inlines = (MoviePersonInline,)
    list_display = (
        "title",
        "genre",
        "language",
        "release_date",
        "catalogue_rating",
        "catalogue_rating_source",
        "status",
        "is_featured",
    )
    search_fields = ("title", "genre", "language", "catalogue_rating_source")
    list_filter = ("genre", "language", "status", "is_featured")


@admin.register(MoviePerson)
class MoviePersonAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "character_name", "movie", "display_order")
    list_filter = ("role", "movie__genre")
    search_fields = ("name", "character_name", "movie__title")


@admin.register(Theatre)
class TheatreAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "cinema_type",
        "seat_layout_style",
        "is_active",
        "is_demo",
    )
    search_fields = ("name", "city", "address")
    list_filter = ("city", "cinema_type", "is_active", "is_demo")


@admin.register(Screen)
class ScreenAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "theatre",
        "screen_type",
        "seat_capacity",
        "is_active",
    )
    search_fields = ("name", "theatre__name", "theatre__city")
    list_filter = ("screen_type", "is_active", "theatre__city", "theatre")
    readonly_fields = ("seat_capacity",)


@admin.register(Showtime)
class ShowtimeAdmin(admin.ModelAdmin):
    list_display = (
        "movie",
        "screen",
        "city",
        "show_date",
        "show_time",
        "ticket_price",
        "ground_ticket_price",
        "middle_ticket_price",
        "upper_ticket_price",
        "format",
        "language",
        "subtitle_languages",
        "booking_open",
        "is_active",
    )
    list_filter = (
        "show_date",
        "screen__theatre__city",
        "format",
        "booking_open",
        "is_active",
    )
    search_fields = ("movie__title", "screen__name", "screen__theatre__name")


@admin.register(SeatBooking)
class SeatBookingAdmin(admin.ModelAdmin):
    list_display = (
        "customer_name",
        "customer_email",
        "customer_phone",
        "showtime",
        "total_paid",
        "confirmation_email_sent",
        "booked_at",
    )
    search_fields = ("customer_name", "customer_email")
    list_filter = ("booked_at",)
    readonly_fields = (
        "showtime",
        "customer_name",
        "customer_email",
        "customer_phone",
        "selected_seats",
        "total_paid",
        "confirmation_token",
        "verification_token",
        "confirmation_email_sent",
        "booked_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = ("seat_number", "showtime", "booking")
    list_filter = (
        "showtime__show_date",
        "showtime__screen__theatre__city",
        "showtime__screen",
    )
    search_fields = ("seat_number", "booking__customer_name", "showtime__movie__title")
    readonly_fields = ("booking", "showtime", "seat_number")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovieReview)
class MovieReviewAdmin(admin.ModelAdmin):
    list_display = ("movie", "reviewer_name", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("movie__title", "reviewer_name")
