"""Convert shapefile to GeoJSON for use with Streamlit app"""
import os
import sys

try:
    import geopandas as gpd
except ImportError:
    print("Installing geopandas...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "geopandas"])
    import geopandas as gpd

shapefile_path = "d:/gee/menofia_3km/menofiariverselection_fiaalBuf_Intersect_ExportFeatures.shp"
output_path = "d:/gee/menofia_3km.geojson"

print(f"Reading shapefile: {shapefile_path}")
gdf = gpd.read_file(shapefile_path)

print(f"Shapefile info:")
print(f"  - Features: {len(gdf)}")
print(f"  - CRS: {gdf.crs}")
print(f"  - Bounds: {gdf.total_bounds}")

print(f"\nConverting to GeoJSON: {output_path}")
gdf.to_file(output_path, driver='GeoJSON')

print(f"SUCCESS: GeoJSON created at {output_path}")
print(f"You can now upload this file in the Streamlit app!")
