import numpy as np
import random
import websockets
import asyncio
import json
from itertools import product
import os
import csv
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
server_uri="ws://localhost:9080/agent-client"
action_map = {0: "LEFT", 1: "RIGHT", 2: "FORWARD"}
def generate_all_keys(angles):
    angles = [i * (360 // angles) for i in range(angles)]
    quads = list(product([0, 1], repeat=4))
    return [(q1, q2, q3, q4, angle) for (q1, q2, q3, q4) in quads for angle in angles]

def build_action_table(genome,angles):
    keys = generate_all_keys(angles)
    if len(genome) != len(keys):
        raise ValueError("Genome length mismatch.")
    return dict(zip(keys, genome))
def snap_degree_to_nearest_sector(degree, angles):
    parts =angles
    return round(degree / (360 / parts)) * (360 // parts) % 360

def normalise_quads_multi_max( quad1, quad2, quad3, quad4):
    quads = [quad1, quad2, quad3, quad4]
    max_val = max(quads)
    return tuple(1 if q == max_val else 0 for q in quads)

def convertGrid(grid, x, y):
    q1 = q2 = q3 = q4 = 0
    for i in range(len(grid)):
        for j in range(len(grid[i])):
            if i < y and j < x: q1 += grid[i][j]
            elif i < y and j >= x: q2 += grid[i][j]
            elif i >= y and j < x: q3 += grid[i][j]
            elif i >= y and j >= x: q4 += grid[i][j]
    return normalise_quads_multi_max(q1, q2, q3, q4)

def load_genome(population_file, angles):
    if os.path.exists(population_file):
        with open(population_file, "r") as f:
            population = json.load(f)
            genome = population[0]["genome"]
            action_table = build_action_table(genome, angles)
            return action_table
    else:
        print ("Error: Population file not found")
        return None


async def run_best():
    angles = 8
    action_table = load_genome("genome_test.json", angles)


    print(action_table)
    async with websockets.connect(server_uri) as websocket:
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data["event"] == "STATE_UPDATE":
                px, py = data["player"]["x"], data["player"]["y"]
                degree = data["player"]["degree"]
                strideX = data["strideX"]
                strideY = data["strideY"]
                grid = data["grid"]

                quads = convertGrid(grid, int(px / strideX), int(py / strideY))
                key = (*quads, snap_degree_to_nearest_sector(degree, angles))
                decision = action_table.get(key, 2)
                await websocket.send(json.dumps({"action": action_map.get(decision)}))
            elif data["event"] == "GAME_OVER":
                fitness = data["coverage"]
                print (fitness)
                return


if __name__ == "__main__":
    asyncio.run(run_best())