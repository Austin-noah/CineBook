# CineBook

CineBook is a Django movie catalogue, community review and seat-booking demo.
Public movie, review and booking pages do not require a user account; Django
Admin remains protected by its normal staff login. No online payment is
collected.

## Run locally on Windows

From the folder containing `manage.py`, in PowerShell:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py seed_movies
.\venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`. Create an administrator when needed with
`.\venv\Scripts\python.exe manage.py createsuperuser`, then sign in at
`http://127.0.0.1:8000/admin/`.

The `seed_movies` command is safe to rerun: it adds missing demonstration
titles, four fictional demo venues in each of the 15 supported cities, and
two future showtimes per movie at each venue. Show dates roll forward from the
current date. Each venue name always maps to the same location and seating
layout. It does not overwrite existing movies or delete or modify existing
reviews/bookings. Demo venues and schedules are clearly labelled and are not
real cinema listings.

## Theatres, screens, showtimes and bookings

The migration adds theatres and screens and safely associates legacy
showtimes with a clearly labelled demo theatre/screen. Existing movie,
booking, review and seat-reservation records are preserved.

For the local sample catalogue, venues and demo showtimes, run:

```powershell
.\venv\Scripts\python.exe manage.py seed_movies
```

The command is repeatable. In Django Admin, add a Theatre first, then one or
more Screens, then add each Showtime by selecting its Movie and Screen.
Theatre/demo schedule records are always identified as sample data. Ticket prices must be positive;
the same screen cannot have overlapping showtimes (a 20-minute changeover is
reserved between films). Set theatres, screens and showtimes inactive to hide
them from public booking without deleting booking history.

Movie details show future active showtimes by selected city and group them
under theatre and screen. City selection is searchable and persists in the
session; the default city is Hyderabad. Each theatre has one fixed seating
layout shared by its screens; the four layouts use different row/seat
arrangements while retaining 100 seats across Ground (30), Middle (50), and
Upper (20). Default section prices increase away from the screen: Ground
(₹100), Middle (₹150), and Upper (₹250). Each showtime can set its own section
prices, and the server recalculates booking totals. Booking pages reload current
reservations on every page load. Use **Refresh availability** to fetch the
latest database state. There is no live cross-browser polling. SQLite does not support
row-level `select_for_update()` locks; an atomic booking transaction and the
unique `(showtime, seat_number)` database constraint prevent duplicate seat
reservations, but SQLite can still report a database-lock error during heavy
simultaneous writes. This demo is not designed for high-concurrency ticket
sales.

Local reservations and seat assignments are stored in the project-root
`db.sqlite3` file and remain after closing and reopening the app or browser.
Do not delete the database or run `manage.py flush` if you want to keep them.

The site theme follows the operating-system preference until the visitor
chooses Dark or Light; that choice is saved in the browser. Movie pages show
only languages, formats, and subtitles configured on future showtimes in the
selected city. Cast and crew are editable from a Movie in Admin; the project
does not prefill unverified credits and displays an unavailable message until
credits are entered.

The confirmation URL displays a reserved digital ticket, QR verification code,
and section-aware ticket prices; it can be printed. A confirmation email with
the verification QR is sent using the configured email backend. By default,
local development prints email in the runserver console. An email failure does
not undo a confirmed reservation, and its confirmation page offers a safe
retry. No online payment is collected.

To deliver confirmation emails, copy `.env.example` to `.env` and set the
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, and
`EMAIL_HOST_PASSWORD` values for your SMTP provider. Setting `EMAIL_HOST`
automatically enables SMTP; local development without an SMTP host prints mail
to the runserver console and does not mark it as delivered. Set
`DEFAULT_FROM_EMAIL` to an address accepted by your provider. For Gmail, use an
App Password (not your Google account password). Never commit `.env`; it is
ignored by Git.

## Movie artwork and TMDB

The app runs normally without TMDB credentials. If no artwork is configured,
it displays original CineBook fallback artwork; no TMDB paths or ratings are
invented. Administrators can manually edit poster URL, backdrop URL, catalogue
rating and its source on a Movie in Django Admin.

For optional, non-commercial development/demo imports:

1. Create a TMDB account and request an API key or API Read Access Token under
   [TMDB API settings](https://www.themoviedb.org/settings/api), after reviewing
   [TMDB's API terms](https://www.themoviedb.org/documentation/api/terms-of-use).
2. Set one credential in PowerShell. Do not commit it to source control:

   ```powershell
   # Add this to the ignored .env file:
   TMDB_API_READ_ACCESS_TOKEN=your-api-read-access-token
   ```

   TMDB is not required to run any page or local feature. Optional
   `TMDB_LANGUAGE` (default `en-US`) and `TMDB_REGION` (default `IN`)
   environment variables select search preferences.
3. Run the importer from the project folder:

   ```powershell
   .\venv\Scripts\python.exe manage.py import_movie_artwork
   ```

   It matches exact normalized titles and release years, reports ambiguous or
   missing matches, uses TMDB's configuration endpoint and secure image base
   URL/supported sizes, and records the source as TMDB when importing a
   catalogue rating. Existing artwork and catalogue ratings are kept unless
   explicitly allowed; `--overwrite` replaces existing poster/backdrop URLs.
   Set a narrower preference for a one-off run with
   `--language en-US --region IN`.

The [About & Credits](/about/) page explains that TMDB is not called
automatically and presents the required non-endorsement notice for use if
TMDB data is imported. Review TMDB terms and branding guidance before using
TMDB data or artwork, especially outside a non-commercial demonstration.
References: [Getting started](https://developer.themoviedb.org/docs/getting-started),
[authentication](https://developer.themoviedb.org/docs/authentication-application),
[image URL basics](https://developer.themoviedb.org/docs/image-basics), and
[movie image API](https://developer.themoviedb.org/reference/movie-images).

## Checks and tests

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test
```

Tests use Django's isolated test database; they do not reset the local
`db.sqlite3`. The project includes mocked TMDB importer tests and does not
make external API calls during the test suite.

## Local pages to verify

- Catalogue and demo sample data: `http://127.0.0.1:8000/`
- Django Admin: `http://127.0.0.1:8000/admin/`
- About, artwork credits and TMDB notice: `http://127.0.0.1:8000/about/`
- Movie detail and its city selector: `http://127.0.0.1:8000/movie/<movie-id>/`
- Seat selection: follow **Book tickets** from an active future showtime.
- Printable ticket: complete a demo reservation and use **Print ticket**.

## Render preparation

The included `render.yaml` installs requirements, collects static assets,
applies migrations, and starts `config.wsgi:application` with Gunicorn. Set
`DJANGO_DEBUG=False`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and
`DJANGO_CSRF_TRUSTED_ORIGINS` in the Render environment. The manifest creates a
secret and supplies the expected CineBook hostname; update the hostname values
if the Render service is renamed or a custom domain is used.
The app sends booking confirmation emails. Configure `EMAIL_HOST`,
`EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, and
`DEFAULT_FROM_EMAIL` in the deployment environment for an SMTP service. The
console backend is for local development only.

WhiteNoise serves collected static assets. Do not commit `.env`, the virtual
environment, collected assets, or `db.sqlite3`. Django migrations must be
committed. Create the production administrator with `createsuperuser` in a
one-off shell after deployment.
The Django deployment check may still warn that HSTS preload is disabled.
It is intentionally not enabled because adding preload without controlling
and verifying the production domain's policy is unsafe.

This project intentionally keeps SQLite to meet the assignment requirements.
Render's free web-service filesystem is ephemeral: SQLite changes (movies,
reviews, reservations, admin data) can be lost when the service is replaced or
restarted. This deployment configuration is suitable for a demonstration,
not durable production bookings. Do not accept real payments or rely on this
SQLite instance for business-critical data.
