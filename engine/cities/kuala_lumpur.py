"""
Kuala Lumpur CBD parking simulation configuration.
"""

city_name = "kuala_lumpur"
display_name = "Kuala Lumpur CBD"

bounds = {
    "lat_min": 3.135,
    "lat_max": 3.170,
    "lon_min": 101.685,
    "lon_max": 101.730,
}

center = {
    "lat": 3.152,
    "lon": 101.710,
}

parking_zones = [
    {
        "name": "Bukit Bintang",
        "lat": 3.1466,
        "lon": 101.7118,
        "capacity": 120,
        "price_per_hour": 6.00,
    },
    {
        "name": "KLCC",
        "lat": 3.1579,
        "lon": 101.7123,
        "capacity": 180,
        "price_per_hour": 7.50,
    },
    {
        "name": "Petronas Towers",
        "lat": 3.1576,
        "lon": 101.7117,
        "capacity": 150,
        "price_per_hour": 8.00,
    },
    {
        "name": "Merdeka",
        "lat": 3.1490,
        "lon": 101.6937,
        "capacity": 90,
        "price_per_hour": 4.50,
    },
    {
        "name": "Chinatown",
        "lat": 3.1424,
        "lon": 101.6977,
        "capacity": 80,
        "price_per_hour": 4.00,
    },
]

description = (
    "Central Kuala Lumpur simulation area covering high-demand CBD, retail, "
    "landmark, and heritage parking zones."
)
