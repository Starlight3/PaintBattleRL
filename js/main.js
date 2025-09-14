// Randomize initial player position within 600x600 bounds
var randomX = Math.floor(Math.random() * 600);
var randomY = Math.floor(Math.random() * 600);
var randomDegree = Math.floor(Math.random() * 360);

(function() {
  var midX = 400,
    midY = 300,
    bounds = {
      top: 0,
      right: 600,
      bottom: 600,
      left: 0,
    },
    // Only one player for RL agent to control
    players = [
      new PB.player({
        x: randomX,
        y: randomY,
        degree: randomDegree,
        left: 37,
        right: 39,
        color: '#FF5EAA',
        name: 'RL Player',
        isComputer: false  // Will be controlled via WebSocket
      })
    ];

  function makeImages(images, callback) {
    var result = {},
      loads = 0,
      keys = Object.keys(images),
      num = keys.length,
      cb = function() {
        if (++loads >= num) callback(result);
      };

    for (var i = num; i--; ) {
      var key = keys[i],
        img = new Image();
      img.onload = cb;
      img.onerror = cb;
      img.src = images[key];
      result[key] = img;
    }
  }

  PB.store = {
    getItem: function(key) {
      if (localStorage) {
        var value = localStorage.getItem(key);
        return value;
      }
    },
    get: function(key) {
      if (localStorage) {
        var value = localStorage.getItem(key);
        if (!value) return;
        try {
          value = JSON.parse(value);
        } catch (e) {}
        return value;
      }
    },
    set: function(key, obj) {
      if (localStorage) {
        if (typeof obj === 'object') obj = JSON.stringify(obj);
        localStorage.setItem(key, obj);
      }
    },
  };

  makeImages(
    {
      bg: 'img/canvas.png',
      brush: 'img/brush.png',
      clean: 'img/clean.png',
      shadow: 'img/shadow.png',
    },
    init
  );

  function drawBackground() {
    var bgCanvas = document.getElementById('BG'),
      bgCtx = bgCanvas.getContext('2d');
    bgCanvas.width = bounds.right;
    bgCanvas.height = bounds.bottom;
    bgCtx.drawImage(PB.images.bg, 0, 0, bounds.right, bounds.bottom);
  }

  function init(images) {
    PB.keys = [];
    PB.images = images;
    
    // Initialize WebSocket communication for RL agent
    PB.initWebSocket();
    
    document.addEventListener('keydown', function(e) {
      e = e ? e : window.event;
      PB.keys[e.keyCode] = true;
      PB.keyHandler && PB.keyHandler(e.keyCode);
    });
    document.addEventListener('keyup', function(e) {
      e = e ? e : window.event;
      PB.keys[e.keyCode] = false;
    });
    
    drawBackground();
    PB.startGame(bounds, players);
  }
})();