PB.FAST_MODE = true; // Enable fast mode for training

PB.startGame = function(bounds, players) {
  var canvas = document.getElementById('PB'),
    ctx = canvas.getContext('2d'),
    propCanvas = document.getElementById('Prop'),
    propCtx = propCanvas.getContext('2d'),
    pause = false,
    gameState = new PB.timer(),
    frameCounter = 0;

  // Shorter game duration for faster training
  const GAME_INTERVAL = PB.FAST_MODE ? 30 * 1000 : 90 * 1000;

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
    if (PB.FAST_MODE) {
      startGame();
      return;
    }
    
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
    // Use higher FPS in fast mode
    const fps = PB.FAST_MODE ? 10 : 30;
    gameState.setInterval(update, 1000/fps);
    gameState.setTimeout(endGame, GAME_INTERVAL);
  }

  function endGame() {
    gameState.stop();
    const result = getGameResult();
    propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
    
    // Display final score only in normal mode
    if (PB.FAST_MODE) {
      propCtx.font = '32px Verdana';
      propCtx.fillStyle = '#000';
      propCtx.fillText(`Coverage: ${result[0].percent}%`, bounds.right / 2 - 120, bounds.bottom / 2);
    }
    
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
      //draw image
      propCtx.drawImage(
        PB.images.shadow,
        x - player.radius,
        y - player.radius,
        player.radius * 2,
        player.radius * 2
      );
      propCtx.drawImage(
        player.drawing ? PB.images.brush : PB.images.clean,
        x - player.radius,
        y - player.radius - player.imgOffset,
        player.radius * 2,
        player.radius * 2
      );


      //draw heading direction line
      propCtx.beginPath();
      propCtx.moveTo(x, y);
      propCtx.lineTo(solved.x, solved.y);
      propCtx.stroke();
      //draw paint
      if (!player.canDraw()) continue;
      ctx.fillStyle = player.color;
      ctx.beginPath();
      ctx.arc(player.position.x | 0, player.position.y | 0, player.radius, 0, 180 * Math.PI, false);
      ctx.fill();
    }
  }

  // function drawDebug() {
  //   propCtx.fillStyle = '#f00';
  //   propCtx.font = '11px Verdana';

  //   for (var i = 0, l = gameState.moments.length; i < l; i++) {
  //     propCtx.fillText(gameState.moments[i].delta | 0, 10, i * 15 + 30);
  //   }
  // }

  function reshapeFlatArrayTo2D(flatArray, width) {
    const grid2D = [];
    for (let i = 0; i < flatArray.length; i += width) {
      grid2D.push(flatArray.slice(i, i + width));
    }
    return grid2D;
  }

  // function printGrid2D(grid2D) {
  //   for (const row of grid2D) {
  //     console.log(row.map(cell => cell.toString()).join(' '));
  //   }
  // }

  function imageDataToPlayerGridFromRgbaList(rgbaList, players, playerIndex, strideX, strideY, width, height) {
    const playerColor = hexToRgb(players[playerIndex].color);
    const result = [];

    for (let y = 0; y < height; y += strideY) {
      for (let x = 0; x < width; x += strideX) {
        const index = y * width + x;
        const rgba = rgbaList[index];

        if (!rgba || rgba[3] === 0 || isBlack(rgba)) {
          result.push(0); // unpainted
        } else if (getRgbDifference(playerColor, rgba.slice(0, 3)) < 30) {
          result.push(1); // painted by this player
        } else {
          result.push(2); // painted by others
        }
      }
    }

    return result;
  }

  function calculateCoverageFromFlatGrid(flatGrid) {
    let paintedByThisPlayer = 0;
    const totalPixels = flatGrid.length;

    for (let cell of flatGrid) {
      if (cell === 0) paintedByThisPlayer++;
    }

    return (paintedByThisPlayer / totalPixels) * 100;
  }
  let frameCount = 0;
  const frameSkip = 20;
  const strideX = 20;

  function update() {
    propCtx.clearRect(0, 0, bounds.right, bounds.bottom);
    updatePlayers();
    drawPlayers();
    // drawDebug();
    if(PB.sendGameState) {
      frameCount++;
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      
      const rgbaList = imageDataToRgbaList(imageData.data);
      const playerIndex = 0;
      //20 is the stride, to reduce the array size, to improve frame processing speed
      const flatGrid = imageDataToPlayerGridFromRgbaList(rgbaList, players, playerIndex, strideX, strideX, canvas.width, canvas.height);
      const grid2D = reshapeFlatArrayTo2D(flatGrid, Math.floor(canvas.width / 20));
      const coverage = calculateCoverageFromFlatGrid(flatGrid);
      
      PB.sendGameState({
        event: 'STATE_UPDATE',
        player: {
          x: players[playerIndex].position.x,
          y: players[playerIndex].position.y,
          degree: ((players[playerIndex].degree % 360) +360) % 360,
          canDraw: players[playerIndex].canDraw()
        },
        coverage:coverage, 
        canvas: grid2D
        });
    }
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

  function getRgbDifference([r1, g1, b1], [r2, g2, b2]) {
    return Math.sqrt(Math.pow(r2 - r1, 2) + Math.pow(g2 - g1, 2) + Math.pow(b2 - b1, 2));
  }

  function isBlack([r, g, b, a]) {
    return !r && !g && !b;
  }

  function getGameResult() {
    const imageData = ctx.getImageData(0, 0, bounds.right, bounds.bottom).data;
    const rgbList = imageDataToRgbaList(imageData);
    const playerColors = players.map(x => hexToRgb(x.color));
    const amountOfPixels = rgbList.length;
    const gameColors = rgbList.reduce((acc, cur) => {
      let playerColor;
      if (isBlack(cur)) {
        playerColor = rgbToHex(...cur);
      } else {
        const colorDiffs = playerColors.map(x => ({
          color: x,
          difference: getRgbDifference(x, cur),
        }));
        const leastDiffer = colorDiffs.sort((a, b) => a.difference - b.difference)[0].color;
        playerColor = rgbToHex(...leastDiffer);
      }
      if (acc[playerColor]) {
        acc[playerColor]++;
      } else {
        acc[playerColor] = 1;
      }
      return acc;
    }, {});
    const result = players.map(player => ({
      name: player.name,
      color: player.color,
      percent: Math.round((gameColors[player.color] * 100) / amountOfPixels),
    }));
    const highestScore = result.slice().sort((a, b) => b.percent - a.percent)[0].percent;
    result.forEach(x => {
      if (x.percent === highestScore) x.winner = true;
    });
    result.push({
      name: 'Total',
      percent: result.reduce((acc, cur) => acc + cur.percent, 0),
    });
    return result;
  }
};
