//VERSION=3

function setup() {
  return {
    input: [{
      bands: ["B03", "B08", "B11", "SCL"],
      units: "DN"
    }],
    output: {
      bands: 1,
      sampleType: "FLOAT32"
    }
  };
}

function evaluatePixel(sample) {
  // SCL = Scene Classification Layer (Sentinel-2 L2A)
  // Values 3=cloud shadow, 8=med cloud, 9=high cloud, 10=thin cirrus, 11=snow
  // Return -9999 for masked pixels so we can ignore them in Python
  var scl = sample.SCL;
  if (scl == 3 || scl == 8 || scl == 9 || scl == 10 || scl == 11) {
    return [-9999];
  }

  // Reflectance = DN / 10000 for Sentinel-2 L2A
  var green = sample.B03 / 10000.0;
  var nir   = sample.B08 / 10000.0;
  var swir  = sample.B11 / 10000.0;

  // NDWI (McFeeters): highlights open water, good for large bodies
  var ndwi  = (green - nir)  / (green + nir  + 1e-6);

  // MNDWI (Xu): suppresses built-up/soil false positives better
  var mndwi = (green - swir) / (green + swir + 1e-6);

  // Return the higher of the two — maximises water detection
  return [Math.max(ndwi, mndwi)];
}
