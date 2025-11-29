import streamlit as st
import ee
import geemap.foliumap as geemap
import pandas as pd
import numpy as np
from datetime import datetime, date
import json
from google.oauth2 import service_account

st.set_page_config(
    page_title="Sentinel-1 Flood Mapper",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .main {padding: 0rem 1rem;}
    .stButton>button {width: 100%; background-color: #007bff; color: white; font-weight: bold; padding: 0.5rem; border-radius: 5px;}
    .stat-box {background-color: #f8f9fa; padding: 1rem; border-radius: 5px; border: 1px solid #ddd; margin: 0.5rem 0;}
    .flood-area {font-size: 24px; font-weight: bold; color: #dc3545;}
    .section-header {border-bottom: 2px solid #007bff; padding-bottom: 0.5rem; margin-top: 1.5rem; margin-bottom: 1rem;}
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def initialize_ee(project=None):
    try:
        try:
            if "gcp_service_account" in st.secrets:
                service_account_info = st.secrets["gcp_service_account"]
                
                if isinstance(service_account_info, str):
                    try:
                        service_account_info = json.loads(service_account_info)
                    except json.JSONDecodeError:
                        return False, "Invalid JSON in secrets"
                
                if isinstance(service_account_info, list) and len(service_account_info) > 0:
                    service_account_info = service_account_info[0]
                    
                try:
                    service_account_info = dict(service_account_info)
                except Exception:
                    pass

                if not isinstance(service_account_info, dict):
                    return False, f"Service account info is {type(service_account_info)}, expected dict. Check TOML format."
                    
                SCOPES = ['https://www.googleapis.com/auth/earthengine']
                
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
                ee.Initialize(credentials=creds)
                return True, None
        except FileNotFoundError:
            pass
        except Exception as e:
            error_msg = f"Secrets auth failed: {str(e)}"
            if "gcp_service_account" in st.secrets:
                 return False, error_msg
            pass
            
        if project:
            ee.Initialize(project=project)
        else:
            ee.Initialize()
        return True, None
    except Exception as e:
        error_msg = str(e)
        if "gcp_service_account" not in st.secrets and "not authenticated" in error_msg.lower():
             return False, "auth_required_no_secrets"
        
        if "no project found" in error_msg.lower() or "project=" in error_msg.lower():
            return False, "project_required"
        elif "not authenticated" in error_msg.lower() or "credentials" in error_msg.lower():
            return False, "auth_required"
        else:
            return False, error_msg

def refined_lee_filter(image):
    bandNames = image.bandNames()
    img = ee.Image(image).toFloat()
    weights = ee.List.repeat(ee.List.repeat(1, 3), 3)
    kernel = ee.Kernel.fixed(3, 3, weights, 1, 1, False)
    mean = img.reduceNeighborhood(reducer=ee.Reducer.mean(), kernel=kernel)
    variance = img.reduceNeighborhood(reducer=ee.Reducer.variance(), kernel=kernel)
    variance_mean_sq = variance.divide(mean.multiply(mean))
    sigma_v = ee.Image(0.05)
    b = variance_mean_sq.subtract(sigma_v).divide(variance_mean_sq.multiply(ee.Image(1).add(sigma_v)))
    b = b.min(1).max(0)
    return mean.add(b.multiply(img.subtract(mean))).rename(bandNames)

def otsu_threshold(histogram):
    counts = ee.Array(ee.Dictionary(histogram).get('histogram'))
    means = ee.Array(ee.Dictionary(histogram).get('bucketMeans'))
    size = means.length().get([0])
    total = counts.reduce(ee.Reducer.sum(), [0]).get([0])
    sum_val = means.multiply(counts).reduce(ee.Reducer.sum(), [0]).get([0])
    mean = sum_val.divide(total)
    indices = ee.List.sequence(1, size)
    
    def calculate_bss(i):
        aCounts = counts.slice(0, 0, i)
        aCount = aCounts.reduce(ee.Reducer.sum(), [0]).get([0])
        aMeans = means.slice(0, 0, i)
        aMean = aMeans.multiply(aCounts).reduce(ee.Reducer.sum(), [0]).get([0]).divide(aCount)
        bCount = total.subtract(aCount)
        bMean = sum_val.subtract(aCount.multiply(aMean)).divide(bCount)
        return aCount.multiply(aMean.subtract(mean).pow(2)).add(bCount.multiply(bMean.subtract(mean).pow(2)))
    
    bss = indices.map(calculate_bss)
    return means.sort(bss).get([-1])

def run_flood_analysis(roi, before_start, before_end, after_start, after_end):
    collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
        .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')) \
        .filterBounds(roi).select('VV')
    
    before = collection.filterDate(before_start, before_end).mosaic().clip(roi)
    after = collection.filterDate(after_start, after_end).mosaic().clip(roi)
    
    before_filtered = refined_lee_filter(before)
    after_filtered = refined_lee_filter(after)
    
    histogram = before_filtered.reduceRegion(
        reducer=ee.Reducer.histogram(255, 0.1),
        geometry=roi, scale=30, bestEffort=True
    )
    
    threshold = ee.Number(ee.Algorithms.If(
        histogram.contains('VV'),
        otsu_threshold(histogram.get('VV')), -15
    ))
    
    water_mask = after_filtered.lt(threshold)
    srtm = ee.Image("USGS/SRTMGL1_003")
    slope = ee.Terrain.slope(srtm)
    slope_mask = slope.lt(5)
    water_cleaned = water_mask.updateMask(slope_mask).focalMode(1.5, 'circle', 'pixels', 5)
    permanent_water = before_filtered.lt(threshold)
    flood_only = water_cleaned.And(permanent_water.Not())
    
    flood_area = flood_only.multiply(ee.Image.pixelArea()).reduceRegion(
        reducer=ee.Reducer.sum(), geometry=roi, scale=30, bestEffort=True
    ).get('VV')
    
    roi_area = roi.geometry().area(maxError=1)
    
    return {
        'before_filtered': before_filtered,
        'after_filtered': after_filtered,
        'flood_mask': flood_only,
        'threshold': threshold,
        'flood_area': flood_area,
        'roi_area': roi_area
    }

def export_to_drive(image, description, folder, roi, scale=10):
    task = ee.batch.Export.image.toDrive(
        image=image, description=description, folder=folder,
        scale=scale, region=roi, maxPixels=1e10
    )
    task.start()
    return task

def export_vector_to_drive(vectors, description, folder):
    task = ee.batch.Export.table.toDrive(
        collection=vectors, description=description,
        folder=folder, fileFormat='SHP'
    )
    task.start()
    return task

def check_password():
    password_set = False
    correct_password = None
    
    try:
        if "APP_PASSWORD" in st.secrets:
            password_set = True
            correct_password = st.secrets["APP_PASSWORD"]
        elif "gcp_service_account" in st.secrets and "APP_PASSWORD" in st.secrets["gcp_service_account"]:
            password_set = True
            correct_password = st.secrets["gcp_service_account"]["APP_PASSWORD"]
            
    except Exception as e:
        print(f"Error checking secrets for password: {e}")
        pass

    if not password_set:
        return True

    def password_entered():
        try:
            if st.session_state["password"] == correct_password:
                st.session_state["password_correct"] = True
                del st.session_state["password"]
            else:
                st.session_state["password_correct"] = False
        except KeyError:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input(
            "Please enter the App Password to access:", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.text_input(
            "Password incorrect. Please try again:", type="password", on_change=password_entered, key="password"
        )
        return False
    else:
        return True

def main():
    st.title("Sentinel-1 Flood Mapper")
    st.markdown("**Advanced flood detection and export tool using Google Earth Engine**")
    
    is_authenticated = check_password()
    
    ui_disabled = not is_authenticated

    st.sidebar.header("0. Google Earth Engine Setup")
    
    ee_status = False
    if is_authenticated:
        ee_status, ee_error = initialize_ee()
        if not ee_status:
            if ee_error == "project_required":
                st.error("Google Earth Engine project required!")
                st.info("Please enter your GEE Project ID in the sidebar. You can find it at https://code.earthengine.google.com")
                st.info("If you haven't authenticated yet, click the 'Authenticate GEE' button in the sidebar first.")
            elif ee_error == "auth_required":
                st.error("Google Earth Engine authentication required!")
                st.info("Click the 'Authenticate GEE' button in the sidebar to authenticate.")
            elif ee_error == "auth_required_no_secrets":
                st.error("Authentication Failed: No secrets found!")
                st.warning("For Cloud Deployment: Make sure you have set up 'gcp_service_account' in your Streamlit Secrets.")
                st.info("For Local Use: Click 'Authenticate GEE' in the sidebar.")
            else:
                st.error(f"Failed to initialize Earth Engine: {ee_error}")
    
    gee_project = st.sidebar.text_input(
        "GEE Project ID",
        value="",
        help="Enter your Google Earth Engine project ID. Find it at https://code.earthengine.google.com",
        disabled=ui_disabled
    )
    
    if st.sidebar.button("Authenticate GEE (Local Only)", disabled=ui_disabled):
        if not is_authenticated:
            st.error("Please unlock the app first.")
        else:
            try:
                ee.Authenticate()
                st.success("Authenticated! Please reload the app.")
            except Exception as e:
                st.error(f"Authentication failed: {e}")

    st.sidebar.header("1. Select Dates")
    st.sidebar.subheader("Pre-Event (Before Flood)")
    before_start = st.sidebar.date_input("Before Start Date", value=date(2025, 9, 29), disabled=ui_disabled)
    before_end = st.sidebar.date_input("Before End Date", value=date(2025, 9, 30), disabled=ui_disabled)
    
    st.sidebar.subheader("Post-Event (After Flood)")
    after_start = st.sidebar.date_input("After Start Date", value=date(2025, 10, 5), disabled=ui_disabled)
    after_end = st.sidebar.date_input("After End Date", value=date(2025, 10, 6), disabled=ui_disabled)
    
    st.sidebar.header("2. Region of Interest")
    roi_method = st.sidebar.radio("Select ROI Method:", ["Upload File (GeoJSON/Shapefile)", "Use Coordinates"], disabled=ui_disabled)
    
    roi = None
    
    if roi_method == "Upload File (GeoJSON/Shapefile)":
        uploaded_file = st.sidebar.file_uploader(
            "Upload GeoJSON or Shapefile (.shp)", 
            type=['geojson', 'json', 'shp', 'zip'],
            disabled=ui_disabled
        )
        if uploaded_file and not ui_disabled:
            try:
                file_type = uploaded_file.name.split('.')[-1].lower()
                
                if file_type in ['geojson', 'json']:
                    geojson_data = json.load(uploaded_file)
                    roi = geemap.geojson_to_ee(geojson_data)
                    st.sidebar.success(f"Loaded {uploaded_file.name}")
                
                elif file_type == 'shp':
                    import tempfile
                    import geopandas as gpd
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.shp') as tmp:
                        tmp.write(uploaded_file.read())
                        tmp_path = tmp.name
                    
                    gdf = gpd.read_file(tmp_path)
                    geojson_data = json.loads(gdf.to_json())
                    roi = geemap.geojson_to_ee(geojson_data)
                    st.sidebar.success(f"Loaded {uploaded_file.name}")
                    
                    import os
                    os.unlink(tmp_path)
                
                elif file_type == 'zip':
                    import tempfile
                    import zipfile
                    import geopandas as gpd
                    
                    with tempfile.TemporaryDirectory() as tmpdir:
                        zip_path = os.path.join(tmpdir, 'upload.zip')
                        with open(zip_path, 'wb') as f:
                            f.write(uploaded_file.read())
                        
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(tmpdir)
                        
                        shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
                        if shp_files:
                            shp_path = os.path.join(tmpdir, shp_files[0])
                            gdf = gpd.read_file(shp_path)
                            geojson_data = json.loads(gdf.to_json())
                            roi = geemap.geojson_to_ee(geojson_data)
                            st.sidebar.success(f"Loaded {shp_files[0]} from zip")
                        else:
                            st.sidebar.error("No .shp file found in zip")
            
            except Exception as e:
                st.sidebar.error(f"Error loading file: {str(e)}")
    
    elif roi_method == "Use Coordinates":
        st.sidebar.markdown("Enter bounding box coordinates:")
        col1, col2 = st.sidebar.columns(2)
        with col1:
            min_lon = st.number_input("Min Longitude", value=30.0, format="%.4f", disabled=ui_disabled)
            min_lat = st.number_input("Min Latitude", value=30.0, format="%.4f", disabled=ui_disabled)
        with col2:
            max_lon = st.number_input("Max Longitude", value=31.0, format="%.4f", disabled=ui_disabled)
            max_lat = st.number_input("Max Latitude", value=31.0, format="%.4f", disabled=ui_disabled)
        if not ui_disabled:
            roi = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    
    run_analysis = st.sidebar.button("RUN ANALYSIS", type="primary", disabled=ui_disabled)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<div class="section-header"><h3>Map View</h3></div>', unsafe_allow_html=True)
        map_placeholder = st.empty()
    
    with col2:
        st.markdown('<div class="section-header"><h3>Statistics</h3></div>', unsafe_allow_html=True)
        stats_placeholder = st.empty()
    
    st.markdown('<div class="section-header"><h3>Exports</h3></div>', unsafe_allow_html=True)
    export_placeholder = st.empty()
    
    if not is_authenticated:
        st.warning("🔒 App is locked. Please enter the password above to enable controls and map.")
        return

    if not ee_status:
        st.stop()
        
    if run_analysis and roi:
        with st.spinner("Running flood analysis... This may take a few minutes."):
            try:
                results = run_flood_analysis(
                    roi,
                    before_start.strftime('%Y-%m-%d'),
                    before_end.strftime('%Y-%m-%d'),
                    after_start.strftime('%Y-%m-%d'),
                    after_end.strftime('%Y-%m-%d')
                )
                
                threshold_val = results['threshold'].getInfo()
                flood_area_val = results['flood_area'].getInfo() / 1e6
                roi_area_val = results['roi_area'].getInfo() / 1e6
                
                with stats_placeholder.container():
                    st.markdown('<div class="stat-box">', unsafe_allow_html=True)
                    st.metric("ROI Area", f"{roi_area_val:.2f} km²")
                    st.metric("Otsu Threshold", f"{threshold_val:.2f}")
                    st.markdown(f'<div class="flood-area">Flooded Area: {flood_area_val:.2f} km²</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                Map = geemap.Map()
                Map.centerObject(roi, 10)
                vis_params = {'min': -18.54, 'max': 1.335, 'gamma': 1.26}
                
                Map.addLayer(roi, {'color': 'red'}, 'ROI', False)
                Map.addLayer(results['before_filtered'], vis_params, 'Before (Filtered)', False)
                Map.addLayer(results['after_filtered'], vis_params, 'After (Filtered)', False)
                
                flood_layer = results['flood_mask'].updateMask(results['flood_mask'])
                Map.addLayer(flood_layer, {'palette': ['red']}, 'Flooded Areas', True)
                
                with map_placeholder:
                    Map.to_streamlit(height=600)
                
                with export_placeholder.container():
                    st.info("Click the buttons below to start export tasks")
                    export_folder = st.text_input("Google Drive Folder", value="Flood_Exports")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("Export Flood Mask (Raster)"):
                            export_to_drive(results['flood_mask'].toByte(), 'Flood_Mask_Raster', export_folder, roi)
                            st.success("Export task started! Check Tasks tab in GEE Code Editor.")
                    
                    with col2:
                        if st.button("Export Before Image"):
                            export_to_drive(results['before_filtered'].visualize(vis_params), 'Before_Image_Visualized', export_folder, roi)
                            st.success("Export task started!")
                    
                    with col3:
                        if st.button("Export After Image"):
                            export_to_drive(results['after_filtered'].visualize(vis_params), 'After_Image_Visualized', export_folder, roi)
                            st.success("Export task started!")
                    
                    if st.button("Export Flood Polygons (Shapefile)"):
                        flood_vectors = results['flood_mask'].reduceToVectors(
                            geometry=roi, scale=10, geometryType='polygon',
                            eightConnected=False, labelProperty='zone',
                            reducer=ee.Reducer.countEvery()
                        )
                        export_vector_to_drive(flood_vectors, 'Flood_Mask_Vectors', export_folder)
                        st.success("Vector export task started!")
                
                st.success("Analysis complete!")
                
            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")
                st.exception(e)
    
    elif run_analysis and not roi:
        st.warning("Please select a Region of Interest first!")
    
    with st.expander("How to Use This App"):
        st.markdown("""
        ### Instructions:
        1. **Select Dates**: Choose pre-event and post-event dates
        2. **Define ROI**: Upload GeoJSON, draw on map, or enter coordinates
        3. **Run Analysis**: Click "RUN ANALYSIS" button (takes 1-3 minutes)
        4. **View Results**: Check statistics and map layers
        5. **Export Data**: Click export buttons to save to Google Drive
        
        ### Technical Details:
        - **Sensor**: Sentinel-1 SAR (VV polarization)
        - **Speckle Filter**: Refined Lee (3x3 kernel)
        - **Threshold**: Otsu's automatic thresholding
        - **Slope Filter**: Removes areas with slope > 5°
        - **Export Format**: GeoTIFF (raster), Shapefile (vector)
        """)

if __name__ == "__main__":
    main()
