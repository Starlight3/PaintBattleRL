PB.startGame = function(bounds, players) {
  var canvas = document.getElementById('PB'),
    ctx = canvas.getContext('2d'),
    propCanvas = document.getElementById('Prop'),
    propCtx = propCanvas.getContext('2d'),
    pause = false,
    gameState = new PB.timer();

  const GAME_INTERVAL = 90 * 1000; // 90 seconds game duration

  init();
  function init() {
    canvas.width = bounds.right;
    canvas.height = bounds.bottom;
    propCanvas.width = bounds.right;
    propCanvas.height = bounds.bottom;
    countdown();

    PB.keyHandler = function(key) {
      const space = 32;
      if (key === space) {
        if (pause) gameState.start();
        else gameState.stop();
        pause = !pause;
      }
    };
  }

  function countdown() {
    let time = 3;
    const x = bounds.right / 2 - 70;
    const y = bounds.bottom / 2 + 70;
    propCtx.font = 'bold 210px Verdana';
    propCtx.fillStyle = 'lightblue';
    propCtx.strokeStyle = 'blue';

    propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
    drawPlayers();
    propCtx.fillText(time, x, y);
    propCtx.strokeText(time--, x, y);

    const timer = gameState.setInterval(function() {
      if (time) {
        propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
        drawPlayers();
        propCtx.fillText(time, x, y);
        propCtx.strokeText(time--, x, y);
      } else {
        gameState.clearTimeout(timer);
        startGame();
      }
    }, 1000);
  }

  function startGame() {
    gameState.setInterval(update, 1000/30); // Update at 30fps
    gameState.setTimeout(endGame, GAME_INTERVAL);
  }

  function endGame() {
    gameState.stop();
    const result = getGameResult();
    propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
    
    // Display final score
    propCtx.font = '32px Verdana';
    propCtx.fillStyle = '#000';
    propCtx.fillText(`Coverage: ${result[0].percent}%`, bounds.right / 2 - 120, bounds.bottom / 2);
    
    // Send final result to RL agent
    if (PB.sendGameState) {
      PB.sendGameState({
        event: 'GAME_OVER',
        coverage: result[0].percent
      });
    }
  }

  function updatePlayers() {
    for (var i = players.length; i--; ) {
      var player = players[i];
      player.move(gameState);
      player.restrict(bounds);
    }
  }

  function drawPlayers() {
    for (var i = players.length; i--; ) {
      var player = players[i],
        solved = player.resolve(player.radius),
        x = player.position.x | 0,
        y = player.position.y | 0;
      
      // Draw shadow
      propCtx.drawImage(
        PB.images.shadow,
        x - player.radius,
        y - player.radius,
        player.radius * 2,
        player.radius * 2
      );
      
      // Draw player
      propCtx.drawImage(
        player.drawing ? PB.images.brush : PB.images.clean,
        x - player.radius,
        y - player.radius - player.imgOffset,
        player.radius * 2,
        player.radius * 2
      );

      // Draw heading direction line
      propCtx.beginPath();
      propCtx.moveTo(x, y);
      propCtx.lineTo(solved.x, solved.y);
      propCtx.stroke();
      
      // Draw paint
      if (player.canDraw()) {
        ctx.fillStyle = player.color;
        ctx.beginPath();
        ctx.arc(player.position.x | 0, player.position.y | 0, player.radius, 0, 180 * Math.PI, false);
        ctx.fill();
      }
    }
  }

  function update() {
    propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
    updatePlayers();
    drawPlayers();
    
    // Send game state to RL agent
    if (PB.sendGameState) {
      const player = players[0];
      const imageData = ctx.getImageData(0, 0, bounds.right, bounds.bottom);
      
      // Calculate current coverage
      const coverage = calculateCoverage(imageData);
      
      // Send minimal state information (position, direction, coverage)
      PB.sendGameState({
        event: 'STATE_UPDATE',
        player: {
          x: player.position.x,
          y: player.position.y,
          degree: player.degree,
          canDraw: player.canDraw()
        },
        coverage: coverage
      });
    }
  }

  function calculateCoverage(imageData) {
    const data = imageData.data;
    let paintedPixels = 0;
    const totalPixels = data.length / 4;
    
    // Count non-transparent pixels (painted areas)
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] > 0) {
        paintedPixels++;
      }
    }
    
    return (paintedPixels / totalPixels) * 100;
  }

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

  function isBlack([r, g, b, a]) {
    return !r && !g && !b;
  }

  function getGameResult() {
    const imageData = ctx.getImageData(0, 0, bounds.right, bounds.bottom).data;
    const rgbList = imageDataToRgbaList(imageData);
    const playerColors = players.map(x => hexToRgb(x.color));
    const amountOfPixels = rgbList.length;
    
    // Calculate painted pixels
    let paintedPixels = 0;
    for (let i = 0; i < rgbList.length; i++) {
      if (!isBlack(rgbList[i])) {
        paintedPixels++;
      }
    }
    
    // Calculate percentage
    const percent = Math.round((paintedPixels * 100) / amountOfPixels);
    
    return [{
      name: players[0].name,
      color: players[0].color,
      percent: percent
    }];
  }
};