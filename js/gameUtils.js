// gameUtils.js - Utility functions for the Paint Battle game

function rgbToHex(r, g, b) {
  return `#${((1 << 24) + (r << 16) + (g << 8) + b)
    .toString(16)
    .slice(1)
    .toUpperCase()}`;
}

function hexToRgb(hex) {
  var r = parseInt(hex.slice(1, 3), 16),
    g = parseInt(hex.slice(3, 5), 16),
    b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
}

function imageDataToRgbaList(imageData) {
  const rgbaList = [];
  for (let i = 0, l = imageData.length; i < l; ) {
    const r = imageData[i++];
    const g = imageData[i++];
    const b = imageData[i++];
    const a = imageData[i++];
    rgbaList.push([r, g, b, a]);
  }
  return rgbaList;
}

function getRgbDifference([r1, g1, b1], [r2, g2, b2]) {
  return Math.sqrt(Math.pow(r2 - r1, 2) + Math.pow(g2 - g1, 2) + Math.pow(b2 - b1, 2));
}

function isBlack([r, g, b, a]) {
  return !r && !g && !b;
}

module.exports = {
  rgbToHex,
  hexToRgb,
  imageDataToRgbaList,
  getRgbDifference,
  isBlack
};