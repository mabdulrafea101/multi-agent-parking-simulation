"""
Penang parking simulation configuration.
"""

city_name = "penang"
display_name = "Penang"

bounds = {
    "lat_min": 5.410,
    "lat_max": 5.450,
    "lon_min": 100.320,
    "lon_max": 100.370,
}

center = {
    "lat": 5.430,
    "lon": 100.345,
}

parking_zones = [
    {
        "name": "George Town",
        "lat": 5.4141,
        "lon": 100.3288,
        "capacity": 95,
        "price_per_hour": 3.50,
    },
    {
        "name": "Komtar",
        "lat": 5.4146,
        "lon": 100.3296,
        "capacity": 125,
        "price_per_hour": 4.00,
    },
    {
        "name": "Batu Ferringhi",
        "lat": 5.4492,
        "lon": 100.3223,
        "capacity": 70,
        "price_per_hour": 3.00,
    },
]

description = (
    "Penang simulation area covering George Town commercial activity, Komtar, "
    "and Batu Ferringhi visitor parking."
)
