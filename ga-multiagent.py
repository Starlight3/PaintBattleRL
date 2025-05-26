# Updated GA-based BattlePainter Agent with fitness penalties instead of random actions
import numpy as np
import random
import websockets
import asyncio
import json
class BattlePainterGA:
    def __init__(self, server_uri="ws://localhost:9080/agent-client"):
        self.server_uri = server_uri
        self.done = False
        self.counter = 0
    def process_state(self, game_data):
        if game_data["event"] == "STATE_UPDATE":
            return None
        return None
    def convertGrid(self, grid, x, y):
        quad1 = 0
        quad2 = 0
        quad3 = 0
        quad4 = 0
        print("x :", x," y:", y)
        #print(grid)
        for i in range(len(grid)):
            for j in range(len(grid[i])):
                if i< y and j<x:
                    quad1 += grid[i][j]
                elif i< y and j>=x:
                    quad2 += grid[i][j]
                elif i>= y and j<x:
                    quad3 += grid[i][j]
                elif i>= y and j>=x:
                    quad4 += grid[i][j]
        
        print(quad1," ", quad2," ", quad3," ",quad4)
    async def game_loop(self):
        try:
            async with websockets.connect(self.server_uri) as websocket:
                while not self.done:
                    message = await websocket.recv()
                    game_data = json.loads(message)
                    if game_data["event"] == "STATE_UPDATE":
                        player_data = game_data["player"]
                        x = player_data["x"]
                        y = player_data["y"]
                        degree = player_data["degree"]
                        strideX = game_data["strideX"]
                        strideY = game_data["strideY"]
                        grid = game_data["grid"]
                        self.convertGrid(grid, int(x/strideX),int(y/strideY))
                        #self.counter=self.counter+1
                        #if self.counter%100 < 50:
                        #    await websocket.send(json.dumps({"action": "LEFT"}))
                        #else:
                        #    await websocket.send(json.dumps({"action": "RIGHT"}))
                    elif game_data["event"] == "GAME_OVER":
                        self.done = True
                        await websocket.send(json.dumps({"action": "RESET"}))
        except Exception as e:
            print(e)
            await asyncio.sleep(1)
    def run(self):
        asyncio.run(self.game_loop())
if __name__ == "__main__":
    agent = BattlePainterGA()
    agent.run()