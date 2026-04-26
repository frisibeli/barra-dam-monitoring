//VERSION=3

function setup() {
  return {
    input: [{
      bands: ["B03", "B11", "SCL"],
      units: "DN"
    }],
    output: {
      bands: 1,
      sampleType: "FLOAT32"
    }
  };
}

function evaluatePixel(sample) {
  // Cloud mask only — SCL 11 (snow/ice) is NOT masked
  // SCL 3=cloud shadow, 8=med cloud, 9=high cloud, 10=thin cirrus
  var scl = sample.SCL;
  if (scl == 3 || scl == 8 || scl == 9 || scl == 10) {
    return [-9999];
  }

  var green = sample.B03 / 10000.0;
  var swir  = sample.B11 / 10000.0;
  return [(green - swir) / (green + swir + 1e-6)];
}
