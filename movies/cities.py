SUPPORTED_CITIES = (
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
)

POPULAR_CITIES = (
    "Hyderabad",
    "Vijayawada",
    "Visakhapatnam",
    "Guntur",
    "Tirupati",
    "Warangal",
    "Nellore",
    "Kurnool",
)


def select_city(request, suggested_city=None):
    requested_city = request.GET.get("city")
    if requested_city in SUPPORTED_CITIES:
        request.session["selected_city"] = requested_city
    elif suggested_city in SUPPORTED_CITIES:
        request.session["selected_city"] = suggested_city

    selected = request.session.get("selected_city", "Hyderabad")
    if selected not in SUPPORTED_CITIES:
        selected = "Hyderabad"
        request.session["selected_city"] = selected
    return selected
