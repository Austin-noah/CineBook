from decimal import Decimal

from django.db import migrations


def configure_theatre_layouts_and_fill_missing_prices(apps, schema_editor):
    Theatre = apps.get_model("movies", "Theatre")
    Showtime = apps.get_model("movies", "Showtime")
    database = schema_editor.connection.alias
    theatres = (
        Theatre.objects.using(database)
        .order_by("city", "name", "pk")
    )
    layouts = ("classic", "wide", "stadium", "compact")
    for index, theatre in enumerate(theatres.iterator()):
        Theatre.objects.using(database).filter(pk=theatre.pk).update(
            seat_layout_style=layouts[index % len(layouts)]
        )

    showtimes = Showtime.objects.using(database)
    showtimes.filter(ground_ticket_price__isnull=True).update(
        ground_ticket_price=Decimal("100.00")
    )
    showtimes.filter(middle_ticket_price__isnull=True).update(
        middle_ticket_price=Decimal("150.00")
    )
    showtimes.filter(upper_ticket_price__isnull=True).update(
        upper_ticket_price=Decimal("250.00")
    )


class Migration(migrations.Migration):

    dependencies = [
        ("movies", "0011_theatre_seat_layout_style_and_more"),
    ]

    operations = [
        migrations.RunPython(
            configure_theatre_layouts_and_fill_missing_prices,
            migrations.RunPython.noop,
        ),
    ]
