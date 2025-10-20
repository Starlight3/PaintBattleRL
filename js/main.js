﻿(function() {
  var midX = 300,
    midY = 300,
    bounds = {
      top: 0,
      right: 600,
      bottom: 600,
      left: 0,
    },
    // 1 RL agent player + 3 computer players all starting in square formation
    players = [
      // RL Agent controlled player (top-left)
      new PB.player({
        x: midX - 50,
        y: midY - 50,
        degree: 225,
        left: 37,
        right: 39,
        color: '#FF5EAA',
        name: 'RL Player',
        isComputer: false  // Will be controlled via WebSocket
      }),
      // Computer player 1 (top-right)
      new PB.player({
        x: midX + 50,
        y: midY - 50,
        degree: 315,
        left: 65,
        right: 68,
        color: '#299EFE',
        name: 'Player 2',
        isComputer: true,
      }),
      // Computer player 2 (bottom-left)
      new PB.player({
        x: midX - 50,
        y: midY + 50,
        degree: 135,
        left: 74,
        right: 76,
        color: '#FDBC56',
        name: 'Player 3',
        isComputer: true,
      }),
      // Computer player 3 (bottom-right)
      new PB.player({
        x: midX + 50,
        y: midY + 50,
        degree: 45,
        left: 100,
        right: 102,
        color: '#67DB66',
        name: 'Player 4',
        isComputer: true,
      }),
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