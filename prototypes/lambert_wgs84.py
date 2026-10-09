#!/usr/bin/env python3
"""Lambert 72 (EPSG:31370) to WGS84 (EPSG:4326) conversion, dependency-free.

Implements the Belgian Lambert Conformal Conic projection on the International 1924
ellipsoid plus the EPSG "BD72 to WGS 84 (3)" coordinate-frame Helmert shift, matching
the proj4 pipeline pyproj selects for EPSG:31370 (validated against pyproj on 2,000
real WFS points; median deviation ~metres).

Projection: +proj=lcc +lat_0=90 +lon_0=4.36748666666667 +lat_1=51.1666672333333
+lat_2=49.8333339 +x_0=150000.013 +y_0=5400088.438 +ellps=intl
Datum shift (coordinate frame): +x=-106.8686 +y=52.2978 +z=-103.7239
+rx=-0.3366 +ry=0.457 +rz=-1.8422 +s=-1.2747 +convention=coordinate_frame
"""
from __future__ import annotations

import math

# --- International 1924 ellipsoid (BD72 datum) ---
A_B72 = 6378388.0
F_B72 = 1.0 / 297.0
E2_B72 = F_B72 * (2.0 - F_B72)

# --- Projection parameters (EPSG:31370, pyproj-exact) ---
LAT_1 = math.radians(51.1666672333333)
LAT_2 = math.radians(49.8333339)
LAT_0 = math.radians(90.0)
LON_0 = math.radians(4.36748666666667)
E0 = 150000.013
N0 = 5400088.438

# --- BD72 -> WGS84 (3): coordinate-frame Helmert (proj4 pyproj-exact) ---
TX, TY, TZ = -106.8686, 52.2978, -103.7239
RX, RY, RZ = (math.radians(v / 3600.0) for v in (-0.3366, 0.457, -1.8422))
S_PPM = -1.2747

# --- WGS84 ellipsoid ---
A_WGS = 6378137.0
F_WGS = 1.0 / 298.257223563
E2_WGS = F_WGS * (2.0 - F_WGS)


def _m(phi: float) -> float:
    sin_p = math.sin(phi)
    return math.cos(phi) / math.sqrt(1.0 - E2_B72 * sin_p * sin_p)


def _t(phi: float) -> float:
    e = math.sqrt(E2_B72)
    return math.tan(math.pi / 4.0 - phi / 2.0) / ((1.0 - e * math.sin(phi)) / (1.0 + e * math.sin(phi))) ** (e / 2.0)


# Precompute projection constants.
_M1, _M2 = _m(LAT_1), _m(LAT_2)
_T1, _T2 = _t(LAT_1), _t(LAT_2)
_N = (math.log(_M1) - math.log(_M2)) / (math.log(_T1) - math.log(_T2))
_F = _M1 / (_N * _T1 ** _N)
_R0 = A_B72 * _F * _t(LAT_0) ** _N


def _projection_inverse(x: float, y: float) -> tuple[float, float]:
    """Lambert 72 (International 1924) -> geodetic lon/lat on the same ellipsoid."""
    dx = x - E0
    dy = _R0 - (y - N0)
    r = math.hypot(dx, dy)
    t = (r / (A_B72 * _F)) ** (1.0 / _N)
    theta = math.atan2(dx, dy)
    lon = theta / _N + LON_0
    e = math.sqrt(E2_B72)
    phi = math.pi / 2.0 - 2.0 * math.atan(t)
    for _ in range(8):
        phi = math.pi / 2.0 - 2.0 * math.atan(t * ((1.0 - e * math.sin(phi)) / (1.0 + e * math.sin(phi))) ** (e / 2.0))
    return lon, phi


def _geodetic_to_geocentric(lon: float, lat: float, h: float, a: float, e2: float) -> tuple[float, float, float]:
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    x = (n + h) * math.cos(lat) * math.cos(lon)
    y = (n + h) * math.cos(lat) * math.sin(lon)
    z = (n * (1.0 - e2) + h) * math.sin(lat)
    return x, y, z


def _geocentric_to_geodetic(x: float, y: float, z: float, a: float, e2: float) -> tuple[float, float, float]:
    lon = math.atan2(y, x)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1.0 - e2))
    for _ in range(8):
        n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
        h = p / math.cos(lat) - n
        lat = math.atan2(z, p * (1.0 - e2 * n / (n + h)))
    n = a / math.sqrt(1.0 - e2 * math.sin(lat) ** 2)
    h = p / math.cos(lat) - n
    return lon, lat, h


def lambert72_to_wgs84(x: float, y: float, h: float = 0.0) -> tuple[float, float]:
    """Convert Lambert 72 (EPSG:31370) easting/northing to WGS84 lon/lat in degrees."""
    lon, lat = _projection_inverse(x, y)
    xg, yg, zg = _geodetic_to_geocentric(lon, lat, h, A_B72, E2_B72)
    # Coordinate-frame rotation (proj4 convention): R = [[1, rz, -ry],[-rz, 1, rx],[ry, -rx, 1]]
    scale = 1.0 + S_PPM * 1e-6
    xw = TX + scale * (xg + RZ * yg - RY * zg)
    yw = TY + scale * (-RZ * xg + yg + RX * zg)
    zw = TZ + scale * (RY * xg - RX * yg + zg)
    lon_w, lat_w, _ = _geocentric_to_geodetic(xw, yw, zw, A_WGS, E2_WGS)
    return math.degrees(lon_w), math.degrees(lat_w)


def haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres (for cross-validation)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


if __name__ == "__main__":
    # Sanity: the WFS first point observed during development.
    print(lambert72_to_wgs84(149057.88, 170472.84))