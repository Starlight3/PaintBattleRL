import os
import json
import csv
import asyncio
import websockets
import logging

# Constants
BEST_MODELS_DIR = "bestModels"
RESULT_CSV_PATH = "test_result_real_game.csv"
WEBSOCKET_URI = "ws://localhost:9080/agent-client" # Replace with your actual URI

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def evaluate_genome(websocket, genome):
    await websocket.recv()  # Wait for initial confirmation from server

    action_index = 0
    genome_length = len(genome)

    while True:
        action = genome[action_index % genome_length]
        await websocket.send(json.dumps({"action": action}))
        message = await websocket.recv()
        data = json.loads(message)

        if data.get("event") == "GAME_OVER":
            return data.get("coverage", 0.0)

        action_index += 1

async def evaluate_all_models():
    results = []

    async with websockets.connect(WEBSOCKET_URI) as websocket:
        for filename in os.listdir(BEST_MODELS_DIR):
            if filename.endswith(".json"):
                filepath = os.path.join(BEST_MODELS_DIR, filename)
                with open(filepath, "r") as f:
                    genome = json.load(f)

                logger.info(f"Evaluating genome from {filename}")
                coverage = await evaluate_genome(websocket, genome)
                results.append((filename, coverage))
                logger.info(f"{filename}: coverage = {coverage}")

                # Send reset command before next genome
                await websocket.send(json.dumps({"action": "RESET"}))
                await websocket.recv()  # Wait for acknowledgment/reset complete

    # Write results to CSV
    with open(RESULT_CSV_PATH, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["filename", "coverage"])
        writer.writerows(results)

    logger.info(f"Results written to {RESULT_CSV_PATH}")

# Entry point
if __name__ == "__main__":
    asyncio.run(evaluate_all_models())
