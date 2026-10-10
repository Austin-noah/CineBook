
from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import UsernameOrEmailAuthenticationForm
from . import views

urlpatterns = [
    path("", views.movie_list, name="movie_list"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="movies/login.html",
            authentication_form=UsernameOrEmailAuthenticationForm,
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="movie_list"),
        name="logout",
    ),
    path("about/", views.about, name="about"),
    path("movie/<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path(
        "movie/<int:movie_id>/shows/",
        views.movie_showtimes,
        name="movie_showtimes",
    ),
    path("book/<int:showtime_id>/", views.book_seats, name="book_seats"),
    path(
        "booking/<uuid:confirmation_token>/",
        views.booking_success,
        name="booking_success",
    ),
    path(
        "booking/<uuid:confirmation_token>/email/",
        views.retry_booking_email,
        name="retry_booking_email",
    ),
    path(
        "verify/<uuid:verification_token>/",
        views.verify_ticket,
        name="verify_ticket",
    ),
]
