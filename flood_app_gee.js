/* ===========================================================================================
                               FLOOD MAPPING APP - FINAL VERSION
===========================================================================================
*/

// --- 1. UI SETUP & STYLING ---

var COLORS = {
    primary: '#007bff',
    secondary: '#346ea0ff',
    success: '#28a745',
    danger: '#dc3545',
    light: '#f8f9fa',
    dark: '#343a40',
    white: '#ffffff',
    red: '#dc3545'
};

var mainPanel = ui.Panel({
    style: { width: '400px', padding: '15px', backgroundColor: COLORS.light }
});

var mapPanel = ui.Map();
mapPanel.setOptions('HYBRID');

ui.root.clear();
ui.root.add(ui.SplitPanel(mainPanel, mapPanel));

// Header
mainPanel.add(ui.Label({
    value: 'Sentinel-1 Flood Mapper',
    style: { fontSize: '28px', fontWeight: 'bold', color: COLORS.dark, margin: '0 0 10px 0' }
}));
mainPanel.add(ui.Label({
    value: 'Advanced flood detection and export tool.',
    style: { fontSize: '14px', color: COLORS.secondary, margin: '0 0 20px 0' }
}));


// --- 2. INPUT SECTION ---

function createSection(title) {
    var headerPanel = ui.Panel({ layout: ui.Panel.Layout.flow('vertical'), style: { margin: '20px 0 10px 0' } });
    var label = ui.Label(title, {
        fontSize: '16px', fontWeight: 'bold', color: COLORS.dark,
        margin: '0 0 5px 0'
    });
    var line = ui.Panel({
        style: { height: '2px', backgroundColor: COLORS.primary, margin: '0 0 5px 0', stretch: 'horizontal' }
    });
    headerPanel.add(label);
    headerPanel.add(line);
    return headerPanel;
}

mainPanel.add(createSection('1. Select Dates'));

function createDateInput(label, defaultVal) {
    var panel = ui.Panel({ layout: ui.Panel.Layout.flow('horizontal'), style: { margin: '5px 0' } });
    panel.add(ui.Label(label, { width: '80px', margin: '5px 0 0 0', fontWeight: 'bold' }));
    var picker = ui.Textbox({ placeholder: 'YYYY-MM-DD', value: defaultVal, style: { width: '120px' } });
    panel.add(picker);
    return { panel: panel, input: picker };
}

var beforeStart = createDateInput('Before Start:', '2025-09-29');
var beforeEnd = createDateInput('Before End:', '2025-09-30');
var afterStart = createDateInput('After Start:', '2025-10-05');
var afterEnd = createDateInput('After End:', '2025-10-06');

mainPanel.add(ui.Label('Pre-Event (Before Flood):', { fontSize: '12px', color: COLORS.secondary }));
mainPanel.add(beforeStart.panel);
mainPanel.add(beforeEnd.panel);

mainPanel.add(ui.Label('Post-Event (After Flood):', { fontSize: '12px', color: COLORS.secondary, margin: '10px 0 0 0' }));
mainPanel.add(afterStart.panel);
mainPanel.add(afterEnd.panel);

// Run Button
var runButton = ui.Button({
    label: 'RUN ANALYSIS',
    style: {
        stretch: 'horizontal', margin: '25px 0',
        backgroundColor: COLORS.primary, color: COLORS.red, fontWeight: 'bold'
    }
});
mainPanel.add(runButton);


// --- 3. RESULTS SECTION ---

mainPanel.add(createSection('2. Statistics'));
var statsPanel = ui.Panel({ style: { backgroundColor: COLORS.white, padding: '10px', border: '1px solid #ddd' } });
mainPanel.add(statsPanel);
statsPanel.add(ui.Label('Run analysis to see statistics.', { color: COLORS.secondary }));

mainPanel.add(createSection('3. Exports'));
var exportPanel = ui.Panel({ style: { backgroundColor: COLORS.white, padding: '10px', border: '1px solid #ddd' } });
mainPanel.add(exportPanel);
exportPanel.add(ui.Label('Export tasks will appear in the "Tasks" tab.', { color: COLORS.secondary }));


// --- 4. LOGIC ---

// ROI Definition (Using 'table' import or fallback)
var roi = ee.FeatureCollection(table);
mapPanel.centerObject(roi, 10);
mapPanel.addLayer(roi, { color: 'red' }, 'ROI', false);

function runAnalysis() {
    statsPanel.clear();
    exportPanel.clear();
    statsPanel.add(ui.Label('Calculating...', { color: COLORS.secondary }));

    mapPanel.layers().reset();
    mapPanel.addLayer(roi, { color: 'red' }, 'ROI', false);

    // 1. ROI Area Calculation
    var roiArea = roi.geometry().area().divide(1e6); // km2
    roiArea.evaluate(function (area) {
        statsPanel.add(ui.Label('ROI Area: ' + area.toFixed(2) + ' km²', { fontWeight: 'bold' }));
    });

    // 2. Image Processing
    var bStart = beforeStart.input.getValue();
    var bEnd = beforeEnd.input.getValue();
    var aStart = afterStart.input.getValue();
    var aEnd = afterEnd.input.getValue();

    var collection = ee.ImageCollection('COPERNICUS/S1_GRD')
        .filter(ee.Filter.eq('instrumentMode', 'IW'))
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
        .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
        .filterBounds(roi)
        .select('VV');

    var before = collection.filterDate(bStart, bEnd).mosaic().clip(roi);
    var after = collection.filterDate(aStart, aEnd).mosaic().clip(roi);

    // Refined Lee Filter
    function RefinedLee(image) {
        var bandNames = image.bandNames();
        var img = ee.Image(image).toFloat();
        var weights = ee.List.repeat(ee.List.repeat(1, 3), 3);
        var kernel = ee.Kernel.fixed(3, 3, weights, 1, 1, false);
        var mean = img.reduceNeighborhood({ reducer: ee.Reducer.mean(), kernel: kernel });
        var variance = img.reduceNeighborhood({ reducer: ee.Reducer.variance(), kernel: kernel });
        var variance_mean_sq = variance.divide(mean.multiply(mean));
        var sigma_v = ee.Image(0.05);
        var b = variance_mean_sq.subtract(sigma_v).divide(variance_mean_sq.multiply(ee.Image(1).add(sigma_v)));
        b = b.min(1).max(0);
        return mean.add(b.multiply(img.subtract(mean))).rename(bandNames);
    }

    var before_filtered = RefinedLee(before);
    var after_filtered = RefinedLee(after);

    // Visualization Parameters from User
    var visParams = { min: -18.54, max: 1.335, gamma: 1.26 };

    mapPanel.addLayer(before_filtered, visParams, 'Before (Filtered)', false);
    mapPanel.addLayer(after_filtered, visParams, 'After (Filtered)', false);

    // Otsu Thresholding
    var histogram = before_filtered.reduceRegion({
        reducer: ee.Reducer.histogram(255, 0.1),
        geometry: roi,
        scale: 30,
        bestEffort: true
    });

    var otsu = function (histogram) {
        var counts = ee.Array(ee.Dictionary(histogram).get('histogram'));
        var means = ee.Array(ee.Dictionary(histogram).get('bucketMeans'));
        var size = means.length().get([0]);
        var total = counts.reduce(ee.Reducer.sum(), [0]).get([0]);
        var sum = means.multiply(counts).reduce(ee.Reducer.sum(), [0]).get([0]);
        var mean = sum.divide(total);
        var indices = ee.List.sequence(1, size);
        var bss = indices.map(function (i) {
            var aCounts = counts.slice(0, 0, i);
            var aCount = aCounts.reduce(ee.Reducer.sum(), [0]).get([0]);
            var aMeans = means.slice(0, 0, i);
            var aMean = aMeans.multiply(aCounts).reduce(ee.Reducer.sum(), [0]).get([0]).divide(aCount);
            var bCount = total.subtract(aCount);
            var bMean = sum.subtract(aCount.multiply(aMean)).divide(bCount);
            return aCount.multiply(aMean.subtract(mean).pow(2)).add(bCount.multiply(bMean.subtract(mean).pow(2)));
        });
        return means.sort(bss).get([-1]);
    };

    var threshold = ee.Number(ee.Algorithms.If(
        histogram.contains('VV'),
        otsu(histogram.get('VV')),
        -15
    ));

    // Display threshold value
    threshold.evaluate(function (t) {
        statsPanel.add(ui.Label('Otsu Threshold: ' + t.toFixed(2), { color: COLORS.dark, fontWeight: 'bold' }));
    });

    // Flood Detection
    var water_mask = after_filtered.lt(threshold);
    var srtm = ee.Image("USGS/SRTMGL1_003");
    var slope = ee.Terrain.slope(srtm);
    var slope_mask = slope.lt(5);
    var water_cleaned = water_mask.updateMask(slope_mask).focalMode(1.5, 'circle', 'pixels', 5);
    var permanent_water = before_filtered.lt(threshold);
    var flood_only = water_cleaned.and(permanent_water.not());
    var flood_layer = flood_only.updateMask(flood_only);

    mapPanel.addLayer(flood_layer, { palette: ['red'] }, 'Flooded Areas');

    // 3. Flood Area Calculation
    var floodArea = flood_only.multiply(ee.Image.pixelArea()).reduceRegion({
        reducer: ee.Reducer.sum(),
        geometry: roi,
        scale: 30,
        bestEffort: true
    }).get('VV');

    floodArea.evaluate(function (area) {
        var km2 = (area / 1e6).toFixed(2);
        statsPanel.add(ui.Label('Flooded Area: ' + km2 + ' km²', {
            fontWeight: 'bold', color: COLORS.danger, fontSize: '18px', margin: '10px 0'
        }));

        // Add Histograms
        statsPanel.add(ui.Label('Histograms:', { fontWeight: 'bold', margin: '10px 0' }));
        statsPanel.add(ui.Chart.image.histogram(before_filtered, roi, 30).setOptions({ title: 'Before Flood', legend: { position: 'none' } }));
        statsPanel.add(ui.Chart.image.histogram(after_filtered, roi, 30).setOptions({ title: 'After Flood', legend: { position: 'none' } }));
    });

    // 4. Exports
    exportPanel.add(ui.Label('Generating Export Tasks...', { color: COLORS.success }));

    // Export Raster (Flood Mask)
    Export.image.toDrive({
        image: flood_only.toByte(),
        description: 'Flood_Mask_Raster',
        folder: 'Flood_Exports',
        scale: 10,
        region: roi,
        maxPixels: 1e10
    });

    // Export Vector (Flood Polygons)
    var floodVectors = flood_only.reduceToVectors({
        geometry: roi,
        scale: 10,
        geometryType: 'polygon',
        eightConnected: false,
        labelProperty: 'zone',
        reducer: ee.Reducer.countEvery()
    });

    Export.table.toDrive({
        collection: floodVectors,
        description: 'Flood_Mask_Vectors',
        folder: 'Flood_Exports',
        fileFormat: 'SHP'
    });

    // Export Visualized Images (Before & After)
    Export.image.toDrive({
        image: before_filtered.visualize(visParams),
        description: 'Before_Image_Visualized',
        folder: 'Flood_Exports',
        scale: 10,
        region: roi,
        maxPixels: 1e10
    });

    Export.image.toDrive({
        image: after_filtered.visualize(visParams),
        description: 'After_Image_Visualized',
        folder: 'Flood_Exports',
        scale: 10,
        region: roi,
        maxPixels: 1e10
    });

    // Export Colored Flood Map (red flood areas on gray background)
    var floodVisualization = flood_only.visualize({ palette: ['red'], min: 0, max: 1 });
    Export.image.toDrive({
        image: floodVisualization,
        description: 'Flood_Map_Colored',
        folder: 'Flood_Exports',
        scale: 10,
        region: roi,
        maxPixels: 1e10
    });

    exportPanel.add(ui.Label('done', { fontWeight: 'bold' }));
}

runButton.onClick(runAnalysis);
