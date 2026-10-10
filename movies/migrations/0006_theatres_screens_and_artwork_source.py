import django.core.validators
import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


def associate_legacy_showtimes(apps, schema_editor):
    Theatre = apps.get_model("movies", "Theatre")
    Screen = apps.get_model("movies", "Screen")
    Showtime = apps.get_model("movies", "Showtime")
    database = schema_editor.connection.alias

    for showtime in Showtime.objects.using(database).order_by("pk"):
        city = showtime.city or "Hyderabad"
        theatre, _ = Theatre.objects.using(database).get_or_create(
            name="DEMO CineBook Theatre",
            city=city,
            defaults={
                "address": "Demonstration location — replace with a verified address.",
                "description": "Legacy showtime migrated as demonstration data.",
                "is_demo": True,
            },
        )
        screen_name = f"Screen {showtime.screen_number}"
        screen, _ = Screen.objects.using(database).get_or_create(
            theatre=theatre,
            name=screen_name,
            defaults={"seat_rows": 5, "seats_per_row": 8},
        )
        if Showtime.objects.using(database).filter(
            screen=screen,
            show_date=showtime.show_date,
            show_time=showtime.show_time,
        ).exists():
            screen, _ = Screen.objects.using(database).get_or_create(
                theatre=theatre,
                name=f"{screen_name} (legacy {showtime.pk})",
                defaults={"seat_rows": 5, "seats_per_row": 8},
            )
        showtime.screen = screen
        showtime.save(using=database, update_fields=["screen"])


def unassociate_legacy_showtimes(apps, schema_editor):
    Showtime = apps.get_model("movies", "Showtime")
    Showtime.objects.using(schema_editor.connection.alias).update(screen=None)


class Migration(migrations.Migration):

    dependencies = [
        ("movies", "0005_alter_seatbooking_total_paid"),
    ]

    operations = [
        migrations.CreateModel(
            name="Theatre",
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
                ("name", models.CharField(max_length=150)),
                ("city", models.CharField(default="Hyderabad", max_length=100)),
                ("address", models.CharField(blank=True, max_length=250)),
                ("description", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_demo", models.BooleanField(default=False)),
            ],
            options={"ordering": ("city", "name")},
        ),
        migrations.CreateModel(
            name="Screen",
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
                ("name", models.CharField(max_length=80)),
                (
                    "seat_rows",
                    models.PositiveSmallIntegerField(
                        default=5,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(26),
                        ],
                    ),
                ),
                (
                    "seats_per_row",
                    models.PositiveSmallIntegerField(
                        default=8,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(99),
                        ],
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "theatre",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="screens",
                        to="movies.theatre",
                    ),
                ),
            ],
            options={"ordering": ("theatre", "name")},
        ),
        migrations.AddField(
            model_name="movie",
            name="catalogue_rating_source",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="showtime",
            name="format",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="showtime",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="showtime",
            name="language",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="showtime",
            name="screen",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="showtimes",
                to="movies.screen",
            ),
        ),
        migrations.RunPython(
            associate_legacy_showtimes,
            unassociate_legacy_showtimes,
        ),
        migrations.RemoveField(
            model_name="showtime",
            name="city",
        ),
        migrations.RemoveField(
            model_name="showtime",
            name="screen_number",
        ),
        migrations.AlterField(
            model_name="showtime",
            name="ticket_price",
            field=models.DecimalField(
                decimal_places=2,
                max_digits=8,
                validators=[django.core.validators.MinValueValidator(0.01)],
            ),
        ),
        migrations.AlterField(
            model_name="showtime",
            name="screen",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="showtimes",
                to="movies.screen",
            ),
        ),
        migrations.AddConstraint(
            model_name="theatre",
            constraint=models.UniqueConstraint(
                fields=("name", "city"),
                name="unique_theatre_name_per_city",
            ),
        ),
        migrations.AddConstraint(
            model_name="screen",
            constraint=models.UniqueConstraint(
                fields=("theatre", "name"),
                name="unique_screen_name_per_theatre",
            ),
        ),
        migrations.AddConstraint(
            model_name="screen",
            constraint=models.CheckConstraint(
                condition=Q(seat_rows__gte=1, seat_rows__lte=26),
                name="screen_rows_between_1_and_26",
            ),
        ),
        migrations.AddConstraint(
            model_name="screen",
            constraint=models.CheckConstraint(
                condition=Q(seats_per_row__gte=1, seats_per_row__lte=99),
                name="screen_columns_between_1_and_99",
            ),
        ),
        migrations.AddConstraint(
            model_name="showtime",
            constraint=models.UniqueConstraint(
                fields=("screen", "show_date", "show_time"),
                name="unique_screen_showtime_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="showtime",
            constraint=models.CheckConstraint(
                condition=Q(ticket_price__gt=0),
                name="showtime_ticket_price_positive",
            ),
        ),
    ]
