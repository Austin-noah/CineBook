from .cities import POPULAR_CITIES, SUPPORTED_CITIES, select_city


def cinema_city(request):
    return {
        "city_names": SUPPORTED_CITIES,
        "popular_cities": POPULAR_CITIES,
        "selected_city": select_city(request),
    }
