PB.player = (function(obj) {
  var DEFAULT_RADIUS = 25,
    DEFAULT_SPEED = 20,
    DEFAULT_TURN_SPEED = 30,
    DEFAULT_IMAGE_OFFSET = DEFAULT_RADIUS / 2;

  // constructor
  function player(options) {
    //Default properties that can be overridden
    obj.call(this, options && options.x, options && options.y);
    this.name = 'Player';
    this.degree = 0;

    if (arguments[0]) for (var prop in arguments[0]) this[prop] = arguments[0][prop];

    //Default properties that can't be overridden
    this.speed = DEFAULT_SPEED;
    this.radius = DEFAULT_RADIUS;
    this.drawing = true;
    this.imgOffset = DEFAULT_IMAGE_OFFSET;
  }
  
  extend(obj, player, {
    handlers: [],
    addAngle: function(degree) {
      this.degree = this.degree + (degree % 360);
    },
    canDraw: function() {
      return this.drawing;
    },
    resolve: function(speed) {
      // degrees = radians * 180 / Math.PI;
      var radian = (this.degree * Math.PI) / 180;
      x = this.position.x + Math.cos(radian) * speed;
      y = this.position.y + Math.sin(radian) * speed;
      return new PB.vector(x, y);
    },
    move: function(timer) {
      var me = this;

      if (me.isComputer) {
        // Random movement for computer players (not used in simplified version)
        me.addAngle(Math.floor(Math.random() * 20) - 10);
      } else if (PB.keys[me.left]) {
        me.addAngle(-DEFAULT_TURN_SPEED);
      } else if (PB.keys[me.right]) {
        me.addAngle(DEFAULT_TURN_SPEED);
      }

      // Move player in current direction
      me.position = me.resolve(me.speed);
    },
    restrict: function(bounds) {
      var me = this;

      // Keep player within bounds
      if (me.position.x < bounds.left + me.radius) me.position.x = bounds.left + me.radius;
      else if (me.position.x > bounds.right - me.radius) me.position.x = bounds.right - me.radius;

      if (me.position.y < bounds.top + me.radius) me.position.y = bounds.top + me.radius;
      else if (me.position.y > bounds.bottom - me.radius) me.position.y = bounds.bottom - me.radius;
    }
  });
  
  return player;
})(PB.object);