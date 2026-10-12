
import logging
import smtplib
import socket
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import (
    Avg,
    Case,
    Count,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Least
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .cities import SUPPORTED_CITIES, select_city
from .forms import (
    AdminLoginForm,
    MovieFilterForm,
    MovieReviewForm,
    SeatBookingForm,
    UserRegistrationForm,
)
from .models import (
    Movie,
    MovieReview,
    Showtime,
    SeatBooking,
    SeatReservation,
)
from .tickets import qr_data_uri, send_booking_confirmation


logger = logging.getLogger(__name__)


def get_seat_numbers(showtime):
    return showtime.screen.seat_numbers()


def get_booked_seats(showtime):
    reserved = set(
        SeatReservation.objects.filter(showtime=showtime).values_list(
            "seat_number",
            flat=True,
        )
    )

    # Include bookings created before individual seat reservations existed.
    for booking in SeatBooking.objects.filter(showtime=showtime).only(
        "selected_seats"
    ):
        if isinstance(booking.selected_seats, list):
            reserved.update(
                seat
                for seat in booking.selected_seats
                if isinstance(seat, str)
                and seat in get_seat_numbers(showtime)
            )

    return reserved


def movie_list(request):
    select_city(request)
    movie_query = Movie.objects.annotate(
        average_rating=Avg("reviews__rating"),
        review_count=Count("reviews", distinct=True),
        booking_count=Count("showtimes__bookings", distinct=True),
        upcoming_showtime_count=Count(
            "showtimes",
            filter=Q(
                showtimes__show_date__gte=timezone.localdate(),
                showtimes__is_active=True,
                showtimes__screen__is_active=True,
                showtimes__screen__theatre__is_active=True,
            ),
            distinct=True,
        ),
    )
    all_movies = movie_query.order_by("title")
    top_movies = list(
        movie_query.order_by(
            Case(
                When(title__icontains="Salaar", then=Value(0)),
                When(is_recommended=True, then=Value(1)),
                When(is_featured=True, then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            "-ranking",
            Case(
                When(poster_url__gt="", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            "-average_rating",
            "-review_count",
            "-catalogue_rating",
            "title",
        )[:5]
    )
    featured_movie = (
        all_movies.filter(title__icontains="Salaar").first()
        or all_movies.filter(is_recommended=True).order_by("-ranking", "title").first()
        or all_movies.filter(is_featured=True).first()
        or all_movies.filter(
            status=Movie.Status.NOW_SHOWING,
            upcoming_showtime_count__gt=0,
        )
        .order_by("-upcoming_showtime_count", "title")
        .first()
        or all_movies.first()
    )
    recommended_movies = list(
        movie_query.filter(
            Q(is_recommended=True) | Q(title__icontains="Salaar")
        ).order_by(
            Case(
                When(title__icontains="Salaar", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            "-ranking",
            "title",
        )[:6]
    )
    if not recommended_movies:
        recommended_movies = top_movies

    genres = Movie.objects.order_by("genre").values_list(
        "genre", flat=True
    ).distinct()
    languages = Movie.objects.order_by("language").values_list(
        "language", flat=True
    ).distinct()
    form = MovieFilterForm(
        request.GET or None,
        genres=genres,
        languages=languages,
    )
    movies = all_movies

    if form.is_valid():
        query = form.cleaned_data["q"]
        genre = form.cleaned_data["genre"]
        language = form.cleaned_data["language"]
        min_rating = form.cleaned_data["min_rating"]
        sort = form.cleaned_data["sort"]

        if query:
            movies = movies.filter(
                Q(title__icontains=query)
                | Q(genre__icontains=query)
                | Q(language__icontains=query)
                | Q(cast_and_crew__name__icontains=query)
                | Q(cast_and_crew__character_name__icontains=query)
            ).distinct()
        if genre:
            movies = movies.filter(genre__icontains=genre)
        if language:
            movies = movies.filter(language=language)
        if min_rating:
            movies = movies.filter(
                catalogue_rating__gte=min_rating,
                catalogue_rating__isnull=False,
            )
        if sort == "rating":
            movies = movies.order_by("-average_rating", "title")
        elif sort == "newest":
            movies = movies.order_by("-created_at", "title")

    movie_list = movies.order_by("title")
    has_filters = any(
        request.GET.get(name)
        for name in ("q", "genre", "language", "min_rating", "sort")
    )
    return render(
        request,
        "movies/movie_list.html",
        {
            "movies": movie_list,
            "filter_form": form,
            "featured_movie": featured_movie,
            "top_movies": top_movies,
            "recommended_movies": recommended_movies,
            "now_showing": movie_list.filter(
                status=Movie.Status.NOW_SHOWING,
                upcoming_showtime_count__gt=0,
            ),
            "upcoming_movies": movie_list.filter(
                status=Movie.Status.UPCOMING
            ),
            "trending_movies": movie_list.filter(
                booking_count__gt=0
            ).order_by("-booking_count", "title")[:8],
            "recent_movies": movie_list.order_by("-created_at")[:8],
            "recent_reviews": MovieReview.objects.select_related("movie")
            .order_by("-created_at")[:6],
            "has_filters": has_filters,
        },
    )


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)

    selected_city = select_city(request)
    reviews = movie.reviews.order_by("-created_at")
    showtime_options = Showtime.objects.filter(
        movie=movie,
        is_active=True,
        booking_open=True,
        show_date__gte=timezone.localdate(),
        screen__is_active=True,
        screen__theatre__is_active=True,
        screen__theatre__city=selected_city,
    ).annotate(
        lowest_ticket_price=Least(
            Coalesce("ground_ticket_price", "ticket_price"),
            Coalesce("middle_ticket_price", "ticket_price"),
            Coalesce("upper_ticket_price", "ticket_price"),
        )
    )
    upcoming_showtimes = list(
        showtime_options.select_related(
            "screen",
            "screen__theatre",
        )
        .order_by("show_date", "show_time", "screen__theatre__name")[:6]
    )
    for showtime in upcoming_showtimes:
        showtime.available_seat_count = (
            showtime.screen.seat_capacity - len(get_booked_seats(showtime))
        )
    movie.average_rating = movie.reviews.aggregate(
        average=Avg("rating")
    )["average"]
    movie.review_count = movie.reviews.count()

    if request.method == "POST":
        form = MovieReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.movie = movie
            review.save()
            messages.success(request, "Your review was submitted.")
            return redirect("movie_detail", movie_id=movie.id)
    else:
        form = MovieReviewForm()

    return render(
        request,
        "movies/movie_detail.html",
        {
            "movie": movie,
            "reviews": reviews,
            "form": form,
            "selected_city": selected_city,
            "cast_and_crew": movie.cast_and_crew.all(),
            "upcoming_showtimes": upcoming_showtimes,
            "available_languages": showtime_options.exclude(language="")
            .order_by("language")
            .values_list("language", flat=True)
            .distinct(),
            "available_formats": showtime_options.exclude(format="")
            .order_by("format")
            .values_list("format", flat=True)
            .distinct(),
            "subtitle_languages": showtime_options.exclude(
                subtitle_languages=""
            )
            .order_by("subtitle_languages")
            .values_list("subtitle_languages", flat=True)
            .distinct(),
        }
    )


def movie_showtimes(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    selected_city = select_city(request)
    today = timezone.localdate()
    showtime_choices = Showtime.objects.filter(
        movie=movie,
        is_active=True,
        booking_open=True,
        show_date__gte=today,
        screen__is_active=True,
        screen__theatre__is_active=True,
        screen__theatre__city=selected_city,
    )
    base_queryset = showtime_choices.annotate(
        lowest_ticket_price=Least(
            Coalesce("ground_ticket_price", "ticket_price"),
            Coalesce("middle_ticket_price", "ticket_price"),
            Coalesce("upper_ticket_price", "ticket_price"),
        )
    ).select_related(
        "screen__theatre", "screen", "movie"
    )

    selected_date = request.GET.get("date", "")
    if selected_date:
        try:
            parsed_date = date.fromisoformat(selected_date)
        except ValueError:
            parsed_date = None
        if parsed_date and parsed_date >= today:
            base_queryset = base_queryset.filter(show_date=parsed_date)
        else:
            selected_date = ""

    language = request.GET.get("language", "").strip()
    if language:
        base_queryset = base_queryset.filter(language__iexact=language)
    format_name = request.GET.get("format", "").strip()
    if format_name:
        base_queryset = base_queryset.filter(format__iexact=format_name)
    preferred_time = request.GET.get("time", "").strip()
    if preferred_time == "morning":
        base_queryset = base_queryset.filter(show_time__lt="12:00")
    elif preferred_time == "afternoon":
        base_queryset = base_queryset.filter(
            show_time__gte="12:00",
            show_time__lt="17:00",
        )
    elif preferred_time == "evening":
        base_queryset = base_queryset.filter(show_time__gte="17:00")

    price_range = request.GET.get("price", "").strip()
    if price_range == "under-150":
        base_queryset = base_queryset.filter(
            lowest_ticket_price__lt=Decimal("150")
        )
    elif price_range == "150-250":
        base_queryset = base_queryset.filter(
            lowest_ticket_price__gte=Decimal("150"),
            lowest_ticket_price__lte=Decimal("250"),
        )
    elif price_range == "250-plus":
        base_queryset = base_queryset.filter(
            lowest_ticket_price__gt=Decimal("250")
        )

    sort = request.GET.get("sort", "time")
    if sort == "price":
        showtimes = base_queryset.order_by("ticket_price", "show_date", "show_time")
    else:
        sort = "time"
        showtimes = base_queryset.order_by(
            "show_date",
            "show_time",
            "screen__theatre__name",
        )

    grouped_showtimes = {}
    for showtime in showtimes:
        showtime.available_seat_count = (
            showtime.screen.seat_capacity - len(get_booked_seats(showtime))
        )
        grouped_showtimes.setdefault(showtime.screen.theatre, []).append(showtime)

    available_dates = [
        available_date
        for available_date in showtime_choices.order_by("show_date")
        .values_list("show_date", flat=True)
        .distinct()
    ][:15]
    filter_values = {
        "date": selected_date,
        "language": language,
        "format": format_name,
        "price": price_range,
        "time": preferred_time,
        "sort": sort,
    }
    return render(
        request,
        "movies/showtimes.html",
        {
            "movie": movie,
            "selected_city": selected_city,
            "showtime_groups": list(grouped_showtimes.items()),
            "available_dates": available_dates,
            "selected_language": language,
            "filter_values": filter_values,
            "languages": showtime_choices
            .exclude(language="")
            .order_by("language")
            .values_list("language", flat=True)
            .distinct(),
            "formats": showtime_choices
            .exclude(format="")
            .order_by("format")
            .values_list("format", flat=True)
            .distinct(),
        },
    )


def book_seats(request, showtime_id):
    showtime = get_object_or_404(
        Showtime.objects.select_related(
            "movie",
            "screen__theatre",
        ),
        id=showtime_id,
        is_active=True,
        booking_open=True,
        screen__is_active=True,
        screen__theatre__is_active=True,
    )
    select_city(request, showtime.city)

    selected_seats = []
    raw_quantity = request.POST.get("ticket_quantity") if request.method == "POST" else request.GET.get("qty", "")
    try:
        ticket_quantity = int(raw_quantity) if raw_quantity else None
    except ValueError:
        ticket_quantity = None
    if ticket_quantity is not None and ticket_quantity not in range(1, 7):
        ticket_quantity = None
    other_showtimes = (
        Showtime.objects.filter(
            movie=showtime.movie,
            is_active=True,
            booking_open=True,
            show_date__gte=timezone.localdate(),
            screen__is_active=True,
            screen__theatre__is_active=True,
            screen__theatre__city=showtime.city,
        )
        .exclude(pk=showtime.pk)
        .select_related("screen__theatre")
        .order_by("show_date", "show_time")
    )
    all_seats = get_seat_numbers(showtime)
    section_prices = {
        "G": showtime.ground_ticket_price or showtime.ticket_price,
        "M": showtime.middle_ticket_price or showtime.ticket_price,
        "U": showtime.upper_ticket_price or showtime.ticket_price,
    }
    seat_sections = []
    for section in showtime.screen.seat_layout:
        section_price = section_prices[section["code"]]
        seat_sections.append(
            {
                **section,
                "price": section_price,
                "rows": tuple(
                    tuple(
                        {
                            "number": seat,
                            "price": section_price,
                        }
                        for seat in row
                    )
                    for row in section["rows"]
                ),
            }
        )

    def render_booking(form):
        booked_seats = get_booked_seats(showtime)
        for section in seat_sections:
            section["available_count"] = sum(
                seat["number"] not in booked_seats
                for row in section["rows"]
                for seat in row
            )
        return render(
            request,
            "movies/book_seats.html",
            {
                "showtime": showtime,
                "seat_layout_name": (
                    showtime.screen.theatre.get_seat_layout_style_display()
                ),
                "other_showtimes": other_showtimes,
                "form": form,
                "all_seats": all_seats,
                "seat_sections": seat_sections,
                "seat_minimap_sections": tuple(seat_sections),
                "booked_seats": booked_seats,
                "selected_seats": selected_seats,
                "ticket_quantity": ticket_quantity,
                "available_seat_count": len(all_seats) - len(booked_seats),
            },
        )

    if request.method != "POST":
        initial_data = {}
        if request.user.is_authenticated:
            full_name = request.user.get_full_name().strip()
            initial_data["customer_name"] = full_name if full_name else request.user.username
            if request.user.email:
                initial_data["customer_email"] = request.user.email
        return render_booking(SeatBookingForm(initial=initial_data))

    form = SeatBookingForm(request.POST)
    selected_seats = request.POST.getlist("selected_seats")

    if ticket_quantity is None:
        form.add_error(None, "Choose a ticket quantity from 1 to 6.")
        return render_booking(form)
    if not form.is_valid():
        return render_booking(form)
    if not selected_seats:
        form.add_error(None, f"Select {ticket_quantity} seats to continue.")
        return render_booking(form)
    if len(selected_seats) != ticket_quantity:
        form.add_error(
            None,
            f"Select exactly {ticket_quantity} seats for this booking.",
        )
        return render_booking(form)
    if len(selected_seats) != len(set(selected_seats)):
        form.add_error(None, "The same seat cannot be selected more than once.")
        return render_booking(form)
    if not set(selected_seats).issubset(all_seats):
        form.add_error(None, "One or more selected seats are invalid.")
        return render_booking(form)

    try:
        with transaction.atomic():
            current_showtime = Showtime.objects.select_related(
                "movie",
                "screen__theatre",
            ).get(
                pk=showtime.pk,
                is_active=True,
                booking_open=True,
                screen__is_active=True,
                screen__theatre__is_active=True,
            )
            current_seats = set(get_seat_numbers(current_showtime))
            if not set(selected_seats).issubset(current_seats):
                form.add_error(
                    None,
                    "The screen layout changed. Refresh availability and "
                    "choose seats again.",
                )
                return render_booking(form)
            booked_seats = get_booked_seats(current_showtime)
            conflicts = set(selected_seats) & booked_seats

            if conflicts:
                form.add_error(
                    None,
                    "These seats have just been booked: "
                    + ", ".join(sorted(conflicts))
                    + ". Please choose different seats.",
                )
                return render_booking(form)

            booking = form.save(commit=False)
            if request.user.is_authenticated:
                booking.user = request.user
            booking.showtime = current_showtime
            booking.selected_seats = selected_seats
            booking.total_paid = sum(
                (
                    current_showtime.price_for_seat(seat)
                    for seat in selected_seats
                ),
                start=current_showtime.ticket_price * 0,
            )
            booking.save()
            SeatReservation.objects.bulk_create(
                [
                    SeatReservation(
                        booking=booking,
                        showtime=current_showtime,
                        seat_number=seat,
                    )
                    for seat in selected_seats
                ]
            )
            transaction.on_commit(
                lambda: _send_booking_email(request, booking),
                robust=True,
            )
    except IntegrityError:
        conflicts = set(selected_seats) & get_booked_seats(showtime)
        if not conflicts:
            raise
        form.add_error(
            None,
            "These seats have just been booked: "
            + ", ".join(sorted(conflicts))
            + ". Please choose different seats.",
        )
        return render_booking(form)

    return redirect(
        "booking_success",
        confirmation_token=booking.confirmation_token,
    )


def booking_success(request, confirmation_token):
    booking = get_object_or_404(
        SeatBooking.objects.select_related(
            "showtime__movie",
            "showtime__screen__theatre",
        ),
        confirmation_token=confirmation_token,
    )
    ticket_breakdown = [
        {
            "seat": seat,
            "price": booking.showtime.price_for_seat(seat),
        }
        for seat in booking.selected_seats
    ]
    return render(
        request,
        "movies/booking_success.html",
        {
            "booking": booking,
            "ticket_breakdown": ticket_breakdown,
            "ticket_qr_data_uri": qr_data_uri(
                request.build_absolute_uri(
                    reverse(
                        "verify_ticket",
                        kwargs={
                            "verification_token": booking.verification_token,
                        },
                    )
                )
            ),
        },
    )


def _send_booking_email(request, booking):
    try:
        send_booking_confirmation(request, booking)
    except (OSError, TimeoutError, socket.error, smtplib.SMTPException):
        logger.exception(
            "Booking confirmation email failed for booking %s",
            booking.confirmation_token,
        )


def retry_booking_email(request, confirmation_token):
    if request.method != "POST":
        return redirect(
            "booking_success",
            confirmation_token=confirmation_token,
        )
    booking = get_object_or_404(
        SeatBooking.objects.select_related(
            "showtime__movie",
            "showtime__screen__theatre",
        ),
        confirmation_token=confirmation_token,
    )
    if booking.confirmation_email_sent:
        messages.info(request, "The confirmation email was already sent.")
    else:
        try:
            send_booking_confirmation(request, booking)
        except (OSError, TimeoutError, socket.error, smtplib.SMTPException):
            logger.exception(
                "Booking confirmation email retry failed for booking %s",
                booking.confirmation_token,
            )
            messages.error(
                request,
                "The email could not be sent right now. Your reservation is "
                "still confirmed; please try again later.",
            )
        else:
            messages.success(request, "The confirmation email was sent.")
    return redirect(
        "booking_success",
        confirmation_token=booking.confirmation_token,
    )


def verify_ticket(request, verification_token):
    booking = get_object_or_404(
        SeatBooking.objects.select_related(
            "showtime__movie",
            "showtime__screen__theatre",
        ),
        verification_token=verification_token,
    )
    return render(
        request,
        "movies/verify_ticket.html",
        {
            "booking": booking,
            "selected_city": select_city(request),
        },
    )


def about(request):
    selected_city = select_city(request)
    return render(
        request,
        "movies/about.html",
        {"selected_city": selected_city},
    )


def page_not_found(request, exception):
    selected_city = select_city(request)
    return render(
        request,
        "movies/404.html",
        {
            "city_names": SUPPORTED_CITIES,
            "selected_city": selected_city,
        },
        status=404,
    )


def register(request):
    selected_city = select_city(request)
    if request.user.is_authenticated:
        return redirect("movie_list")

    redirect_to = request.POST.get("next") or request.GET.get("next") or ""
    if not redirect_to or not url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_to = reverse("movie_list")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(
                request,
                user,
                backend="movies.authentication.UsernameOrEmailBackend",
            )
            messages.success(
                request,
                f"Welcome to CineBook, {user.first_name or user.username}! Your account has been registered successfully.",
            )
            return redirect(redirect_to)
    else:
        form = UserRegistrationForm()

    return render(
        request,
        "movies/register.html",
        {
            "form": form,
            "selected_city": selected_city,
            "next": redirect_to,
        },
    )


@login_required
def user_bookings(request):
    selected_city = select_city(request)
    bookings = (
        SeatBooking.objects.filter(user=request.user)
        .select_related(
            "showtime__movie",
            "showtime__screen__theatre",
        )
        .order_by("-booked_at")
    )
    return render(
        request,
        "movies/my_bookings.html",
        {
            "bookings": bookings,
            "selected_city": selected_city,
        },
    )


def search_suggestions(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 1:
        return JsonResponse({"results": []})

    matches = (
        Movie.objects.filter(
            Q(title__icontains=q)
            | Q(genre__icontains=q)
            | Q(language__icontains=q)
            | Q(cast_and_crew__name__icontains=q)
        )
        .distinct()
        .order_by(
            Case(
                When(title__istartswith=q, then=Value(0)),
                When(title__icontains=q, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
            "title",
        )[:6]
    )
    results = [
        {
            "id": m.pk,
            "title": m.title,
            "genre": m.genre,
            "language": m.language,
            "duration": m.duration,
            "poster_url": m.poster_url,
            "detail_url": reverse("movie_detail", args=[m.pk]),
            "book_url": reverse("movie_showtimes", args=[m.pk]),
        }
        for m in matches
    ]
    return JsonResponse({"results": results})



# ---------------------------------------------------------------------------
# Admin login / dashboard
# ---------------------------------------------------------------------------

def admin_login(request):
    """Dedicated admin login. Credentials come from settings, not frontend JS."""
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect("admin_dashboard")

    selected_city = select_city(request)
    error = None

    if request.method == "POST":
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None and (user.is_staff or user.is_superuser):
                login(request, user)
                return redirect("admin_dashboard")
            else:
                error = "Access denied. You do not have administrator privileges."
        else:
            error = "Invalid admin credentials. Please try again."
    else:
        form = AdminLoginForm(request)

    return render(
        request,
        "movies/admin_login.html",
        {"form": form, "error": error, "selected_city": selected_city},
    )


def _admin_required(view_fn):
    """Decorator: user must be authenticated AND staff/superuser."""
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(reverse("admin_login") + "?next=" + request.path)
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, "You don't have permission to access the admin area.")
            return redirect("movie_list")
        return view_fn(request, *args, **kwargs)
    wrapped.__name__ = view_fn.__name__
    return wrapped


@_admin_required
def admin_dashboard(request):
    """Admin dashboard with real database records."""
    selected_city = select_city(request)
    User = get_user_model()

    user_search = request.GET.get("user_search", "").strip()
    booking_search = request.GET.get("booking_search", "").strip()

    users_qs = User.objects.order_by("-date_joined")
    if user_search:
        users_qs = users_qs.filter(
            Q(username__icontains=user_search)
            | Q(email__icontains=user_search)
            | Q(first_name__icontains=user_search)
            | Q(last_name__icontains=user_search)
        )

    bookings_qs = (
        SeatBooking.objects
        .select_related("showtime__movie", "showtime__screen__theatre", "user")
        .order_by("-booked_at")
    )
    if booking_search:
        bookings_qs = bookings_qs.filter(
            Q(customer_name__icontains=booking_search)
            | Q(customer_email__icontains=booking_search)
            | Q(showtime__movie__title__icontains=booking_search)
        )

    reservations_qs = (
        SeatReservation.objects
        .select_related("showtime__movie", "showtime__screen__theatre", "booking")
        .order_by("-pk")
    )

    total_users = User.objects.count()
    total_bookings = SeatBooking.objects.count()
    total_reservations = SeatReservation.objects.count()
    total_revenue = SeatBooking.objects.aggregate(total=Sum("total_paid"))["total"] or 0

    return render(
        request,
        "movies/admin_dashboard.html",
        {
            "selected_city": selected_city,
            "users": users_qs[:200],
            "bookings": bookings_qs[:200],
            "reservations": reservations_qs[:200],
            "user_search": user_search,
            "booking_search": booking_search,
            "total_users": total_users,
            "total_bookings": total_bookings,
            "total_reservations": total_reservations,
            "total_revenue": total_revenue,
        },
    )


@_admin_required
def admin_toggle_user(request, user_id):
    """Toggle a user account active/inactive."""
    if request.method != "POST":
        return redirect("admin_dashboard")
    User = get_user_model()
    target = get_object_or_404(User, pk=user_id)
    if target == request.user:
        messages.warning(request, "You cannot deactivate your own account.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        action = "activated" if target.is_active else "deactivated"
        messages.success(request, f"User '{target.username}' has been {action}.")
    return redirect("admin_dashboard")
