// gameState.test.js

// Mock the window object and animation frame functions
global.window = {
  requestAnimationFrame: jest.fn((callback) => {
    return setTimeout(callback, 16); // Simulate ~60fps
  }),
  cancelAnimationFrame: jest.fn((id) => {
    clearTimeout(id);
  })
};

// Mock PB global object
global.PB = {};

// Import the timer after setting up mocks
// Assuming gameState.js exports the timer or we need to execute it
// For testing, we'll need to make the timer accessible
// If gameState.js doesn't export, you'll need to modify it to: module.exports = PB.timer;

describe('PB.timer', () => {
  let Timer;

  beforeAll(() => {
    // Execute the timer creation
    Timer = (function({ requestAnimationFrame, cancelAnimationFrame }) {
      const fps60 = 1000 / 60;

      function moment(loop, fn, interval) {
        this.loop = loop;
        this.fn = fn;
        this.interval = interval || fps60;
        this.delta = 0;
      }

      function timer(disable) {
        var me = this;
        me.id = null;
        me.interval = fps60;
        me.enabled = disable ? false : true;
        me.then = Date.now();
        me.moments = [];
        me.time = { elapsed: 0 };
        me.boundLoop = me.loop.bind(me);
        me.queue();
      }

      timer.prototype = {
        loop: function() {
          var me = this;

          if (!me.enabled) return;
          me.now = Date.now();
          var delta = me.now - me.then;

          if (delta > me.interval) {
            me.then = me.now - (delta % me.interval);
            me.time.elapsed += me.interval;
            for (var i = me.moments.length; i--; ) {
              if (!me.enabled) return;
              var m = me.moments[i];
              m.delta += me.interval;

              if (m.delta < m.interval) continue;
              m.fn();
              m.delta = 0;

              if (!m.loop) me.moments.splice(i, 1);
            }
          }
          me.queue();
        },
        start: function() {
          var me = this;

          if (me.enabled) return;
          me.enabled = true;
          me.then = Date.now();
          me.queue();
        },
        queue: function() {
          this.id = requestAnimationFrame(this.boundLoop);
        },
        stop: function() {
          this.enabled = false;
          this.id && cancelAnimationFrame(this.id);
        },
        setTimeout: function(fn, interval) {
          var m = new moment(false, fn, interval);
          this.moments.push(m);
          return m;
        },
        setInterval: function(fn, interval) {
          var m = new moment(true, fn, interval);
          this.moments.push(m);
          return m;
        },
        clearTimeout: function(m) {
          const index = this.moments.indexOf(m);
          if (~index) this.moments.splice(index, 1);
          return !!~index;
        },
      };
      return timer;
    })(window);
  });

  beforeEach(() => {
    jest.clearAllMocks();
    jest.clearAllTimers();
  });

  describe('Constructor', () => {
    test('should create timer with default enabled state', () => {
      const timer = new Timer();

      expect(timer.enabled).toBe(true);
      expect(timer.moments).toEqual([]);
      expect(timer.time.elapsed).toBe(0);
      expect(timer.interval).toBe(1000 / 60);
    });

    test('should create timer with disabled state when parameter is true', () => {
      const timer = new Timer(true);

      expect(timer.enabled).toBe(false);
    });

    test('should call requestAnimationFrame on initialization', () => {
      const timer = new Timer();

      expect(window.requestAnimationFrame).toHaveBeenCalled();
    });

    test('should have then property set to current time', () => {
      const beforeTime = Date.now();
      const timer = new Timer();
      const afterTime = Date.now();

      expect(timer.then).toBeGreaterThanOrEqual(beforeTime);
      expect(timer.then).toBeLessThanOrEqual(afterTime);
    });
  });

  describe('setTimeout', () => {
    test('should add a non-looping moment to moments array', () => {
      const timer = new Timer(true); // Disabled to prevent auto-execution
      const mockFn = jest.fn();

      const moment = timer.setTimeout(mockFn, 1000);

      expect(timer.moments.length).toBe(1);
      expect(timer.moments[0]).toBe(moment);
      expect(moment.loop).toBe(false);
      expect(moment.fn).toBe(mockFn);
      expect(moment.interval).toBe(1000);
    });

    test('should use default interval if not provided', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();

      const moment = timer.setTimeout(mockFn);

      expect(moment.interval).toBe(1000 / 60);
    });

    test('should return the moment object', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();

      const moment = timer.setTimeout(mockFn, 500);

      expect(moment).toBeDefined();
      expect(moment.fn).toBe(mockFn);
    });
  });

  describe('setInterval', () => {
    test('should add a looping moment to moments array', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();

      const moment = timer.setInterval(mockFn, 1000);

      expect(timer.moments.length).toBe(1);
      expect(timer.moments[0]).toBe(moment);
      expect(moment.loop).toBe(true);
      expect(moment.fn).toBe(mockFn);
      expect(moment.interval).toBe(1000);
    });

    test('should return the moment object', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();

      const moment = timer.setInterval(mockFn, 500);

      expect(moment).toBeDefined();
      expect(moment.loop).toBe(true);
    });
  });

  describe('clearTimeout', () => {
    test('should remove moment from moments array', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();
      const moment = timer.setTimeout(mockFn, 1000);

      expect(timer.moments.length).toBe(1);

      const result = timer.clearTimeout(moment);

      expect(result).toBe(true);
      expect(timer.moments.length).toBe(0);
    });

    test('should return false when moment not found', () => {
      const timer = new Timer(true);
      const fakeMoment = { loop: false, fn: jest.fn(), interval: 1000, delta: 0 };

      const result = timer.clearTimeout(fakeMoment);

      expect(result).toBe(false);
    });

    test('should handle clearing already cleared moment', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();
      const moment = timer.setTimeout(mockFn, 1000);

      timer.clearTimeout(moment);
      const result = timer.clearTimeout(moment);

      expect(result).toBe(false);
    });
  });

  describe('start', () => {
    test('should enable the timer', () => {
      const timer = new Timer(true); // Start disabled

      expect(timer.enabled).toBe(false);

      timer.start();

      expect(timer.enabled).toBe(true);
    });

    test('should call requestAnimationFrame', () => {
      const timer = new Timer(true);
      jest.clearAllMocks();

      timer.start();

      expect(window.requestAnimationFrame).toHaveBeenCalled();
    });

    test('should not restart if already enabled', () => {
      const timer = new Timer(); // Starts enabled
      const initialThen = timer.then;

      timer.start();

      expect(timer.enabled).toBe(true);
      expect(timer.then).toBe(initialThen);
    });

    test('should reset then property', () => {
      const timer = new Timer(true);
      timer.then = 0; // Set to old value

      const beforeTime = Date.now();
      timer.start();
      const afterTime = Date.now();

      expect(timer.then).toBeGreaterThanOrEqual(beforeTime);
      expect(timer.then).toBeLessThanOrEqual(afterTime);
    });
  });

  describe('stop', () => {
    test('should disable the timer', () => {
      const timer = new Timer();

      expect(timer.enabled).toBe(true);

      timer.stop();

      expect(timer.enabled).toBe(false);
    });

    test('should call cancelAnimationFrame', () => {
      const timer = new Timer();
      jest.clearAllMocks();

      timer.stop();

      expect(window.cancelAnimationFrame).toHaveBeenCalled();
    });

    test('should handle stopping when already stopped', () => {
      const timer = new Timer(true);

      timer.stop();

      expect(timer.enabled).toBe(false);
    });
  });

  describe('loop', () => {
    test('should not execute when disabled', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();
      timer.setTimeout(mockFn, 0);

      timer.loop();

      expect(mockFn).not.toHaveBeenCalled();
    });

    test('should execute moments when interval has passed', (done) => {
      jest.useRealTimers();
      const timer = new Timer(true);
      const mockFn = jest.fn();
      
      timer.setTimeout(mockFn, 50);
      timer.then = Date.now() - 100; 
      timer.enabled = true;

      timer.loop();

      setTimeout(() => {
        expect(mockFn).toHaveBeenCalled();
        timer.stop();
        done();
      }, 20);
    });

    test('should update elapsed time', () => {
      jest.useRealTimers();
      const timer = new Timer(true);
      timer.enabled = true;
      timer.then = Date.now() - 100; // Simulate 100ms has passed
      
      const initialElapsed = timer.time.elapsed;
      timer.loop();

      expect(timer.time.elapsed).toBeGreaterThan(initialElapsed);
      timer.stop();
    });

    test('should remove non-looping moments after execution', (done) => {
      jest.useRealTimers();
      const timer = new Timer(true);
      const mockFn = jest.fn();
      
      timer.setTimeout(mockFn, 50);
      timer.enabled = true;
      timer.then = Date.now() - 100;

      expect(timer.moments.length).toBe(1);

      timer.loop();

      setTimeout(() => {
        expect(timer.moments.length).toBe(0);
        timer.stop();
        done();
      }, 20);
    });

    test('should keep looping moments after execution', (done) => {
      jest.useRealTimers();
      const timer = new Timer(true);
      const mockFn = jest.fn();
      
      timer.setInterval(mockFn, 50);
      timer.enabled = true;
      timer.then = Date.now() - 100;

      expect(timer.moments.length).toBe(1);

      timer.loop();

      setTimeout(() => {
        expect(timer.moments.length).toBe(1);
        timer.stop();
        done();
      }, 20);
    });
  });

  describe('queue', () => {
    test('should call requestAnimationFrame', () => {
      const timer = new Timer(true);
      jest.clearAllMocks();

      timer.queue();

      expect(window.requestAnimationFrame).toHaveBeenCalled();
      expect(window.requestAnimationFrame).toHaveBeenCalledWith(timer.boundLoop);
    });

    test('should store animation frame id', () => {
      const timer = new Timer(true);
      const mockId = 123;
      window.requestAnimationFrame.mockReturnValueOnce(mockId);

      timer.queue();

      expect(timer.id).toBe(mockId);
    });
  });

  describe('Integration Tests', () => {
    test('should execute setTimeout callback after specified interval', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const mockFn = jest.fn();
      const startTime = Date.now();

      timer.setTimeout(() => {
        mockFn();
        const endTime = Date.now();
        const elapsed = endTime - startTime;
        
        expect(mockFn).toHaveBeenCalledTimes(1);
        expect(elapsed).toBeGreaterThanOrEqual(90);
        timer.stop();
        done();
      }, 100);
    }, 10000);

    test('should execute setInterval callback multiple times', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const mockFn = jest.fn();
      let callCount = 0;

      timer.setInterval(() => {
        callCount++;
        mockFn();
        
        if (callCount >= 3) {
          expect(mockFn).toHaveBeenCalledTimes(3);
          timer.stop();
          done();
        }
      }, 50);
    }, 10000);

    test('should handle multiple moments simultaneously', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const mockFn1 = jest.fn();
      const mockFn2 = jest.fn();
      const mockFn3 = jest.fn();

      timer.setTimeout(mockFn1, 50);
      timer.setTimeout(mockFn2, 100);
      timer.setInterval(mockFn3, 75);

      setTimeout(() => {
        expect(mockFn1).toHaveBeenCalled();
        expect(mockFn2).toHaveBeenCalled();
        expect(mockFn3).toHaveBeenCalled();
        timer.stop();
        done();
      }, 200);
    }, 10000);

    test('should stop executing when stopped', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const mockFn = jest.fn();

      timer.setInterval(mockFn, 50);

      setTimeout(() => {
        timer.stop();
        const callCountAtStop = mockFn.mock.calls.length;

        setTimeout(() => {
          expect(mockFn.mock.calls.length).toBe(callCountAtStop);
          done();
        }, 100);
      }, 150);
    }, 10000);

    test('should resume executing when restarted', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const mockFn = jest.fn();

      timer.setInterval(mockFn, 50);

      setTimeout(() => {
        timer.stop();
        const callCountAtStop = mockFn.mock.calls.length;

        setTimeout(() => {
          timer.start();

          setTimeout(() => {
            expect(mockFn.mock.calls.length).toBeGreaterThan(callCountAtStop);
            timer.stop();
            done();
          }, 100);
        }, 50);
      }, 100);
    }, 10000);
  });

  describe('Edge Cases', () => {
    test('should handle zero interval', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();

      timer.setTimeout(mockFn, 0);

      expect(timer.moments[0].interval).toBe(0);
    });

    test('should handle very large intervals', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();
      const largeInterval = 1000000;

      timer.setTimeout(mockFn, largeInterval);

      expect(timer.moments[0].interval).toBe(largeInterval);
    });

    test('should handle empty moments array in loop', () => {
      const timer = new Timer(true);
      timer.enabled = true;

      expect(() => timer.loop()).not.toThrow();
    });

    test('should handle clearing moments during execution', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      let moment1, moment2;

      moment1 = timer.setTimeout(() => {
        timer.clearTimeout(moment2);
      }, 50);

      const mockFn2 = jest.fn();
      moment2 = timer.setTimeout(mockFn2, 75);

      setTimeout(() => {
        expect(mockFn2).not.toHaveBeenCalled();
        timer.stop();
        done();
      }, 150);
    }, 10000);
  });

  describe('Time Accuracy', () => {
    test('should maintain accurate elapsed time', (done) => {
      jest.useRealTimers();
      const timer = new Timer();
      const startElapsed = timer.time.elapsed;

      setTimeout(() => {
        const elapsedDiff = timer.time.elapsed - startElapsed;
        expect(elapsedDiff).toBeGreaterThanOrEqual(80);
        expect(elapsedDiff).toBeLessThanOrEqual(120);
        timer.stop();
        done();
      }, 100);
    }, 10000);

    test('should track delta correctly for moments', () => {
      const timer = new Timer(true);
      const mockFn = jest.fn();
      const moment = timer.setTimeout(mockFn, 1000);

      expect(moment.delta).toBe(0);
    });
  });
});