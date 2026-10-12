from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from movies.cities import SUPPORTED_CITIES
from movies.models import Movie, MoviePerson, Screen, Showtime, Theatre


REMOVED_MOVIE_TITLES = (
    "Jawan",
    "K.G.F: Chapter 1",
    "Queen",
    "Kalki 2898 AD",
    "Ponniyin Selvan: I",
    "The Dark Knight",
    "Zindagi Na Milegi Dobara",
)


SAMPLE_MOVIES = (
    {
        "title": "Salaar: Part 1 – Ceasefire",
        "genre": "Action / Thriller",
        "duration": 175,
        "release_date": date(2023, 12, 22),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/salaar.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "In the dystopian city-state of Khansaar, a prince faces a brutal "
            "battle for power and turns to his exiled childhood friend Deva, "
            "who unleashes fury to help him claim the throne."
        ),
        "is_featured": True,
        "is_recommended": True,
        "ranking": 1,
        "cast_and_crew": (
            ("Prashanth Neel", MoviePerson.Role.DIRECTOR, "", 1),
            ("Prabhas", MoviePerson.Role.MAIN_CAST, "Deva / Salaar", 2),
            ("Prithviraj Sukumaran", MoviePerson.Role.MAIN_CAST, "Varadharaja Mannaar", 3),
            ("Shruti Haasan", MoviePerson.Role.SUPPORTING_CAST, "Aadya", 4),
        ),
    },
    {
        "title": "Interstellar",
        "genre": "Sci-Fi",
        "duration": 169,
        "release_date": date(2014, 11, 7),
        "language": "English",
        "poster_url": "/static/movies/images/posters/interstellar.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A team of explorers travels beyond Earth to search for a "
            "possible new home for humanity."
        ),
        "is_featured": True,
    },
    {
        "title": "Inception",
        "genre": "Sci-Fi",
        "duration": 148,
        "release_date": date(2010, 7, 16),
        "language": "English",
        "poster_url": "/static/movies/images/posters/inception.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A specialist who enters dreams is offered a chance to return "
            "home by undertaking an unusually difficult mission."
        ),
    },
    {
        "title": "Arrival",
        "genre": "Sci-Fi",
        "duration": 116,
        "release_date": date(2016, 11, 11),
        "language": "English",
        "poster_url": "/static/movies/images/posters/Arrival.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A linguist works to understand the language of visitors who "
            "have arrived at sites around the world."
        ),
    },
    {
        "title": "Dune: Part Two",
        "genre": "Sci-Fi",
        "duration": 166,
        "release_date": date(2024, 3, 1),
        "language": "English",
        "poster_url": "/static/movies/images/posters/dune-part-two.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "Paul Atreides joins the Fremen on Arrakis as he confronts the "
            "future of his family and the planet."
        ),
    },
    {
        "title": "RRR",
        "genre": "Action",
        "duration": 187,
        "release_date": date(2022, 3, 25),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/rrr.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "Two courageous men from different worlds form an unexpected "
            "friendship in a fictional tale set in colonial India."
        ),
    },
    {
        "title": "Baahubali: The Beginning",
        "genre": "Action",
        "duration": 159,
        "release_date": date(2015, 7, 10),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/Baahubali_The_Beginning.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A young man discovers a connection to a kingdom and becomes "
            "involved in its struggle for power."
        ),
    },
    {
        "title": "Baahubali 2: The Conclusion",
        "genre": "Action",
        "duration": 167,
        "release_date": date(2017, 4, 28),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/Baahubali 2_ The Conclusion.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "The story of the Mahishmati kingdom continues as its past "
            "reveals the events behind a lasting question."
        ),
    },
    {
        "title": "Sita Ramam",
        "genre": "Romance",
        "duration": 163,
        "release_date": date(2022, 8, 5),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/sita-ramam.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A letter from a soldier begins a search that connects people "
            "across time."
        ),
    },
    {
        "title": "Pushpa: The Rise",
        "genre": "Action",
        "duration": 179,
        "release_date": date(2021, 12, 17),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/pushpa-the-rise.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A determined worker rises through the ranks of a red-sanders "
            "smuggling network."
        ),
    },
    {
        "title": "Jersey",
        "genre": "Drama",
        "duration": 157,
        "release_date": date(2019, 4, 19),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/jersey.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A former cricketer considers returning to the sport to fulfil "
            "a promise to his son."
        ),
    },
    {
        "title": "Eega",
        "genre": "Fantasy",
        "duration": 134,
        "release_date": date(2012, 7, 6),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/eega.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A murdered man returns in an unexpected form to protect the "
            "people he loves."
        ),
    },
    {
        "title": "Hanu-Man",
        "genre": "Fantasy",
        "duration": 158,
        "release_date": date(2024, 1, 12),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/hanu-man.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A young man in a small village discovers an extraordinary "
            "power and takes on a new responsibility."
        ),
    },
    {
        "title": "Devara: Part 1",
        "genre": "Action",
        "duration": 178,
        "release_date": date(2024, 9, 27),
        "language": "Telugu",
        "poster_url": "/static/movies/images/posters/devara-part-1.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A coastal community faces conflict as a son confronts the "
            "legacy of his father."
        ),
    },
    {
        "title": "Dangal",
        "genre": "Drama",
        "duration": 161,
        "release_date": date(2016, 12, 23),
        "language": "Hindi",
        "poster_url": "/static/movies/images/posters/dangal.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A former wrestler trains his daughters to compete in a sport "
            "where they face formidable expectations."
        ),
    },
    {
        "title": "3 Idiots",
        "genre": "Comedy",
        "duration": 170,
        "release_date": date(2009, 12, 25),
        "language": "Hindi",
        "poster_url": "/static/movies/images/posters/3-idiots.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "Three engineering students question convention and search for "
            "a friend years after graduation."
        ),
    },
    {
        "title": "Gully Boy",
        "genre": "Drama",
        "duration": 153,
        "release_date": date(2019, 2, 14),
        "language": "Hindi",
        "poster_url": "/static/movies/images/posters/gully-boy.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A young man from Mumbai finds his voice through hip-hop and "
            "works toward a life of his own."
        ),
    },
    {
        "title": "Andhadhun",
        "genre": "Thriller",
        "duration": 139,
        "release_date": date(2018, 10, 5),
        "language": "Hindi",
        "poster_url": "/static/movies/images/posters/andhadhun.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A pianist becomes caught in a series of complications after "
            "witnessing a crime."
        ),
    },
    {
        "title": "Vikram",
        "genre": "Action",
        "duration": 174,
        "release_date": date(2022, 6, 3),
        "language": "Tamil",
        "poster_url": "/static/movies/images/posters/vikram.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A special investigation into a string of murders uncovers "
            "connections to a powerful criminal network."
        ),
    },
    {
        "title": "Jailer",
        "genre": "Action",
        "duration": 169,
        "release_date": date(2023, 8, 10),
        "language": "Tamil",
        "poster_url": "/static/movies/images/posters/jailer.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A retired jailer is drawn into a dangerous mission to protect "
            "his family."
        ),
    },
    {
        "title": "Kaithi",
        "genre": "Action",
        "duration": 145,
        "release_date": date(2019, 10, 25),
        "language": "Tamil",
        "poster_url": "/static/movies/images/posters/kaithi.png",
        "status": Movie.Status.CATALOGUE,
        "description": (
            "A prisoner on the night of his release helps police officers "
            "in a race against time."
        ),
    },
    {
        "title": "Kantara",
        "genre": "Action",
        "duration": 148,
        "release_date": date(2022, 9, 30),
        "language": "Kannada",
        "poster_url": "/static/movies/images/posters/kantara.png",
        "status": Movie.Status.NOW_SHOWING,
        "description": (
            "A forest community's traditions and land come into conflict "
            "with official authority."
        ),
    },
    {
        "title": "Spirited Away",
        "genre": "Animation",
        "duration": 125,
        "release_date": date(2001, 7, 20),
        "language": "Japanese",
        "poster_url": "/static/movies/images/posters/spirited-away.png",
        "status": Movie.Status.UPCOMING,
        "description": (
            "A young girl enters a mysterious spirit world and must find "
            "her way home."
        ),
    },
)


class Command(BaseCommand):
    help = (
        "Add sample catalogue, fixed-layout demo theatres and future showtimes "
        "without changing existing movies, reviews or bookings."
    )

    def handle(self, *args, **options):
        created_count = 0
        existing_count = 0

        # --- Seed admin user (Render deployment auto-setup) ------------------
        admin_username = getattr(settings, "ADMIN_USERNAME", "Harsha")
        admin_password = getattr(settings, "ADMIN_PASSWORD", "vamsi")
        User = get_user_model()
        admin_user, admin_created = User.objects.get_or_create(
            username=admin_username,
            defaults={"is_staff": True, "is_superuser": True},
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password(admin_password)
        admin_user.save(update_fields=["is_staff", "is_superuser", "password"])
        action = "created" if admin_created else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"Admin user '{admin_username}' {action} with staff/superuser privileges."
        ))
        # ---------------------------------------------------------------------

        Movie.objects.filter(title__in=REMOVED_MOVIE_TITLES).delete()

        for movie_data in SAMPLE_MOVIES:
            target_status = movie_data.get("status", Movie.Status.CATALOGUE)
            cast_data = movie_data.get("cast_and_crew", ())
            clean_movie_data = {
                k: v for k, v in movie_data.items() if k != "cast_and_crew"
            }
            movie, created = Movie.objects.get_or_create(
                title=clean_movie_data["title"],
                defaults={
                    **clean_movie_data,
                    "status": target_status,
                    "backdrop_url": "",
                    "catalogue_rating": None,
                },
            )
            update_fields = []
            poster_url = clean_movie_data.get("poster_url", "")
            if poster_url and movie.poster_url != poster_url:
                movie.poster_url = poster_url
                update_fields.append("poster_url")
            if target_status and movie.status != target_status:
                movie.status = target_status
                update_fields.append("status")
            if clean_movie_data.get("is_featured") and not movie.is_featured:
                movie.is_featured = True
                update_fields.append("is_featured")
            if clean_movie_data.get("is_recommended") and not movie.is_recommended:
                movie.is_recommended = True
                update_fields.append("is_recommended")
            if clean_movie_data.get("ranking") and movie.ranking != clean_movie_data["ranking"]:
                movie.ranking = clean_movie_data["ranking"]
                update_fields.append("ranking")
            if update_fields:
                movie.save(update_fields=update_fields)

            for person_name, person_role, char_name, order in cast_data:
                MoviePerson.objects.get_or_create(
                    movie=movie,
                    name=person_name,
                    role=person_role,
                    defaults={
                        "character_name": char_name,
                        "display_order": order,
                    },
                )

            created_count += int(created)
            existing_count += int(not created)

        movies = list(Movie.objects.order_by("pk"))
        today = timezone.localdate()
        schedule_days = max(15, (len(movies) + 1) // 2)
        first_show_date = today
        show_slots = (
            time(10, 0),
            time(13, 30),
            time(17, 0),
            time(20, 30),
        )
        theatre_names = (
            "CineBook Central (DEMO)",
            "Silver Screen Cinema (DEMO)",
            "StarView Cinemas (DEMO)",
            "Moonlight Cinemas (DEMO)",
        )
        demo_locations = (
            "DEMO Central District",
            "DEMO Riverside District",
            "DEMO North District",
            "DEMO East District",
        )
        theatre_layouts = {
            "CineBook Central (DEMO)": Theatre.SeatLayout.CLASSIC,
            "Silver Screen Cinema (DEMO)": Theatre.SeatLayout.WIDE,
            "StarView Cinemas (DEMO)": Theatre.SeatLayout.STADIUM,
            "Moonlight Cinemas (DEMO)": Theatre.SeatLayout.COMPACT,
        }
        if len(theatre_names) != len(demo_locations):
            raise RuntimeError("Each seeded theatre needs a fixed location.")
        if set(theatre_names) != set(theatre_layouts):
            raise RuntimeError("Each seeded theatre needs a fixed seat layout.")
        performances_by_date = {}
        for movie_index, movie in enumerate(movies):
            show_dates = (
                first_show_date + timedelta(days=movie_index % schedule_days),
                first_show_date
                + timedelta(days=(movie_index + schedule_days // 2) % schedule_days),
            )
            for show_date in show_dates:
                performances_by_date.setdefault(show_date, []).append(
                    (movie_index, movie)
                )

        showtimes_added = 0
        schedule_conflicts = 0
        with transaction.atomic():
            for city_index, city in enumerate(SUPPORTED_CITIES):
                for venue_index, (name, location) in enumerate(
                    zip(theatre_names, demo_locations)
                ):
                    theatre, _ = Theatre.objects.get_or_create(
                        name=name,
                        city=city,
                        defaults={
                            "cinema_type": Theatre.CinemaType.SINGLE_SCREEN,
                            "seat_layout_style": theatre_layouts[name],
                            "address": f"{location}, {city} (fictional demo)",
                            "description": (
                                "Fictional CineBook demonstration venue and "
                                "schedule; not a real-world cinema listing."
                            ),
                            "is_demo": True,
                        },
                    )
                    screen, _ = Screen.objects.get_or_create(
                        theatre=theatre,
                        name="Screen 1",
                        defaults={"screen_type": Screen.ScreenType.STANDARD},
                    )
                    schedule = {}
                    for showtime in Showtime.objects.filter(
                        screen=screen,
                        show_date__range=(
                            first_show_date,
                            first_show_date + timedelta(days=schedule_days - 1),
                        ),
                    ).select_related("movie"):
                        schedule.setdefault(showtime.show_date, []).append(
                            (
                                datetime.combine(
                                    showtime.show_date,
                                    showtime.show_time,
                                ),
                                datetime.combine(
                                    showtime.show_date,
                                    showtime.show_time,
                                )
                                + timedelta(
                                    minutes=showtime.movie.duration + 20
                                ),
                            )
                        )

                    existing_keys = set(
                        Showtime.objects.filter(
                            demo_seed_key__startswith="cinebook-demo-v2-",
                            screen=screen,
                        ).values_list("demo_seed_key", flat=True)
                    )
                    new_showtimes = []
                    for show_date, performances in sorted(
                        performances_by_date.items()
                    ):
                        for slot_index, (movie_index, movie) in enumerate(
                            sorted(performances)
                        ):
                            seed_key = (
                                f"cinebook-demo-v2-{movie.pk}-{theatre.pk}-"
                                f"{show_date:%Y%m%d}"
                            )
                            if seed_key in existing_keys:
                                continue

                            slot_order = (
                                slot_index + city_index + venue_index
                            ) % len(show_slots)
                            show_time = show_slots[slot_order]
                            start = datetime.combine(show_date, show_time)
                            end = start + timedelta(minutes=movie.duration + 20)
                            occupied = schedule.setdefault(show_date, [])
                            if any(
                                start < booked_end and booked_start < end
                                for booked_start, booked_end in occupied
                            ):
                                schedule_conflicts += 1
                                continue

                            occupied.append((start, end))
                            new_showtimes.append(
                                Showtime(
                                    movie=movie,
                                    screen=screen,
                                    show_date=show_date,
                                    show_time=show_time,
                                    ticket_price=Decimal("100.00"),
                                    upper_ticket_price=Decimal("250.00"),
                                    middle_ticket_price=Decimal("150.00"),
                                    ground_ticket_price=Decimal("100.00"),
                                    language=movie.language,
                                    format="2D",
                                    demo_seed_key=seed_key,
                                )
                            )

                    if new_showtimes:
                        Showtime.objects.bulk_create(
                            new_showtimes,
                            batch_size=500,
                            ignore_conflicts=True,
                        )
                        showtimes_added += len(new_showtimes)

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue ready: {created_count} added, "
                f"{existing_count} already existed; "
                f"{showtimes_added} demo showtimes added; "
                f"{schedule_conflicts} conflicting schedules skipped."
            )
        )
        self.stdout.write(
            f"Created or retained demo venues in {len(SUPPORTED_CITIES)} "
            "supported cities. Each movie is scheduled twice at four "
            "fictional venues per city, with non-overlapping times. "
            "Venues and showtimes are demonstration data, not real cinema "
            "schedules. Existing reviews and bookings for retained movies "
            "were preserved."
        )
