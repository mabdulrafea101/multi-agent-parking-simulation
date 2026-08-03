"""
City configuration loader for parking simulation scenarios.
"""
from importlib import import_module


_CITY_MODULES = {
    "kuala_lumpur": "engine.cities.kuala_lumpur",
    "kl": "engine.cities.kuala_lumpur",
    "johor_bahru": "engine.cities.johor_bahru",
    "jb": "engine.cities.johor_bahru",
    "penang": "engine.cities.penang",
}


def get_city_config(city_name):
    """Return the configuration dictionary for a supported city."""
    normalized_name = city_name.lower().strip().replace(" ", "_")
    module_path = _CITY_MODULES.get(normalized_name)

    if module_path is None:
        supported_cities = sorted(
            name for name in _CITY_MODULES if len(name) > 2 or name == "kl"
        )
        raise ValueError(
            f"Unsupported city '{city_name}'. Supported cities: {', '.join(supported_cities)}"
        )

    module = import_module(module_path)
    return {
        "name": module.city_name,
        "city_name": module.city_name,
        "display_name": module.display_name,
        "bounds": module.bounds,
        "center": module.center,
        "parking_zones": module.parking_zones,
        "description": module.description,
    }


__all__ = ["get_city_config"]
