// gameState.test.js

// Mock the window object and animation frame functions
// Regarding the beforeall(), PB.timer, could not be exported and used on each test file
// so we need to have the implementation here and test the funciton
global.window = {
  requestAnimationFrame: jest.fn((callback) => {
    return setTimeout(callback, 16);
  }),
  cancelAnimationFrame: jest.fn((id) => {
    clearTimeout(id);
  })
};

global.PB = {};

describe('PB.timer - Essential Tests', () => {
  let Timer;

  beforeAll(() => {
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
  });

  test('1. should create timer with enabled state by default', () => {
    const timer = new Timer();

    expect(timer.enabled).toBe(true);
    expect(timer.moments).toEqual([]);
    expect(timer.time.elapsed).toBe(0);
  });

  test('2. should create timer with disabled state when parameter is true', () => {
    const timer = new Timer(true);

    expect(timer.enabled).toBe(false);
  });

  test('3. should add non-looping moment with setTimeout', () => {
    const timer = new Timer(true);
    const mockFn = jest.fn();

    const moment = timer.setTimeout(mockFn, 1000);

    expect(timer.moments.length).toBe(1);
    expect(moment.loop).toBe(false);
    expect(moment.interval).toBe(1000);
  });

  test('4. should add looping moment with setInterval', () => {
    const timer = new Timer(true);
    const mockFn = jest.fn();

    const moment = timer.setInterval(mockFn, 500);

    expect(timer.moments.length).toBe(1);
    expect(moment.loop).toBe(true);
    expect(moment.interval).toBe(500);
  });

  test('5. should remove moment with clearTimeout', () => {
    const timer = new Timer(true);
    const mockFn = jest.fn();
    const moment = timer.setTimeout(mockFn, 1000);

    expect(timer.moments.length).toBe(1);

    const result = timer.clearTimeout(moment);

    expect(result).toBe(true);
    expect(timer.moments.length).toBe(0);
  });

  test('6. should enable timer with start method', () => {
    const timer = new Timer(true);

    expect(timer.enabled).toBe(false);

    timer.start();

    expect(timer.enabled).toBe(true);
  });

  test('7. should disable timer with stop method', () => {
    const timer = new Timer();

    expect(timer.enabled).toBe(true);

    timer.stop();

    expect(timer.enabled).toBe(false);
  });

  test('8. should execute setTimeout callback after interval', (done) => {
    jest.useRealTimers();
    const timer = new Timer();
    const mockFn = jest.fn();

    timer.setTimeout(() => {
      mockFn();
      expect(mockFn).toHaveBeenCalledTimes(1);
      timer.stop();
      done();
    }, 100);
  }, 5000);

  test('9. should execute setInterval callback multiple times', (done) => {
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
  }, 5000);

  test('10. should stop executing callbacks when timer is stopped', (done) => {
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
  }, 5000);
});