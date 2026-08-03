"""
Johor Bahru city center parking simulation configuration.
"""

city_name = "johor_bahru"
display_name = "Johor Bahru City Center"

bounds = {
    "lat_min": 1.450,
    "lat_max": 1.500,
    "lon_min": 103.730,
    "lon_max": 103.790,
}

center = {
    "lat": 1.475,
    "lon": 103.760,
}

parking_zones = [
    {
        "name": "JB Sentral",
        "lat": 1.4625,
        "lon": 103.7649,
        "capacity": 110,
        "price_per_hour": 3.50,
    },
    {
        "name": "City Square",
        "lat": 1.4620,
        "lon": 103.7636,
        "capacity": 130,
        "price_per_hour": 4.00,
    },
    {
        "name": "Komtar JBCC",
        "lat": 1.4612,
        "lon": 103.7630,
        "capacity": 100,
        "price_per_hour": 4.50,
    },
]

description = (
    "Johor Bahru downtown simulation area centered on transit, shopping, "
    "and commercial parking demand."
)
