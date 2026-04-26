//VERSION=3
// True color with cloud masking only — snow (SCL 11) is NOT masked.
// Used by the snow monitoring pipeline so snow appears in true color.

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
  // Cloud mask only — SCL 11 (snow/ice) is NOT masked here
  if (scl == 3 || scl == 8 || scl == 9 || scl == 10) {
    return [0, 0, 0, 0];
  }

  var gain = 3.5;
  var r = Math.min(255, Math.max(0, Math.round(sample.B04 / 10000.0 * gain * 255)));
  var g = Math.min(255, Math.max(0, Math.round(sample.B03 / 10000.0 * gain * 255)));
  var b = Math.min(255, Math.max(0, Math.round(sample.B02 / 10000.0 * gain * 255)));

  return [r, g, b, 255];
}
