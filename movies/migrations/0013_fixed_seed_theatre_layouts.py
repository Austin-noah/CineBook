from django.db import migrations


THEATRE_LAYOUTS = {
    "CineBook Central (DEMO)": "classic",
    "Silver Screen Cinema (DEMO)": "wide",
    "StarView Cinemas (DEMO)": "stadium",
    "Moonlight Cinemas (DEMO)": "compact",
}


def assign_fixed_seed_theatre_layouts(apps, schema_editor):
    Theatre = apps.get_model("movies", "Theatre")
    theatres = Theatre.objects.using(schema_editor.connection.alias)
    for name, layout in THEATRE_LAYOUTS.items():
        theatres.filter(name=name).update(seat_layout_style=layout)


class Migration(migrations.Migration):

    dependencies = [
        ("movies", "0012_default_missing_section_prices"),
    ]

    operations = [
        migrations.RunPython(
            assign_fixed_seed_theatre_layouts,
            migrations.RunPython.noop,
        ),
    ]
