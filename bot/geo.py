from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_METERS = 6_371_000


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia entre dos coordenadas usando la formula de haversine."""
    lat1_r, lon1_r, lat2_r, lon2_r = map(radians, (lat1, lon1, lat2, lon2))
    d_lat = lat2_r - lat1_r
    d_lon = lon2_r - lon1_r
    a = sin(d_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return EARTH_RADIUS_METERS * c
