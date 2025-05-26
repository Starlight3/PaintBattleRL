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
    async def game_loop(self):
        try:
            async with websockets.connect(self.server_uri) as websocket:
                while not self.done:
                    message = await websocket.recv()
                    game_data = json.loads(message)
                    if game_data["event"] == "STATE_UPDATE":
                        print(self.counter)
                        self.counter=self.counter+1
                        if self.counter%100 < 50:
                            await websocket.send(json.dumps({"action": "LEFT"}))
                        else:
                            await websocket.send(json.dumps({"action": "RIGHT"}))
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