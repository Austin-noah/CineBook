from datetime import date, time
from decimal import Decimal
import json
from io import StringIO
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.finders import find
from django.core import mail
from django.core.management.base import CommandError
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .management.commands.seed_movies import (
    REMOVED_MOVIE_TITLES,
    SAMPLE_MOVIES,
)
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


class MoviePageTests(TestCase):
    def setUp(self):
        self.theatre = Theatre.objects.create(
            name="Test Theatre",
            city="Hyderabad",
            address="Verified test address",
        )
        self.screen = Screen.objects.create(
            theatre=self.theatre,
            name="Screen 1",
        )
        self.movie = Movie.objects.create(
            title="Test Movie",
            genre="Drama",
            duration=120,
            release_date=date(2025, 1, 1),
            description="A movie used to test the movie pages.",
        )

    def test_movie_list_page_renders(self):
        for number in range(4):
            Movie.objects.create(
                title=f"Top Five Film {number}",
                genre="Drama",
                duration=100,
                release_date=date(2025, 1, 1),
                description="A movie for the Top 5 carousel test.",
            )
        response = self.client.get(reverse("movie_list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "movies/movie_list.html")
        self.assertContains(response, "/static/movies/css/style.css")
        self.assertEqual(len(response.context["top_movies"]), 5)

    def test_selected_city_persists_across_movie_pages(self):
        self.client.get(reverse("movie_list"), {"city": "Vijayawada"})

        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertEqual(response.context["selected_city"], "Vijayawada")
        self.assertContains(response, 'value="Vijayawada"')

    def test_movie_detail_page_renders(self):
        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "movies/movie_detail.html")
        self.assertContains(response, "/static/movies/css/style.css")
        self.assertContains(response, "Cast details not available yet.")

    def test_missing_poster_uses_the_branded_fallback(self):
        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertContains(response, "poster-placeholder")
        self.assertNotContains(response, 'src=""')

    def test_movie_stylesheet_is_discoverable(self):
        self.assertIsNotNone(find("movies/css/style.css"))
        self.assertIsNotNone(find("movies/js/main.js"))
        self.assertIsNotNone(find("movies/js/booking.js"))

    def test_movie_title_search_filters_results(self):
        Movie.objects.create(
            title="Other Film",
            genre="Comedy",
            duration=95,
            release_date=date(2024, 1, 1),
            language="Hindi",
            description="Another test title.",
        )

        response = self.client.get(reverse("movie_list"), {"q": "Test"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [movie.title for movie in response.context["movies"]],
            ["Test Movie"],
        )

    def test_genre_and_language_filters_work(self):
        Movie.objects.create(
            title="Hindi Comedy",
            genre="Comedy",
            duration=95,
            release_date=date(2024, 1, 1),
            language="Hindi",
            description="A test comedy.",
        )
        Movie.objects.create(
            title="Telugu Drama",
            genre="Drama",
            duration=110,
            release_date=date(2024, 1, 1),
            language="Telugu",
            description="A test drama.",
        )

        response = self.client.get(
            reverse("movie_list"),
            {"genre": "Comedy", "language": "Hindi"},
        )

        self.assertEqual(
            [movie.title for movie in response.context["movies"]],
            ["Hindi Comedy"],
        )

    def test_catalogue_rating_filter_excludes_unrated_titles(self):
        self.movie.catalogue_rating = Decimal("8.2")
        self.movie.save(update_fields=["catalogue_rating"])
        Movie.objects.create(
            title="Unrated Film",
            genre="Drama",
            duration=100,
            release_date=date(2024, 1, 1),
            description="No external rating.",
        )

        response = self.client.get(
            reverse("movie_list"),
            {"min_rating": "8"},
        )

        self.assertEqual(
            [movie.title for movie in response.context["movies"]],
            ["Test Movie"],
        )

    def test_homepage_shows_average_rating_and_review_count(self):
        MovieReview.objects.create(
            movie=self.movie,
            reviewer_name="One",
            rating=4,
            comment="Good.",
        )
        MovieReview.objects.create(
            movie=self.movie,
            reviewer_name="Two",
            rating=5,
            comment="Great.",
        )

        response = self.client.get(reverse("movie_list"))

        self.assertContains(response, "4.5")
        self.assertContains(response, "(2)")

    def test_upcoming_movies_and_featured_movie_are_selected(self):
        self.movie.status = Movie.Status.UPCOMING
        self.movie.is_featured = True
        self.movie.save(update_fields=["status", "is_featured"])

        response = self.client.get(reverse("movie_list"))

        self.assertEqual(response.context["featured_movie"].pk, self.movie.pk)
        self.assertEqual(
            [movie.pk for movie in response.context["upcoming_movies"]],
            [self.movie.pk],
        )

    def test_homepage_is_compact_and_top_five_remains_scrollable(self):
        response = self.client.get(reverse("movie_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "carousel-controls")
        self.assertNotContains(response, "featured-hero")
        self.assertContains(response, 'class="top-movies-carousel"')
        self.assertContains(response, 'id="catalogue"')

    def test_theme_switcher_is_shared_by_movie_pages(self):
        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertContains(response, "data-theme-toggle")
        self.assertContains(response, "cinebook-theme")
        self.assertContains(response, "prefers-color-scheme")

    def test_cast_crew_and_configured_showtime_languages_render(self):
        MoviePerson.objects.create(
            movie=self.movie,
            name="Fictional Test Performer",
            role=MoviePerson.Role.MAIN_CAST,
            character_name="Test Character",
        )
        showtime = Showtime.objects.create(
            movie=self.movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(20, 0),
            ticket_price=Decimal("100.00"),
            language="Telugu",
            format="2D",
            subtitle_languages="English",
        )

        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertContains(response, "Cast &amp; Crew")
        self.assertContains(response, "Fictional Test Performer")
        self.assertContains(response, "Test Character")
        self.assertContains(response, "Telugu")
        self.assertContains(response, "English")
        self.assertContains(response, f"language=Telugu")
        self.assertEqual(showtime.subtitle_languages, "English")

    def test_homepage_features_a_movie_with_an_upcoming_showtime(self):
        self.movie.status = Movie.Status.NOW_SHOWING
        self.movie.save(update_fields=["status"])
        Showtime.objects.create(
            movie=self.movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(20, 0),
            ticket_price=Decimal("100.00"),
        )

        response = self.client.get(reverse("movie_list"))

        self.assertEqual(response.context["featured_movie"].pk, self.movie.pk)

    def test_movie_detail_filters_showtimes_by_selected_city(self):
        self.movie.language = "Telugu"
        self.movie.catalogue_rating = Decimal("8.5")
        self.movie.save(update_fields=["language", "catalogue_rating"])
        vijayawada_theatre = Theatre.objects.create(
            name="Vijayawada Theatre",
            city="Vijayawada",
            address="Test address",
        )
        vijayawada_screen = Screen.objects.create(
            theatre=vijayawada_theatre,
            name="Screen 2",
        )
        Showtime.objects.create(
            movie=self.movie,
            screen=vijayawada_screen,
            show_date=date(2027, 1, 2),
            show_time=time(20, 0),
            ticket_price=Decimal("100.00"),
            language="Telugu",
            format="2D",
        )

        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk]),
            {"city": "Vijayawada"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Telugu")
        self.assertContains(response, "8.5/10")
        self.assertEqual(response.context["selected_city"], "Vijayawada")
        self.assertContains(
            response,
            reverse("movie_showtimes", args=[self.movie.pk]),
        )

    def test_showtime_page_filters_by_city_date_language_and_format(self):
        self.movie.language = "Telugu"
        self.movie.save(update_fields=["language"])
        show_date = date(2027, 1, 2)
        self.showtime = Showtime.objects.create(
            movie=self.movie,
            screen=self.screen,
            show_date=show_date,
            show_time=time(20, 0),
            ticket_price=Decimal("100.00"),
            language="Telugu",
            format="2D",
        )

        response = self.client.get(
            reverse("movie_showtimes", args=[self.movie.pk]),
            {
                "city": "Hyderabad",
                "date": show_date.isoformat(),
                "language": "Telugu",
                "format": "2D",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Theatre")
        self.assertContains(response, "Select seats")
        self.assertContains(response, "100 seats available")
        self.assertEqual(len(response.context["showtime_groups"]), 1)

    def test_showtime_price_filter_uses_lowest_section_price(self):
        Showtime.objects.create(
            movie=self.movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(20, 0),
            ticket_price=Decimal("150.00"),
            ground_ticket_price=Decimal("100.00"),
            middle_ticket_price=Decimal("150.00"),
            upper_ticket_price=Decimal("250.00"),
        )

        response = self.client.get(
            reverse("movie_showtimes", args=[self.movie.pk]),
            {"city": "Hyderabad", "price": "under-150"},
        )

        matching_showtimes = [
            showtime
            for _, items in response.context["showtime_groups"]
            for showtime in items
        ]
        self.assertEqual(len(matching_showtimes), 1)
        self.assertEqual(
            matching_showtimes[0].lowest_ticket_price,
            Decimal("100.00"),
        )
        self.assertContains(response, "From ₹")

    def test_theatre_city_selection_filters_grouped_future_showtimes(self):
        another_movie = Movie.objects.create(
            title="Another Test Movie",
            genre="Drama",
            duration=100,
            release_date=date(2025, 2, 1),
            description="Another movie.",
        )
        vijayawada = Theatre.objects.create(
            name="Vijayawada Demo",
            city="Vijayawada",
        )
        vijayawada_screen = Screen.objects.create(
            theatre=vijayawada,
            name="Screen A",
        )
        Showtime.objects.create(
            movie=self.movie,
            screen=vijayawada_screen,
            show_date=date(2027, 2, 1),
            show_time=time(18, 0),
            ticket_price=Decimal("120.00"),
            format="IMAX",
        )
        hyderabad_screen = self.screen
        Showtime.objects.create(
            movie=another_movie,
            screen=hyderabad_screen,
            show_date=date(2027, 2, 1),
            show_time=time(18, 0),
            ticket_price=Decimal("120.00"),
        )

        response = self.client.get(
            reverse("movie_showtimes", args=[self.movie.pk]),
            {"city": "Vijayawada"},
        )

        self.assertEqual(len(response.context["showtime_groups"]), 1)
        self.assertEqual(
            response.context["showtime_groups"][0][0].name,
            "Vijayawada Demo",
        )
        self.assertContains(response, "IMAX")
        self.assertNotContains(response, "Test Theatre")

    def test_showtime_rejects_nonpositive_price_and_screen_overlap(self):
        with self.assertRaises(ValidationError):
            Showtime.objects.create(
                movie=self.movie,
                screen=self.screen,
                show_date=date(2027, 1, 2),
                show_time=time(20, 0),
                ticket_price=Decimal("0.00"),
            )

        Showtime.objects.create(
            movie=self.movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(18, 0),
            ticket_price=Decimal("100.00"),
        )
        other_movie = Movie.objects.create(
            title="Overlap Movie",
            genre="Drama",
            duration=90,
            release_date=date(2025, 3, 1),
            description="Another test movie.",
        )
        with self.assertRaises(ValidationError):
            Showtime.objects.create(
                movie=other_movie,
                screen=self.screen,
                show_date=date(2027, 1, 2),
                show_time=time(19, 30),
                ticket_price=Decimal("100.00"),
            )

    def test_invalid_filter_values_do_not_crash(self):
        response = self.client.get(
            reverse("movie_list"),
            {"genre": "not-a-genre"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["filter_form"].is_valid())

    def test_seed_command_is_repeatable_and_preserves_existing_movie(self):
        movie = Movie.objects.create(
            title="Interstellar",
            genre="Custom genre",
            duration=169,
            release_date=date(2014, 11, 7),
            description="Keep this user-edited description.",
        )
        removed_movie = Movie.objects.create(
            title="Jawan",
            genre="Action",
            duration=169,
            release_date=date(2023, 9, 7),
            description="Movie scheduled for removal.",
        )
        original_showtime = Showtime.objects.create(
            movie=movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(10, 0),
            ticket_price=Decimal("100.00"),
        )
        original_booking = SeatBooking.objects.create(
            showtime=original_showtime,
            customer_name="Existing Viewer",
            customer_email="viewer@example.com",
            selected_seats=["G01"],
            total_paid=Decimal("100.00"),
        )
        removed_showtime = Showtime.objects.create(
            movie=removed_movie,
            screen=self.screen,
            show_date=date(2027, 1, 2),
            show_time=time(14, 0),
            ticket_price=Decimal("100.00"),
        )
        SeatBooking.objects.create(
            showtime=removed_showtime,
            customer_name="Removed Movie Viewer",
            customer_email="removed@example.com",
            selected_seats=["G02"],
            total_paid=Decimal("100.00"),
        )
        MovieReview.objects.create(
            movie=removed_movie,
            reviewer_name="Removed Movie Reviewer",
            rating=3,
            comment="Review for a removed movie.",
        )
        original_reservation = SeatReservation.objects.create(
            booking=original_booking,
            showtime=original_showtime,
            seat_number="G01",
        )
        original_review = MovieReview.objects.create(
            movie=movie,
            reviewer_name="Existing Reviewer",
            rating=5,
            comment="Preserve this review.",
        )
        User = get_user_model()
        original_user = User.objects.create_user(
            username="existing_admin",
            email="admin@example.com",
            password="securepassword123",
        )
        output = StringIO()

        call_command("seed_movies", stdout=output)
        first_count = Movie.objects.count()
        original_theatres = list(
            Theatre.objects.filter(is_demo=True)
            .order_by("city", "name")
            .values_list(
                "name",
                "city",
                "address",
                "seat_layout_style",
            )
        )
        second_output = StringIO()
        call_command("seed_movies", stdout=second_output)

        movie.refresh_from_db()
        self.assertEqual(Movie.objects.count(), first_count)
        self.assertEqual(
            movie.description,
            "Keep this user-edited description.",
        )
        self.assertFalse(
            Movie.objects.filter(title__in=REMOVED_MOVIE_TITLES).exists()
        )
        self.assertIn(f"{len(SAMPLE_MOVIES) - 1} added", output.getvalue())
        self.assertIn("0 added", second_output.getvalue())
        self.assertEqual(
            list(
                Theatre.objects.filter(is_demo=True)
                .order_by("city", "name")
                .values_list(
                    "name",
                    "city",
                    "address",
                    "seat_layout_style",
                )
            ),
            original_theatres,
        )
        expected_demo_showtimes = Movie.objects.count() * 15 * 4 * 2
        self.assertEqual(
            Showtime.objects.count(),
            expected_demo_showtimes + 1,
        )
        self.assertEqual(Theatre.objects.filter(is_demo=True).count(), 60)
        expected_layouts = {
            "CineBook Central (DEMO)": Theatre.SeatLayout.CLASSIC,
            "Silver Screen Cinema (DEMO)": Theatre.SeatLayout.WIDE,
            "StarView Cinemas (DEMO)": Theatre.SeatLayout.STADIUM,
            "Moonlight Cinemas (DEMO)": Theatre.SeatLayout.COMPACT,
        }
        for theatre_name, layout in expected_layouts.items():
            self.assertSetEqual(
                set(
                    Theatre.objects.filter(name=theatre_name).values_list(
                        "seat_layout_style",
                        flat=True,
                    )
                ),
                {layout},
            )
        for city in (
            "Vijayawada",
            "Visakhapatnam",
            "Guntur",
            "Tirupati",
            "Nellore",
            "Kurnool",
            "Rajahmundry",
            "Kakinada",
            "Hyderabad",
            "Warangal",
            "Karimnagar",
            "Nizamabad",
            "Khammam",
            "Mahbubnagar",
            "Nalgonda",
        ):
            for scheduled_movie in Movie.objects.all():
                showings = Showtime.objects.filter(
                    movie=scheduled_movie,
                    screen__theatre__city=city,
                    demo_seed_key__startswith="cinebook-demo-v2-",
                )
                self.assertEqual(
                    showings.values("screen__theatre_id").distinct().count(),
                    4,
                )
                self.assertEqual(showings.count(), 8)
        self.assertEqual(
            Showtime.objects.filter(
                demo_seed_key__startswith="cinebook-demo-v2-"
            ).count(),
            expected_demo_showtimes,
        )
        self.assertEqual(SeatBooking.objects.get(), original_booking)
        self.assertEqual(SeatReservation.objects.get(), original_reservation)
        self.assertEqual(MovieReview.objects.get(), original_review)
        self.assertEqual(User.objects.get(pk=original_user.pk), original_user)

    def test_theatre_and_screen_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(Theatre))
        self.assertTrue(admin.site.is_registered(Screen))

    def test_admin_registers_all_catalogue_and_booking_models(self):
        self.assertTrue(admin.site.is_registered(Movie))
        self.assertTrue(admin.site.is_registered(MoviePerson))
        self.assertTrue(admin.site.is_registered(Showtime))
        self.assertTrue(admin.site.is_registered(SeatBooking))
        self.assertTrue(admin.site.is_registered(SeatReservation))
        self.assertTrue(admin.site.is_registered(MovieReview))

    def test_about_page_includes_tmdb_attribution(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "CineBook does not call TMDB automatically.",
        )
        self.assertContains(
            response,
            "This product uses the TMDB API but is not endorsed or certified by TMDB.",
        )
        self.assertContains(response, "themoviedb.org/assets")
        self.assertContains(response, "image-text-fallback")

    def test_authenticated_admin_can_open_movie_management(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_superuser(
            username="catalogue-admin",
            email="admin@example.com",
            password="test-password-not-used-outside-tests",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/movies/movie/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select movie to change")

    def test_csrf_protection_is_required_for_review_submission(self):
        client = Client(enforce_csrf_checks=True)
        detail_url = reverse("movie_detail", args=[self.movie.pk])

        response = client.post(
            detail_url,
            {
                "reviewer_name": "Reviewer",
                "rating": "5",
                "comment": "CSRF check.",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(MovieReview.objects.exists())

    def test_invalid_movie_id_uses_not_found_response_in_production(self):
        with override_settings(DEBUG=False):
            response = self.client.get(
                reverse("movie_detail", args=[999999])
            )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "SCENE NOT FOUND", status_code=404)

    def test_valid_review_is_saved_and_average_is_updated(self):
        response = self.client.post(
            reverse("movie_detail", args=[self.movie.pk]),
            {
                "reviewer_name": "Verified Reviewer",
                "rating": "5",
                "comment": "A valid review.",
            },
        )

        self.assertRedirects(
            response,
            reverse("movie_detail", args=[self.movie.pk]),
        )
        self.assertTrue(
            MovieReview.objects.filter(
                movie=self.movie,
                rating=5,
                comment="A valid review.",
            ).exists()
        )
        homepage = self.client.get(reverse("movie_list"))
        self.assertContains(homepage, "5.0")
        detail = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )
        self.assertContains(detail, 'type="radio"')
        self.assertContains(detail, "Viewer rating 5.0 out of 5 stars")
        self.assertNotContains(detail, '<select name="rating"')


class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="cinemafan",
            email="fan@example.com",
            password="correct-horse-battery",
        )

    def test_login_is_available_in_the_collapsible_navigation(self):
        response = self.client.get(reverse("movie_list"))

        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, "Log in")

    def test_user_can_log_in_with_username(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "cinemafan",
                "password": "correct-horse-battery",
            },
        )

        self.assertRedirects(response, reverse("movie_list"))
        self.assertTrue(
            self.client.session.get("_auth_user_id")
        )

    def test_user_can_log_in_with_email(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "FAN@example.com",
                "password": "correct-horse-battery",
            },
        )

        self.assertRedirects(response, reverse("movie_list"))
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.user.pk,
        )

    def test_invalid_password_does_not_authenticate(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "cinemafan",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_authenticated_user_can_log_out(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("movie_list"))
        self.assertNotIn("_auth_user_id", self.client.session)


class SeatBookingTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(
            title="Test Movie",
            genre="Drama",
            duration=120,
            release_date=date(2025, 1, 1),
            description="A movie used to test the booking workflow.",
        )
        self.showtime = Showtime.objects.create(
            movie=self.movie,
            screen=Screen.objects.create(
                theatre=Theatre.objects.create(
                    name="Booking Test Theatre",
                    city="Hyderabad",
                ),
                name="Screen 1",
            ),
            show_date=date(2027, 1, 1),
            show_time=time(18, 30),
            ticket_price=Decimal("150.00"),
            ground_ticket_price=Decimal("100.00"),
            middle_ticket_price=Decimal("150.00"),
            upper_ticket_price=Decimal("250.00"),
            language="Telugu",
            format="2D",
        )
        self.screen = self.showtime.screen
        self.booking_url = reverse(
            "book_seats",
            args=[self.showtime.pk],
        )
        self.booking_data = {
            "customer_name": "Alex Example",
            "customer_email": "alex@example.com",
        }

    def create_booking(self, seats):
        booking = SeatBooking.objects.create(
            showtime=self.showtime,
            customer_name="Existing Customer",
            customer_email="existing@example.com",
            selected_seats=seats,
            total_paid=self.showtime.ticket_price * len(seats),
        )
        SeatReservation.objects.bulk_create(
            [
                SeatReservation(
                    booking=booking,
                    showtime=self.showtime,
                    seat_number=seat,
                )
                for seat in seats
            ]
        )
        return booking

    def test_booking_page_shows_exactly_100_seats_in_three_sections(self):
        response = self.client.get(self.booking_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "movies/book_seats.html")
        self.assertEqual(len(response.context["all_seats"]), 100)
        self.assertEqual(response.context["all_seats"][0], "G01")
        self.assertEqual(response.context["all_seats"][-1], "U20")
        self.assertEqual(
            [section["count"] for section in response.context["seat_sections"]],
            [30, 50, 20],
        )
        self.assertEqual(
            [
                (section["code"], section["price"])
                for section in response.context["seat_sections"]
            ],
            [
                ("G", Decimal("100.00")),
                ("M", Decimal("150.00")),
                ("U", Decimal("250.00")),
            ],
        )
        self.assertEqual(
            [
                section["code"]
                for section in response.context["seat_minimap_sections"]
            ],
            ["G", "M", "U"],
        )
        self.assertContains(response, 'data-price="150.00"')
        self.assertContains(response, 'data-price="100.00"')
        self.assertContains(response, 'data-price="250.00"')
        self.assertContains(response, "closest to screen")
        self.assertContains(response, "Language")
        self.assertContains(response, "Telugu")
        self.assertContains(response, "movies/js/booking.js")

    def test_each_theatre_layout_uses_the_uniform_10_seat_rows(self):
        layout_patterns = set()
        for layout_style in Theatre.SeatLayout.values:
            theatre = Theatre.objects.create(
                name=f"{layout_style} Layout Theatre",
                city="Hyderabad",
                seat_layout_style=layout_style,
            )
            screen = Screen.objects.create(
                theatre=theatre,
                name="Screen 1",
            )
            layout_patterns.add(
                tuple(
                    tuple(len(row) for row in section["rows"])
                    for section in screen.seat_layout
                )
            )
            self.assertEqual(screen.seat_capacity, 100)
            self.assertEqual(len(screen.seat_numbers()), 100)
            self.assertEqual(
                [section["count"] for section in screen.seat_layout],
                [30, 50, 20],
            )
            self.assertEqual(
                tuple(len(row) for row in screen.seat_layout[0]["rows"]),
                (10, 10, 10),
            )
            self.assertEqual(
                tuple(len(row) for row in screen.seat_layout[1]["rows"]),
                (10, 10, 10, 10, 10),
            )
            self.assertEqual(
                tuple(len(row) for row in screen.seat_layout[2]["rows"]),
                (10, 10),
            )
        self.assertEqual(len(layout_patterns), 1)

    def test_seat_grid_has_fixed_sectioned_layout(self):
        response = self.client.get(self.booking_url)

        self.assertEqual(len(response.context["all_seats"]), 100)
        self.assertContains(response, 'value="G30"')
        self.assertContains(response, 'value="M50"')
        self.assertContains(response, 'value="U20"')

        invalid_response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "1",
                "selected_seats": ["Z99"],
            },
        )
        self.assertContains(
            invalid_response,
            "One or more selected seats are invalid.",
        )
        self.assertFalse(SeatBooking.objects.exists())

    def test_quantity_modal_shows_capacity_and_pricing_before_seat_map(self):
        response = self.client.get(self.booking_url)

        self.assertContains(response, "How many seats?")
        self.assertContains(response, 'data-quantity="6"')
        self.assertContains(response, "30 available")
        self.assertContains(response, "50 available")
        self.assertContains(response, "20 available")
        self.assertContains(response, "data-seat-map")

    def test_server_requires_selected_seat_count_to_match_quantity(self):
        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "2",
                "selected_seats": ["G01"],
            },
        )

        self.assertContains(response, "Select exactly 2 seats")
        self.assertFalse(SeatBooking.objects.exists())

    def test_movie_details_link_to_booking_page(self):
        response = self.client.get(
            reverse("movie_detail", args=[self.movie.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse("movie_showtimes", args=[self.movie.pk]),
        )

    def test_successful_booking_uses_server_price_and_confirms(self):
        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "3",
                "selected_seats": ["G01", "M01", "U01"],
                "total_paid": "0.01",
            },
        )

        booking = SeatBooking.objects.get()
        self.assertRedirects(
            response,
            reverse(
                "booking_success",
                args=[booking.confirmation_token],
            ),
        )
        self.assertEqual(booking.selected_seats, ["G01", "M01", "U01"])
        self.assertEqual(booking.total_paid, Decimal("500.00"))
        self.assertSetEqual(
            set(
                booking.reservations.values_list("seat_number", flat=True)
            ),
            {"G01", "M01", "U01"},
        )

        confirmation = self.client.get(response.url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "BOOKING CONFIRMED")
        self.assertContains(confirmation, "Booking reference")
        self.assertContains(confirmation, "payment due at cinema")
        self.assertContains(confirmation, "G01, M01, U01")
        self.assertContains(confirmation, "500.00")
        self.assertContains(confirmation, "G01 ticket")
        self.assertContains(confirmation, "100.00")
        self.assertContains(confirmation, "250.00")
        self.assertContains(confirmation, "Booking Test Theatre")
        self.assertContains(confirmation, "Telugu")
        self.assertContains(confirmation, "2D")
        self.assertContains(confirmation, "Print ticket")
        self.assertContains(confirmation, "data-print-ticket")
        self.assertContains(confirmation, "No online payment was collected.")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="CineBook <tickets@example.com>",
    )
    def test_booking_sends_confirmation_email_and_qr_verifies_without_pii(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.booking_url,
                {
                    **self.booking_data,
                    "ticket_quantity": "2",
                    "customer_phone": "555-0100",
                    "selected_seats": ["G01", "U01"],
                },
            )

        booking = SeatBooking.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(booking.confirmation_email_sent)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        verify_path = reverse(
            "verify_ticket",
            kwargs={"verification_token": booking.verification_token},
        )
        self.assertIn(verify_path, message.body)
        html_body = message.alternatives[0][0]
        self.assertIn("cid:cinebook-ticket-qr", html_body)
        self.assertIn("U01 (₹250.00)", html_body)

        confirmation = self.client.get(response.url)
        self.assertContains(confirmation, "data:image/png;base64,")
        self.assertNotContains(confirmation, "email has not been sent yet")
        self.assertNotContains(confirmation, "Retry confirmation email")
        self.assertNotContains(confirmation, "not a real cinema reservation")
        verified = self.client.get(verify_path)
        self.assertEqual(verified.status_code, 200)
        self.assertContains(verified, "G01, U01")
        self.assertNotContains(verified, "alex@example.com")
        self.assertNotContains(verified, "555-0100")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    def test_console_email_backend_does_not_claim_email_was_delivered(self):
        with (
            self.assertLogs("movies.views", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                self.booking_url,
                {
                    **self.booking_data,
                    "ticket_quantity": "1",
                    "selected_seats": ["G01"],
                },
            )

        booking = SeatBooking.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(booking.confirmation_email_sent)
        confirmation = self.client.get(response.url)
        self.assertNotContains(confirmation, "The email has not been sent yet.")
        self.assertNotContains(confirmation, "You can retry safely.")
        self.assertNotContains(confirmation, "Retry confirmation email")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="CineBook <tickets@example.com>",
    )
    def test_email_failure_keeps_booking_and_retry_does_not_duplicate_it(self):
        with (
            patch(
                "django.core.mail.message.EmailMultiAlternatives.send",
                side_effect=OSError("SMTP unavailable"),
            ),
            self.assertLogs("movies.views", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                self.booking_url,
                {
                    **self.booking_data,
                    "ticket_quantity": "1",
                    "selected_seats": ["G01"],
                },
            )

        booking = SeatBooking.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(booking.confirmation_email_sent)
        self.assertEqual(SeatReservation.objects.count(), 1)

        retry = self.client.post(
            reverse(
                "retry_booking_email",
                args=[booking.confirmation_token],
            )
        )

        booking.refresh_from_db()
        self.assertRedirects(
            retry,
            reverse(
                "booking_success",
                args=[booking.confirmation_token],
            ),
        )
        self.assertTrue(booking.confirmation_email_sent)
        self.assertEqual(SeatBooking.objects.count(), 1)
        self.assertEqual(SeatReservation.objects.count(), 1)

    def test_refresh_availability_disables_newly_booked_seats(self):
        self.create_booking(["G01"])

        response = self.client.get(self.booking_url)

        self.assertContains(response, "Refresh availability")
        self.assertIn("G01", response.context["booked_seats"])


    def test_booked_seats_stay_unavailable_after_reopening_booking_page(self):
        self.create_booking(["G01", "U20"])

        response = Client().get(self.booking_url)

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(
            response.context["booked_seats"],
            {"G01", "U20"},
        )
        html = response.content.decode()
        self.assertRegex(
            html,
            r'(?s)id="seat-G01".*?value="G01".*?class="seat-checkbox".*?disabled',
        )
        self.assertRegex(
            html,
            r'(?s)id="seat-U20".*?value="U20".*?class="seat-checkbox".*?disabled',
        )
        self.assertContains(response, 'class="seat booked"')

    def test_existing_legacy_booking_json_blocks_seat(self):
        SeatBooking.objects.create(
            showtime=self.showtime,
            customer_name="Legacy Customer",
            customer_email="legacy@example.com",
            selected_seats=["G01"],
            total_paid=Decimal("150.00"),
        )

        response = self.client.get(self.booking_url)

        self.assertIn("G01", response.context["booked_seats"])

    def test_booking_requires_at_least_one_seat(self):
        response = self.client.post(
            self.booking_url,
            {**self.booking_data, "ticket_quantity": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select 1 seats to continue.")
        self.assertFalse(SeatBooking.objects.exists())

    def test_invalid_seat_is_rejected(self):
        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "1",
                "selected_seats": ["Z9"],
            },
        )

        self.assertContains(response, "One or more selected seats are invalid.")
        self.assertFalse(SeatBooking.objects.exists())

    def test_duplicate_seat_values_are_rejected(self):
        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "2",
                "selected_seats": ["G01", "G01"],
            },
        )

        self.assertContains(
            response,
            "The same seat cannot be selected more than once.",
        )
        self.assertFalse(SeatBooking.objects.exists())

    def test_already_booked_seat_is_rejected(self):
        self.create_booking(["G01"])

        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "1",
                "selected_seats": ["G01"],
            },
        )

        self.assertContains(response, "These seats have just been booked: G01")
        self.assertEqual(SeatBooking.objects.count(), 1)

    def test_a_second_booking_for_different_seats_succeeds(self):
        self.create_booking(["G01"])

        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "1",
                "selected_seats": ["M01"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SeatBooking.objects.count(), 2)
        self.assertTrue(
            SeatReservation.objects.filter(
                showtime=self.showtime,
                seat_number="M01",
            ).exists()
        )

    def test_conflicted_multi_seat_request_creates_no_partial_reservation(self):
        self.create_booking(["M01"])

        response = self.client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "2",
                "selected_seats": ["G01", "M01"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SeatBooking.objects.count(), 1)
        self.assertFalse(
            SeatReservation.objects.filter(
                showtime=self.showtime,
                seat_number="G01",
            ).exists()
        )

    def test_booking_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            self.booking_url,
            {
                **self.booking_data,
                "ticket_quantity": "1",
                "selected_seats": ["G01"],
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(SeatBooking.objects.exists())

    def test_database_prevents_duplicate_seat_reservations(self):
        booking = self.create_booking(["G01"])
        second_booking = SeatBooking.objects.create(
            showtime=self.showtime,
            customer_name="Another Customer",
            customer_email="another@example.com",
            selected_seats=["G01"],
            total_paid=Decimal("150.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SeatReservation.objects.create(
                    booking=second_booking,
                    showtime=self.showtime,
                    seat_number="G01",
                )

        self.assertEqual(booking.reservations.count(), 1)

    def test_booking_requires_valid_customer_fields(self):
        response = self.client.post(
            self.booking_url,
            {
                "customer_name": "",
                "customer_email": "not-an-email",
                "ticket_quantity": "1",
                "selected_seats": ["G01"],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SeatBooking.objects.exists())

    def test_review_rating_above_five_is_rejected(self):
        response = self.client.post(
            reverse("movie_detail", args=[self.movie.pk]),
            {
                "reviewer_name": "Reviewer",
                "rating": "6",
                "comment": "Invalid rating",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(MovieReview.objects.exists())
        self.assertTrue(response.context["form"].errors["rating"])
        self.assertContains(response, 'data-star-rating="true"')


class TMDBArtworkImportTests(TestCase):
    def setUp(self):
        self.movie = Movie.objects.create(
            title="Verified Test Film",
            genre="Drama",
            duration=110,
            release_date=date(2020, 4, 3),
            description="A test movie for the TMDB importer.",
        )

    @staticmethod
    def response(data):
        from io import BytesIO

        return BytesIO(json.dumps(data).encode("utf-8"))

    def configuration(self):
        return {
            "images": {
                "secure_base_url": "https://image.tmdb.org/t/p/",
                "poster_sizes": ["w342", "w500", "original"],
                "backdrop_sizes": ["w780", "w1280", "original"],
            }
        }

    def test_import_uses_exact_title_year_and_documented_https_urls(self):
        results = {
            "results": [
                {
                    "id": 123,
                    "title": "Verified Test Film",
                    "original_title": "Verified Test Film",
                    "release_date": "2020-04-03",
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "vote_average": 7.3,
                    "vote_count": 51,
                }
            ]
        }
        with (
            patch.dict("os.environ", {"TMDB_API_KEY": "test-key"}, clear=True),
            patch(
                "movies.management.commands.import_movie_artwork.urlopen",
                side_effect=[
                    self.response(self.configuration()),
                    self.response(results),
                ],
            ) as mocked_urlopen,
        ):
            call_command("import_movie_artwork")

        self.movie.refresh_from_db()
        self.assertEqual(
            self.movie.poster_url,
            "https://image.tmdb.org/t/p/w500/poster.jpg",
        )
        self.assertEqual(
            self.movie.backdrop_url,
            "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
        )
        self.assertEqual(self.movie.catalogue_rating, Decimal("7.3"))
        self.assertEqual(self.movie.catalogue_rating_source, "TMDB")
        search_request = mocked_urlopen.call_args_list[1].args[0]
        self.assertIsInstance(search_request, Request)
        query = parse_qs(urlparse(search_request.full_url).query)
        self.assertEqual(query["primary_release_year"], ["2020"])
        self.assertEqual(query["region"], ["IN"])

    def test_import_preserves_existing_artwork_and_rating_by_default(self):
        self.movie.poster_url = "https://example.com/custom-poster.jpg"
        self.movie.catalogue_rating = Decimal("8.0")
        self.movie.catalogue_rating_source = "Verified source"
        self.movie.save(
            update_fields=[
                "poster_url",
                "catalogue_rating",
                "catalogue_rating_source",
            ]
        )
        results = {
            "results": [
                {
                    "id": 123,
                    "title": "Verified Test Film",
                    "original_title": "Verified Test Film",
                    "release_date": "2020-04-03",
                    "poster_path": "/replacement.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "vote_average": 7.3,
                    "vote_count": 51,
                }
            ]
        }
        with (
            patch.dict("os.environ", {"TMDB_API_KEY": "test-key"}, clear=True),
            patch(
                "movies.management.commands.import_movie_artwork.urlopen",
                side_effect=[
                    self.response(self.configuration()),
                    self.response(results),
                ],
            ),
        ):
            call_command("import_movie_artwork")

        self.movie.refresh_from_db()
        self.assertEqual(
            self.movie.poster_url,
            "https://example.com/custom-poster.jpg",
        )
        self.assertEqual(
            self.movie.backdrop_url,
            "https://image.tmdb.org/t/p/w1280/backdrop.jpg",
        )
        self.assertEqual(self.movie.catalogue_rating, Decimal("8.0"))
        self.assertEqual(self.movie.catalogue_rating_source, "Verified source")

    def test_import_requires_credentials_without_affecting_website(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesMessage(CommandError, "Set TMDB_API_KEY"):
                call_command("import_movie_artwork")

        response = self.client.get(reverse("movie_detail", args=[self.movie.pk]))
        self.assertEqual(response.status_code, 200)

    def test_import_reports_tmdb_rate_limit(self):
        rate_limit = HTTPError(
            "https://api.themoviedb.org/3/configuration",
            429,
            "Rate limited",
            {"Retry-After": "5"},
            None,
        )
        with (
            patch.dict("os.environ", {"TMDB_API_KEY": "test-key"}, clear=True),
            patch(
                "movies.management.commands.import_movie_artwork.urlopen",
                side_effect=rate_limit,
            ),
        ):
            with self.assertRaisesMessage(CommandError, "rate limit reached"):
                call_command("import_movie_artwork")

    def test_import_rejects_different_movie_or_release_year(self):
        results = {
            "results": [
                {
                    "id": 456,
                    "title": "Verified Test Film",
                    "original_title": "Verified Test Film",
                    "release_date": "1990-01-01",
                    "poster_path": "/wrong-year.jpg",
                    "backdrop_path": "/wrong-year-backdrop.jpg",
                }
            ]
        }
        output = StringIO()
        with (
            patch.dict("os.environ", {"TMDB_API_KEY": "test-key"}, clear=True),
            patch(
                "movies.management.commands.import_movie_artwork.urlopen",
                side_effect=[
                    self.response(self.configuration()),
                    self.response(results),
                ],
            ),
        ):
            call_command("import_movie_artwork", stdout=output)

        self.movie.refresh_from_db()
        self.assertIn("Unmatched or ambiguous", output.getvalue())
        self.assertEqual(self.movie.poster_url, "")
        self.assertEqual(self.movie.backdrop_url, "")


class EnhancedFeatureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user1 = User.objects.create_user(
            username="viewer1",
            email="viewer1@example.com",
            password="SecurePassword123!",
            first_name="Jane",
            last_name="Doe",
        )
        self.user2 = User.objects.create_user(
            username="viewer2",
            email="viewer2@example.com",
            password="SecurePassword456!",
            first_name="John",
            last_name="Smith",
        )
        self.theatre = Theatre.objects.create(
            name="CineBook Grand",
            city="Hyderabad",
            address="Test Avenue, Hyderabad",
        )
        self.screen = Screen.objects.create(
            theatre=self.theatre,
            name="Screen 1",
        )
        self.salaar = Movie.objects.create(
            title="Salaar: Part 1 – Ceasefire",
            genre="Action / Thriller",
            duration=175,
            release_date=date(2023, 12, 22),
            language="Telugu",
            description="A violent battle for Khansaar throne.",
            is_featured=True,
            is_recommended=True,
            ranking=1,
            status=Movie.Status.NOW_SHOWING,
        )
        MoviePerson.objects.create(
            movie=self.salaar,
            name="Prashanth Neel",
            role=MoviePerson.Role.DIRECTOR,
            display_order=1,
        )
        MoviePerson.objects.create(
            movie=self.salaar,
            name="Prabhas",
            role=MoviePerson.Role.MAIN_CAST,
            character_name="Deva / Salaar",
            display_order=2,
        )
        self.showtime = Showtime.objects.create(
            movie=self.salaar,
            screen=self.screen,
            show_date=date(2027, 2, 1),
            show_time=time(19, 0),
            ticket_price=Decimal("150.00"),
            language="Telugu",
            format="2D",
        )

    def test_user_registration_creates_account_and_hashes_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newcinephile",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPass!99",
                "password2": "StrongPass!99",
            },
        )
        self.assertRedirects(response, reverse("movie_list"))
        User = get_user_model()
        new_user = User.objects.get(username="newcinephile")
        self.assertEqual(new_user.email, "new@example.com")
        self.assertTrue(new_user.check_password("StrongPass!99"))
        self.assertNotEqual(new_user.password, "StrongPass!99")
        # Session confirms user is logged in
        self.assertEqual(int(self.client.session["_auth_user_id"]), new_user.pk)

    def test_user_registration_duplicate_email_rejected(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "anotheruser",
                "email": "viewer1@example.com",
                "password1": "StrongPass!99",
                "password2": "StrongPass!99",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "email",
            "An account with this email address already exists. Please log in.",
        )

    def test_user_registration_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "mismatchuser",
                "email": "mismatch@example.com",
                "password1": "PasswordOne1!",
                "password2": "PasswordTwo2!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

    def test_my_bookings_requires_login(self):
        response = self.client.get(reverse("user_bookings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_my_bookings_displays_only_authenticated_users_bookings(self):
        # Booking belonging to user1
        booking1 = SeatBooking.objects.create(
            user=self.user1,
            showtime=self.showtime,
            customer_name="Jane Doe",
            customer_email="viewer1@example.com",
            selected_seats=["G01", "G02"],
            total_paid=Decimal("300.00"),
        )
        # Booking belonging to user2
        booking2 = SeatBooking.objects.create(
            user=self.user2,
            showtime=self.showtime,
            customer_name="John Smith",
            customer_email="viewer2@example.com",
            selected_seats=["G03"],
            total_paid=Decimal("150.00"),
        )

        self.client.force_login(self.user1)
        response = self.client.get(reverse("user_bookings"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, booking1.booking_reference)
        self.assertNotContains(response, booking2.booking_reference)
        self.assertEqual(list(response.context["bookings"]), [booking1])

    def test_authenticated_booking_saves_user_foreign_key(self):
        self.client.force_login(self.user1)
        response = self.client.post(
            reverse("book_seats", args=[self.showtime.pk]),
            {
                "customer_name": "Jane Doe",
                "customer_email": "viewer1@example.com",
                "ticket_quantity": "2",
                "selected_seats": ["G05", "G06"],
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = SeatBooking.objects.get(selected_seats=["G05", "G06"])
        self.assertEqual(booking.user, self.user1)
        self.assertTrue(booking.booking_reference.startswith("CB-"))

    def test_guest_booking_without_user_continues_to_work(self):
        response = self.client.post(
            reverse("book_seats", args=[self.showtime.pk]),
            {
                "customer_name": "Guest Customer",
                "customer_email": "guest@example.com",
                "ticket_quantity": "1",
                "selected_seats": ["G07"],
            },
        )
        self.assertEqual(response.status_code, 302)
        booking = SeatBooking.objects.get(selected_seats=["G07"])
        self.assertIsNone(booking.user)

    def test_salaar_featured_in_recommended_section_and_hero(self):
        response = self.client.get(reverse("movie_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Salaar: Part 1 – Ceasefire")
        self.assertContains(response, "Top Recommended Movies")
        self.assertContains(response, "Prashanth Neel")
        self.assertContains(response, "Prabhas")
        self.assertEqual(response.context["featured_movie"], self.salaar)
        self.assertIn(self.salaar, response.context["top_movies"])

    def test_search_by_actor_and_title(self):
        response_title = self.client.get(reverse("movie_list"), {"q": "Salaar"})
        self.assertIn(self.salaar, response_title.context["movies"])

        response_actor = self.client.get(reverse("movie_list"), {"q": "Prabhas"})
        self.assertIn(self.salaar, response_actor.context["movies"])

    def test_search_suggestions_endpoint(self):
        response = self.client.get(reverse("search_suggestions"), {"q": "Salaar"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(any(item["title"] == "Salaar: Part 1 – Ceasefire" for item in data["results"]))

    def test_adjacent_seat_selection_algorithm(self):
        from movies.adjacent_seats import select_adjacent_seats, STANDARD_ROWS

        row_b = STANDARD_ROWS["B"]  # B1 to B8
        row_c = STANDARD_ROWS["C"]  # C1 to C8

        # 3 tickets, choose B3 -> B3, B4, B5
        self.assertEqual(
            select_adjacent_seats(row_b, "B3", 3),
            ["B3", "B4", "B5"],
        )

        # 2 tickets, choose C6 -> C6, C7
        self.assertEqual(
            select_adjacent_seats(row_c, "C6", 2),
            ["C6", "C7"],
        )

        # 3 tickets at boundary: select B7 in 8-seat row -> shift left to B6, B7, B8
        self.assertEqual(
            select_adjacent_seats(row_b, "B7", 3),
            ["B6", "B7", "B8"],
        )

        # B4 is booked: selecting B3 with 3 tickets falls back to available block [B1, B2, B3]
        self.assertEqual(
            select_adjacent_seats(row_b, "B3", 3, booked_seats=["B4"]),
            ["B1", "B2", "B3"],
        )

        # No contiguous block of 3 exists when alternating seats booked -> returns None
        self.assertIsNone(
            select_adjacent_seats(row_b, "B3", 3, booked_seats=["B2", "B4", "B6"])
        )

    def test_admin_seatbooking_configuration(self):
        from movies.admin import SeatBookingAdmin
        booking_admin = SeatBookingAdmin(SeatBooking, admin.site)
        self.assertIn("booking_reference", booking_admin.list_display)
        self.assertIn("user_account", booking_admin.list_display)
        self.assertIn("movie_title", booking_admin.list_display)
        self.assertEqual(booking_admin.date_hierarchy, "booked_at")
        self.assertIn("user", booking_admin.readonly_fields)
        self.assertIn("booking_reference", booking_admin.readonly_fields)

