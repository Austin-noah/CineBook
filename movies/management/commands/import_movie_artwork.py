import json
import os
import re
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError

from movies.models import Movie


API_ROOT = "https://api.themoviedb.org/3"
TIMEOUT_SECONDS = 10


def normalized_title(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def request_json(path, params, api_key, access_token):
    query = dict(params)
    if api_key:
        query["api_key"] = api_key
    request = Request(
        f"{API_ROOT}/{path}?{urlencode(query)}",
        headers={
            "Accept": "application/json",
            "User-Agent": "CineBook development artwork importer",
            **(
                {"Authorization": f"Bearer {access_token}"}
                if access_token
                else {}
            ),
        },
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 429:
            retry_after = error.headers.get("Retry-After", "a short time")
            raise CommandError(
                "TMDB rate limit reached. Wait at least "
                f"{retry_after} seconds before rerunning the import."
            ) from error
        raise CommandError(
            f"TMDB request failed with HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError) as error:
        raise CommandError(
            f"Could not reach TMDB: {error}."
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CommandError("TMDB returned an invalid JSON response.") from error


def choose_exact_match(movie, results):
    expected_title = normalized_title(movie.title)
    expected_year = str(movie.release_date.year)
    exact_title = []
    exact_original_title = []
    for result in results:
        release_date = result.get("release_date", "")
        if not release_date.startswith(expected_year + "-"):
            continue
        if normalized_title(result.get("title", "")) == expected_title:
            exact_title.append(result)
        elif normalized_title(result.get("original_title", "")) == expected_title:
            exact_original_title.append(result)
    candidates = exact_title or exact_original_title
    unique_candidates = {candidate.get("id"): candidate for candidate in candidates}
    if len(unique_candidates) != 1:
        return None
    return next(iter(unique_candidates.values()))


def preferred_size(available_sizes, preferred):
    if preferred in available_sizes:
        return preferred
    numeric_sizes = [
        (int(size[1:]), size)
        for size in available_sizes
        if size.startswith("w") and size[1:].isdigit()
    ]
    if numeric_sizes:
        return max(numeric_sizes)[1]
    if "original" in available_sizes:
        return "original"
    return None


def make_image_url(secure_base_url, size, file_path):
    if not file_path or not file_path.startswith("/") or ".." in file_path:
        return ""
    if not secure_base_url.startswith("https://") or not size:
        return ""
    return f"{secure_base_url.rstrip('/')}/{size}{file_path}"


class Command(BaseCommand):
    help = (
        "Import verified TMDB poster/backdrop paths and optional catalogue "
        "ratings for exact title/year matches."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--language",
            default=os.environ.get("TMDB_LANGUAGE", "en-US"),
            help="TMDB response language (default: TMDB_LANGUAGE or en-US).",
        )
        parser.add_argument(
            "--region",
            default=os.environ.get("TMDB_REGION", "IN"),
            help="TMDB release region (default: TMDB_REGION or IN).",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace existing poster and backdrop URLs explicitly.",
        )

    def handle(self, *args, **options):
        api_key = os.environ.get("TMDB_API_KEY", "").strip()
        access_token = (
            os.environ.get("TMDB_ACCESS_TOKEN", "").strip()
            or os.environ.get("TMDB_API_READ_ACCESS_TOKEN", "").strip()
        )
        if not api_key and not access_token:
            raise CommandError(
                "Set TMDB_API_KEY or TMDB_ACCESS_TOKEN "
                "(TMDB_API_READ_ACCESS_TOKEN is also supported)."
            )

        configuration = request_json(
            "configuration",
            {},
            api_key,
            access_token,
        )
        images = configuration.get("images", {})
        secure_base_url = images.get("secure_base_url", "")
        poster_size = preferred_size(
            images.get("poster_sizes", []),
            "w500",
        )
        backdrop_size = preferred_size(
            images.get("backdrop_sizes", []),
            "w1280",
        )
        if not secure_base_url.startswith("https://"):
            raise CommandError(
                "TMDB configuration did not provide an HTTPS image base URL."
            )

        imported = 0
        unmatched = 0
        unchanged = 0
        for movie in Movie.objects.order_by("title"):
            results = request_json(
                "search/movie",
                {
                    "query": movie.title,
                    "primary_release_year": movie.release_date.year,
                    "language": options["language"],
                    "region": options["region"],
                    "include_adult": "false",
                },
                api_key,
                access_token,
            ).get("results", [])
            match = choose_exact_match(movie, results)
            if match is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"Unmatched or ambiguous: {movie.title} "
                        f"({movie.release_date.year})"
                    )
                )
                unmatched += 1
                continue

            changes = []
            poster_url = make_image_url(
                secure_base_url,
                poster_size,
                match.get("poster_path"),
            )
            backdrop_url = make_image_url(
                secure_base_url,
                backdrop_size,
                match.get("backdrop_path"),
            )
            if poster_url and (options["overwrite"] or not movie.poster_url):
                movie.poster_url = poster_url
                changes.append("poster_url")
            if backdrop_url and (
                options["overwrite"] or not movie.backdrop_url
            ):
                movie.backdrop_url = backdrop_url
                changes.append("backdrop_url")

            if (
                movie.catalogue_rating is None
                and match.get("vote_count", 0) > 0
                and match.get("vote_average") is not None
            ):
                try:
                    rating = Decimal(str(match["vote_average"]))
                except (InvalidOperation, ValueError):
                    rating = None
                if rating is not None and Decimal("0") <= rating <= Decimal("10"):
                    movie.catalogue_rating = rating.quantize(Decimal("0.1"))
                    movie.catalogue_rating_source = "TMDB"
                    changes.extend(
                        ("catalogue_rating", "catalogue_rating_source")
                    )

            if changes:
                movie.save(update_fields=changes)
                imported += 1
                self.stdout.write(f"Imported TMDB artwork/data: {movie.title}")
            else:
                unchanged += 1
                self.stdout.write(
                    f"No new artwork or rating available: {movie.title}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"TMDB import complete: {imported} updated, "
                f"{unchanged} unchanged, {unmatched} unmatched."
            )
        )
