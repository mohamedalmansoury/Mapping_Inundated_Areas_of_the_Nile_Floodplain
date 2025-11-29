# Mapping Inundated Areas of the Nile Floodplain

A Streamlit web application for automated flood detection and mapping of inundated areas in the Nile floodplain using Google Earth Engine and Sentinel-1 SAR data.


# Nile Floodplain Mapping menofia 2025

**Advanced flood detection and export tool using Google Earth Engine**

## Live Application
[Click here to access the Streamlit App](https://mappinginundatedareasofthenilefloodplain-almansoury.streamlit.app/)

## Overview

This project provides an interactive tool for detecting and mapping flooded areas using Sentinel-1 SAR imagery. It was specifically developed for monitoring flood events in the Nile floodplain region, particularly the Menofia area in Egypt.

**Two versions available:**
- **Python/Streamlit** (`flood_app_streamlit.py`) - Web application with interactive UI
- **JavaScript** (`flood_app_gee.js`) - For Google Earth Engine Code Editor

## Features

- Automated Flood Detection using Otsu thresholding algorithm
- Speckle Filtering with Refined Lee filter for SAR noise reduction
- Interactive Map visualization with before/after comparison
- Multiple ROI Input Methods (GeoJSON, Shapefile, coordinates)
- Export to Google Drive (raster and vector formats)

## Quick Start

### Running Locally

```bash
python setup_and_run.py
```

The app will open in your browser at `http://localhost:8501`

### Using Google Earth Engine Code Editor

1. Go to https://code.earthengine.google.com
2. Open `flood_app_gee.js` from this repository
3. Copy and paste the code into GEE Code Editor
4. Upload your ROI or draw a geometry
5. Click "Run"

## Usage

1. **GEE Setup**: Enter your GEE Project ID and authenticate
2. **Select Dates**: Choose pre-event and post-event dates  
3. **Define ROI**: Upload GeoJSON/Shapefile or enter coordinates
4. **Run Analysis**: Click "RUN ANALYSIS" button (takes 1-3 minutes)
5. **View Results**: Check statistics and map layers
6. **Export Data**: Save results to Google Drive

## Technical Details

- **Data Source**: Sentinel-1 SAR (VV polarization, Ascending orbit)
- **Processing**: Refined Lee filter, Otsu thresholding, slope masking
- **Platform**: Google Earth Engine
- **Framework**: Streamlit + geemap

## Project Structure

```
Nile-Floodplain-Mapping/
├── flood_app_streamlit.py    # Streamlit web app
├── flood_app_gee.js           # GEE Code Editor version
├── setup_and_run.py           # Quick setup script
├── setup_git.py               # Git initialization
├── convert_shapefile.py       # Shapefile converter
├── requirements.txt           # Python dependencies
└── data/
    ├── menofia_3km.geojson   # Menofia region ROI
    └── sample_roi.geojson    # Sample test region
```

## Example: Menofia Region

Pre-configured ROI for the Menofia region in Egypt's Nile Delta:
- **File**: `data/menofia_3km.geojson`
- **Coordinates**: 30.73°E to 31.06°E, 30.18°N to 30.77°N
- **Area**: Nile floodplain agricultural zone

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this tool in your research, please cite:

```
Mapping Inundated Areas of the Nile Floodplain. (2025). 
GitHub repository: https://github.com/yourusername/Nile-Floodplain-Mapping
```

## Acknowledgments

- Google Earth Engine for cloud-based geospatial analysis
- ESA Copernicus Programme for Sentinel-1 SAR data
- Streamlit for the web application framework
