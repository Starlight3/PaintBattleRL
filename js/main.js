(function() {
  var midX = 400,
    midY = 300,
    bounds = {
      top: 0,
      right: 800,
      bottom: 600,
      left: 0,
    },
    // Only one player for RL agent to control
    players = [
      new PB.player({
        x: midX,
        y: midY,
        degree: 225,
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

  function drawGrid(ctx, width, height, gridSize) {
    ctx.strokeStyle = '#cccccc'; // Light gray color for grid lines
    ctx.lineWidth = 1;

    // Draw vertical lines
    for (let x = 0; x <= width; x += gridSize) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
    }

    // Draw horizontal lines
    for (let y = 0; y <= height; y += gridSize) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
    }
  }

  function drawBackground() {
    var bgCanvas = document.getElementById('BG'),
      bgCtx = bgCanvas.getContext('2d');
    bgCanvas.width = bounds.right;
    bgCanvas.height = bounds.bottom;
    bgCtx.drawImage(PB.images.bg, 0, 0, bounds.right, bounds.bottom);

    // Draw grid lines
    drawGrid(bgCtx, bounds.right, bounds.bottom, 30); // Adjust grid size if needed
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