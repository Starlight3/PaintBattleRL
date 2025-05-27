import asyncio
import websockets
import json
import logging
import random
import time
# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("websocket-battle-painters")

import numpy as np
import math

class GameState:
    def __init__(self, canvas_width=800, canvas_height=600, stride=20, max_steps=1800):
        # Grid resolution
        self.strideX = stride
        self.strideY = stride

        # Canvas dimensions and resolution
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.grid_cols = canvas_width // stride
        self.grid_rows = canvas_height // stride

        # Full-resolution paint canvas (True = painted)
        self.canvas = np.zeros((self.canvas_height, self.canvas_width), dtype=bool)

        # Player settings
        self.player_radius = 25
        self.player_speed = 20
        self.turn_speed = 30
        self.player = {
            "x": canvas_width // 2,
            "y": canvas_height // 2,
            "degree": 90,
            "canDraw": True
        }

        # Game state
        self.steps = 0
        self.max_steps = max_steps
        self.coverage = 0.0

    def apply_action(self, action):
        if action == "LEFT":
            self.player["degree"] = (self.player["degree"] - self.turn_speed) % 360
        elif action == "RIGHT":
            self.player["degree"] = (self.player["degree"] + self.turn_speed) % 360
        elif action == "FORWARD":
            pass  # Movement always applied below
        self.step()

    def step(self):
        self.move_player()
        self.paint_canvas()
        self.coverage = self.calculate_coverage()
        self.steps += 1

    def move_player(self):
        rad = math.radians(self.player["degree"])
        dx = math.cos(rad) * self.player_speed
        dy = math.sin(rad) * self.player_speed

        new_x = self.player["x"] + dx
        new_y = self.player["y"] + dy

        # Clamp within bounds considering radius
        r = self.player_radius
        new_x = min(max(r, new_x), self.canvas_width - r)
        new_y = min(max(r, new_y), self.canvas_height - r)

        self.player["x"] = new_x
        self.player["y"] = new_y

    def paint_canvas(self):
        if not self.player["canDraw"]:
            return

        px, py = int(self.player["x"]), int(self.player["y"])
        r = self.player_radius

        min_x = max(0, px - r)
        max_x = min(self.canvas_width, px + r + 1)
        min_y = max(0, py - r)
        max_y = min(self.canvas_height, py + r + 1)

        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                dx = x - px
                dy = y - py
                if dx * dx + dy * dy <= r * r:
                    self.canvas[y, x] = True

    def calculate_coverage(self):
        return (np.sum(self.canvas) / self.canvas.size) * 100.0
    
    def print_grid(self):
        grid = self.generate_grid_from_canvas()
        for row in grid:
            print(" ".join(str(cell) for cell in row))

    def generate_grid_from_canvas(self):
        """Downsample the full-resolution canvas into a grid (0 = painted, 1 = unpainted)"""
        grid = []
        for gy in range(0, self.canvas_height, self.strideY):
            row = []
            for gx in range(0, self.canvas_width, self.strideX):
                if self.canvas[gy, gx]:
                    row.append(0)  # painted by this player
                else:
                    row.append(1)  # unpainted
                    # Add logic for painted-by-others = 2 if needed
            grid.append(row)
        return grid

    def get_state_update(self):
        return {
            "event": "STATE_UPDATE",
            "player": {
                "x": self.player["x"],
                "y": self.player["y"],
                "degree": int(self.player["degree"] % 360),
                "canDraw": self.player["canDraw"]
            },
            "coverage": self.coverage,
            "strideX": self.strideX,
            "strideY": self.strideY,
            "grid": self.generate_grid_from_canvas()
        }

    def is_game_over(self):
        return self.steps >= self.max_steps

    def get_game_over(self):
        return {
            "event": "GAME_OVER",
            "coverage": self.coverage
        }



async def agent_handler(websocket):
    logger.info(f"Agent connected from {websocket.remote_address}")
    game = GameState()
    await websocket.send(json.dumps(game.get_state_update()))
    episodes_completed = 0

    try:
        while True:
            message = await websocket.recv()
            logger.debug(f"Received: {message}")
            data = json.loads(message)
            action = data.get("action")

            if action == "RESET":
                logger.info("Reset requested by agent")
                game = GameState()
                await websocket.send(json.dumps(game.get_state_update()))
                continue

            game.apply_action(action)

            if game.is_game_over():
                game.print_grid()
                #time.sleep(0.01)
                print("COVERAGE :",game.calculate_coverage())
                await websocket.send(json.dumps(game.get_game_over()))
                episodes_completed += 1

                # Optional: print speed stats
                if episodes_completed % 10 == 0:
                    logger.info(f"Episodes completed: {episodes_completed}")
            else:
                await websocket.send(json.dumps(game.get_state_update()))

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Connection closed: {e}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


async def start_server():
    async def main_handler(websocket):
        path = websocket.request.path
        if path == "/agent-client":
            await agent_handler(websocket)
        else:
            logger.warning(f"Rejected connection on invalid path: {path}")
            await websocket.close(1008, "Invalid path")

    logger.info("Starting server at ws://localhost:9080/agent-client")
    return await websockets.serve(main_handler, "localhost", 9080)


async def main():
    server = await start_server()
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shut down")
