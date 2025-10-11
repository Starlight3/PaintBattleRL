// Tests related to colors of the screen, this includes colors of players
const {
  isBlack,
  rgbToHex,
  hexToRgb,
  getRgbDifference,
  imageDataToRgbaList
} = require('../gameUtils');

describe('Game.js Utility Functions', () => {
  
  describe('isBlack', () => {
    test('should return true for black color [0,0,0,255]', () => {
      expect(isBlack([0, 0, 0, 255])).toBe(true);
    });

    test('should return true for transparent black [0,0,0,0]', () => {
      expect(isBlack([0, 0, 0, 0])).toBe(true);
    });

    test('should return false for white color [255,255,255,255]', () => {
      expect(isBlack([255, 255, 255, 255])).toBe(false);
    });

    test('should return false for red color [255,0,0,255]', () => {
      expect(isBlack([255, 0, 0, 255])).toBe(false);
    });

    test('should return false for any color with non-zero RGB values', () => {
      expect(isBlack([1, 0, 0, 255])).toBe(false);
      expect(isBlack([0, 1, 0, 255])).toBe(false);
      expect(isBlack([0, 0, 1, 255])).toBe(false);
    });
  });

  describe('rgbToHex', () => {
    test('should convert black RGB to hex', () => {
      expect(rgbToHex(0, 0, 0)).toBe('#000000');
    });

    test('should convert white RGB to hex', () => {
      expect(rgbToHex(255, 255, 255)).toBe('#FFFFFF');
    });

    test('should convert red RGB to hex', () => {
      expect(rgbToHex(255, 0, 0)).toBe('#FF0000');
    });

    test('should convert green RGB to hex', () => {
      expect(rgbToHex(0, 255, 0)).toBe('#00FF00');
    });

    test('should convert blue RGB to hex', () => {
      expect(rgbToHex(0, 0, 255)).toBe('#0000FF');
    });

    test('should handle mixed colors', () => {
      expect(rgbToHex(128, 64, 192)).toBe('#8040C0');
    });
  });

  describe('hexToRgb', () => {
    test('should convert black hex to RGB', () => {
      expect(hexToRgb('#000000')).toEqual([0, 0, 0]);
    });

    test('should convert white hex to RGB', () => {
      expect(hexToRgb('#FFFFFF')).toEqual([255, 255, 255]);
    });

    test('should convert red hex to RGB', () => {
      expect(hexToRgb('#FF0000')).toEqual([255, 0, 0]);
    });

    test('should convert lowercase hex to RGB', () => {
      expect(hexToRgb('#ff0000')).toEqual([255, 0, 0]);
    });

    test('should handle mixed case hex values', () => {
      expect(hexToRgb('#8040C0')).toEqual([128, 64, 192]);
    });
  });

  describe('getRgbDifference', () => {
    test('should return 0 for identical colors', () => {
      expect(getRgbDifference([100, 100, 100], [100, 100, 100])).toBe(0);
    });

    test('should calculate difference between black and white', () => {
      const diff = getRgbDifference([0, 0, 0], [255, 255, 255]);
      expect(diff).toBeCloseTo(441.67, 1);
    });

    test('should calculate difference between red and blue', () => {
      const diff = getRgbDifference([255, 0, 0], [0, 0, 255]);
      expect(diff).toBeCloseTo(360.62, 1);
    });

    test('should be commutative', () => {
      const diff1 = getRgbDifference([100, 50, 150], [200, 100, 50]);
      const diff2 = getRgbDifference([200, 100, 50], [100, 50, 150]);
      expect(diff1).toBe(diff2);
    });
  });

  describe('imageDataToRgbaList', () => {
    test('should convert empty array', () => {
      expect(imageDataToRgbaList([])).toEqual([]);
    });

    test('should convert single pixel', () => {
      const imageData = [255, 0, 0, 255];
      expect(imageDataToRgbaList(imageData)).toEqual([[255, 0, 0, 255]]);
    });

    test('should convert multiple pixels', () => {
      const imageData = [255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255];
      expect(imageDataToRgbaList(imageData)).toEqual([
        [255, 0, 0, 255],
        [0, 255, 0, 255],
        [0, 0, 255, 255]
      ]);
    });

    test('should handle partial transparency', () => {
      const imageData = [100, 100, 100, 128];
      expect(imageDataToRgbaList(imageData)).toEqual([[100, 100, 100, 128]]);
    });
  });
});

describe('Edge Cases', () => {
  describe('Timer Display', () => {
    test('should not display negative time', () => {
      const GAME_INTERVAL = 90 * 1000;
      const elapsedMs = 95000;
      const remainingSeconds = Math.ceil((GAME_INTERVAL - elapsedMs) / 1000);
      const displayTime = Math.max(0, remainingSeconds);
      
      expect(displayTime).toBe(0);
    });

    test('should round up remaining seconds', () => {
      const GAME_INTERVAL = 90 * 1000;
      const elapsedMs = 1500;
      const remainingSeconds = Math.ceil((GAME_INTERVAL - elapsedMs) / 1000);
      
      expect(remainingSeconds).toBe(89);
    });
  });
});