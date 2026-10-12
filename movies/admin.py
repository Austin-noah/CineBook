
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin

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

User = get_user_model()
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class CustomUserAdmin(DefaultUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)


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
        "is_recommended",
        "ranking",
    )
    search_fields = ("title", "genre", "language", "catalogue_rating_source")
    list_filter = ("genre", "language", "status", "is_featured", "is_recommended")


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
        "booking_reference",
        "customer_name",
        "customer_email",
        "user_account",
        "movie_title",
        "showtime_display",
        "screen_number",
        "seats_display",
        "total_paid",
        "booked_at",
    )
    list_filter = (
        "booked_at",
        "showtime__movie",
        "showtime__show_date",
        "showtime__screen__theatre__city",
        "confirmation_email_sent",
    )
    search_fields = (
        "customer_name",
        "customer_email",
        "customer_phone",
        "confirmation_token",
        "user__username",
        "user__email",
        "showtime__movie__title",
        "showtime__screen__theatre__name",
    )
    date_hierarchy = "booked_at"
    ordering = ("-booked_at",)
    readonly_fields = (
        "booking_reference",
        "user",
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

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "user",
                "showtime__movie",
                "showtime__screen__theatre",
            )
        )

    @admin.display(description="User")
    def user_account(self, obj):
        return obj.user.username if obj.user else "Guest"

    @admin.display(description="Movie")
    def movie_title(self, obj):
        return obj.showtime.movie.title

    @admin.display(description="Showtime")
    def showtime_display(self, obj):
        return f"{obj.showtime.show_date} {obj.showtime.show_time:%H:%M}"

    @admin.display(description="Screen")
    def screen_number(self, obj):
        return f"{obj.showtime.screen.name} ({obj.showtime.screen.theatre.name})"

    @admin.display(description="Seats")
    def seats_display(self, obj):
        if isinstance(obj.selected_seats, list):
            return ", ".join(obj.selected_seats)
        return str(obj.selected_seats)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeatReservation)
class SeatReservationAdmin(admin.ModelAdmin):
    list_display = (
        "seat_number",
        "showtime",
        "movie_title",
        "theatre_and_screen",
        "customer_name",
        "booking_ref",
    )
    list_filter = (
        "showtime__show_date",
        "showtime__screen__theatre__city",
        "showtime__screen",
        "showtime__movie",
    )
    search_fields = (
        "seat_number",
        "booking__customer_name",
        "booking__customer_email",
        "showtime__movie__title",
    )
    readonly_fields = ("booking", "showtime", "seat_number")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "booking",
                "showtime__movie",
                "showtime__screen__theatre",
            )
        )

    @admin.display(description="Movie")
    def movie_title(self, obj):
        return obj.showtime.movie.title

    @admin.display(description="Venue & Screen")
    def theatre_and_screen(self, obj):
        return f"{obj.showtime.screen.theatre.name} - {obj.showtime.screen.name}"

    @admin.display(description="Customer")
    def customer_name(self, obj):
        return obj.booking.customer_name

    @admin.display(description="Booking Ref")
    def booking_ref(self, obj):
        return obj.booking.booking_reference

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovieReview)
class MovieReviewAdmin(admin.ModelAdmin):
    list_display = ("movie", "reviewer_name", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("movie__title", "reviewer_name")

