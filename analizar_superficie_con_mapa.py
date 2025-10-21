#!/usr/bin/env python3
"""
analizar_superficie_con_mapa.py
Lee un GPX, clasifica segmentos como asfalto/offroad, calcula % por distancia
y genera un mapa HTML con la ruta coloreada.

Uso:
    python analizar_superficie_con_mapa.py ruta.gpx
"""

import sys
import os
import math
import tempfile
from pathlib import Path

import gpxpy
import osmnx as ox
import geopandas as gpd
from shapely.geometry import Point, LineString
from geopy.distance import geodesic
import folium

# --- CONFIGURACIÓN ---
ASFALTO = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "residential", "living_street", "service", "unclassified"
}

PAVED_SURFACES = {
    "asphalt", "paved", "concrete", "concrete:lanes", "sett",
    "paving_stones", "cement", "concrete:plates", "metal", "wood"
}
UNPAVED_SURFACES = {
    "unpaved", "gravel", "fine_gravel", "ground", "dirt", "earth",
    "compacted", "sand", "grass", "mud", "pebblestone"
}

# colores para el mapa
COLOR_ASFALTO = "black"
COLOR_OFFROAD = "green"
COLOR_DESCONOCIDO = "orange"

# --- UTILIDADES ---
def midpoint(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)

def safe_highway_value(val):
    """
    OSM puede devolver highway como string, lista o None.
    Queremos devolver una string representativa o None.
    """
    if val is None:
        return None
    if isinstance(val, list):
        return val[0] if val else None
    return val

def distancia_metros(p1, p2):
    # geodesic requiere (lat, lon)
    return geodesic((p1[0], p1[1]), (p2[0], p2[1])).meters


def safe_tag_value(val):
    if val is None:
        return None
    if isinstance(val, list):
        return val[0] if val else None
    return str(val)


# --- MAIN ---
def main(gpx_path: str):
    gpx_path = Path(gpx_path)
    if not gpx_path.exists():
        print(f"ERROR: no existe {gpx_path}")
        return


    # 1) Leer GPX y extraer puntos (lat, lon)
    with gpx_path.open("r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    puntos = []
    for track in gpx.tracks:
        for segment in track.segments:
            for p in segment.points:
                puntos.append((p.latitude, p.longitude))

    if len(puntos) < 2:
        print("El GPX no tiene suficientes puntos.")
        return

    print(f"Puntos cargados: {len(puntos)}")

    # 2) Construir lista de segmentos y midpoint por segmento
    segmentos = []
    midpoints = []
    for i in range(len(puntos) - 1):
        p1 = puntos[i]
        p2 = puntos[i + 1]
        segmentos.append((p1, p2))
        midpoints.append(midpoint(p1, p2))

    # 3) Descargar red de OSM alrededor de la ruta usando bounding box
    print("Descargando datos de OpenStreetMap (esto puede tardar unos segundos)...")

    # 3) Descargar red de OSM solo en un buffer alrededor de la ruta

    import geopandas as gpd
    from shapely.geometry import LineString

    # 3.1) Crear la geometría de la ruta (LineString) en WGS84
    linea = LineString([(lon, lat) for lat, lon in puntos])  # ojo: (x=lon, y=lat)
    gdf_linea = gpd.GeoDataFrame(geometry=[linea], crs="EPSG:4326")

    # 3.2) Proyectar a UTM zona 30N (Andalucía occidental ~ Marbella/Ojén)
    # Si quisieras hacerlo genérico, se puede calcular la zona UTM en base a la longitud.
    gdf_linea_utm = gdf_linea.to_crs("EPSG:32630")

    # 3.3) Buffer en metros alrededor de la ruta
    buffer_m = 150  # ajusta si quieres más/menos ancho de búsqueda
    gdf_buffer_utm = gdf_linea_utm.buffer(buffer_m)

    # 3.4) Volver a lat/lon para pasarlo a OSMnx
    gdf_buffer = gpd.GeoSeries(gdf_buffer_utm, crs="EPSG:32630").to_crs("EPSG:4326")
    poly_buffer = gdf_buffer.unary_union  # un único polígono

    # 3.5) Descargar la red solo dentro del polígono
    G = ox.graph_from_polygon(
        poly_buffer,
        network_type="all",   # "walk", "bike", "drive" si quieres filtrar
        simplify=True
    )



    # calcular bounding box de todos los puntos
    """ lats = [p[0] for p in puntos]
    lons = [p[1] for p in puntos]

    north, south = max(lats), min(lats)
    east, west = max(lons), min(lons)

    # añadimos un margen de 0.005° (~500 m aprox)
    G = ox.graph_from_bbox(
        bbox=(north + 0.005, south - 0.005, east + 0.005, west - 0.005),
        network_type="all"
    ) """






    edges_gdf = ox.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)

    edges_gdf = ox.graph_to_gdfs(G, nodes=False, fill_edge_geometry=True)
    # edges_gdf tiene columnas como 'highway', 'length', 'geometry', etc.

    # 4) Crear GeoDataFrame de midpoints y hacer sjoin_nearest con edges
    gdf_mid = gpd.GeoDataFrame(
        geometry=[Point(lon, lat) for lat, lon in midpoints], crs="EPSG:4326"
    )

    # Asegurarnos de tener CRS consistente y luego ejecutar sjoin_nearest
    edges_gdf = edges_gdf.reset_index(drop=True)
    # edges ya en EPSG:4326 por defecto en osmnx; si no, reprojectar sería necesario.
    joined = gpd.sjoin_nearest(gdf_mid, edges_gdf, how="left",max_distance=50, distance_col="dist_to_edge")

    # 5) Clasificar segmentos por la propiedad 'highway' de la arista más cercana
    resultados = []  # lista de dicts por segmento
    total_asfalto = total_offroad = total_desconocido = 0.0

    for i, seg in enumerate(segmentos):
        p1, p2 = seg
        d = distancia_metros(p1, p2)

        try:
            row = joined.iloc[i]
        except Exception:
            row = {}

        highway_val = safe_tag_value(row.get("highway", None))
        surface_val = safe_tag_value(row.get("surface", None))
        tracktype_val = safe_tag_value(row.get("tracktype", None))
        dist_edge = row.get("dist_to_edge", None)

        # Por defecto
        tipo = "desconocido"

        # 1) Si estamos demasiado lejos de cualquier vía -> desconocido
        if dist_edge is not None and dist_edge > 50:  # metros
            total_desconocido += d

        # 2) Clasificación por surface si está definido
        elif surface_val in PAVED_SURFACES:
            tipo = "asfalto"
            total_asfalto += d
        elif surface_val in UNPAVED_SURFACES:
            tipo = "offroad"
            total_offroad += d

        # 3) Sin surface -> inferimos por highway / tracktype
        elif highway_val in ASFALTO:
            tipo = "asfalto"
            total_asfalto += d
        elif highway_val in {"track", "path", "bridleway"}:
            if tracktype_val == "grade1":
                tipo = "asfalto"
                total_asfalto += d
            else:
                tipo = "offroad"
                total_offroad += d
        elif highway_val in {"footway", "cycleway"}:
            if surface_val in PAVED_SURFACES:
                tipo = "asfalto"
                total_asfalto += d
            else:
                total_desconocido += d
        else:
            total_desconocido += d

        resultados.append({
            "idx": i,
            "p1": p1,
            "p2": p2,
            "dist_m": d,
            "highway": highway_val,
            "surface": surface_val,
            "tracktype": tracktype_val,
            "tipo": tipo
        })


    """ for i, seg in enumerate(segmentos):
        p1, p2 = seg
        d = distancia_metros(p1, p2)

        # joined puede contener 'highway' (string o list) en la columna joined['highway']
        highway_val = None
        try:
            highway_val = joined.iloc[i].get("highway", None)
        except Exception:
            highway_val = None

        highway_val = safe_highway_value(highway_val)

        if highway_val is None:
            tipo = "desconocido"
            total_desconocido += d
        else:
            # Algunas aristas tienen 'highway' == 'track' o 'path' etc.
            if highway_val in ASFALTO:
                tipo = "asfalto"
                total_asfalto += d
            else:
                tipo = "offroad"
                total_offroad += d

        resultados.append({
            "idx": i,
            "p1": p1,
            "p2": p2,
            "dist_m": d,
            "highway": highway_val,
            "tipo": tipo
        }) """

    # 6) Resumen porcentual
    total = total_asfalto + total_offroad + total_desconocido
    if total == 0:
        print("No se pudo calcular distancias (total 0).")
        return

    pct_asfalto = total_asfalto / total * 100
    pct_offroad = total_offroad / total * 100
    pct_desconocido = total_desconocido / total * 100

    print(f"Distancia total: {total:.1f} m")
    print(f"Asfalto: {total_asfalto:.1f} m ({pct_asfalto:.2f}%)")
    print(f"Offroad: {total_offroad:.1f} m ({pct_offroad:.2f}%)")
    print(f"Desconocido: {total_desconocido:.1f} m ({pct_desconocido:.2f}%)")

    # 7) Generar mapa interactivo con folium
    center_lat = sum(p[0] for p in puntos) / len(puntos)
    center_lon = sum(p[1] for p in puntos) / len(puntos)
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=14)

    # Dibujar cada segmento con color según tipo
    for r in resultados:
        line = [(r["p1"][0], r["p1"][1]), (r["p2"][0], r["p2"][1])]
        color = COLOR_DESCONOCIDO
        if r["tipo"] == "asfalto":
            color = COLOR_ASFALTO
        elif r["tipo"] == "offroad":
            color = COLOR_OFFROAD

        folium.PolyLine(
            locations=line,
            color=color,
            weight=4,
            opacity=0.9
        ).add_to(fmap)

    # Añadir una leyenda simple (usando marcador HTML)
    legend_html = f"""
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 160px; 
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; padding:8px;">
        <b>Leyenda</b><br>
        <i style="background: black; width: 12px; height: 6px; display:inline-block;"></i>&nbsp;Asfalto<br>
        &nbsp;&nbsp;{total_asfalto/1000:.2f} km ({pct_asfalto:.1f}%)<br>
        <i style="background: green; width: 12px; height: 6px; display:inline-block;"></i>&nbsp;Offroad<br>
        &nbsp;&nbsp;{total_offroad/1000:.2f} km ({pct_offroad:.1f}%)<br>
        <i style="background: orange; width: 12px; height: 6px; display:inline-block;"></i>&nbsp;Desconocido<br>
        &nbsp;&nbsp;{total_desconocido/1000:.2f} km ({pct_desconocido:.1f}%)<br>
        <hr>
        <b>Total: {total/1000:.2f} km</b>
        </div>
    """

    fmap.get_root().html.add_child(folium.Element(legend_html))

    # Guardar mapa
    """ out_html = Path.cwd() / f"mapa_ruta_{gpx_path.stem}.html"
    fmap.save(str(out_html))
    print(f"Mapa guardado en: {out_html}") """
        # 10) Generar el mapa HTML en memoria (sin guardar en disco)
    from io import BytesIO

    html_buffer = BytesIO()
    fmap.save(html_buffer, close_file=False)
    html_content = html_buffer.getvalue().decode("utf-8")

    print("Mapa generado correctamente (en memoria).")
    return html_content


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python analizar_superficie_con_mapa.py ruta.gpx")
    else:
        main(sys.argv[1])
