//VERSION=3
// True color with cloud + snow masking (SCL 11 masked → transparent)
// Used by the water monitoring pipeline.

function setup() {
  return {
    input: [{
      bands: ["B04", "B03", "B02", "SCL"],
      units: "DN"
    }],
    output: {
      bands: 4,
      sampleType: "UINT8"
    }
  };
}

function evaluatePixel(sample) {
  var scl = sample.SCL;
  // Cloud / snow mask → transparent pixel (alpha = 0)
  if (scl == 3 || scl == 8 || scl == 9 || scl == 10 || scl == 11) {
    return [0, 0, 0, 0];
  }

  // Reflectance → 0-255 with brightness boost (×3.5 is a common Sentinel-2 stretch)
  var gain = 3.5;
  var r = Math.min(255, Math.max(0, Math.round(sample.B04 / 10000.0 * gain * 255)));
  var g = Math.min(255, Math.max(0, Math.round(sample.B03 / 10000.0 * gain * 255)));
  var b = Math.min(255, Math.max(0, Math.round(sample.B02 / 10000.0 * gain * 255)));

  return [r, g, b, 255];
}
