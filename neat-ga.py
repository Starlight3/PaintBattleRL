import numpy as np
import asyncio
import websockets
import json
import neat
import os
import pickle

# Environment and state setup
STATE_SIZE = 5
ACTION_SIZE = 3
BOUNDS = {"top": 0, "right": 800, "bottom": 600, "left": 0}
ACTIONS = ["LEFT", "RIGHT", "FORWARD"]

# Grid setup
GRID_ROWS = 30
GRID_COLS = 30
CELL_WIDTH = BOUNDS["right"] / GRID_COLS
CELL_HEIGHT = BOUNDS["bottom"] / GRID_ROWS

# Grid-based state processing
def process_state_grid(game_data, visited_cells):
    player = game_data["player"]
    x = player["x"]
    y = player["y"]

    # Convert position to grid cell
    grid_x = int(x // CELL_WIDTH)
    grid_y = int(y // CELL_HEIGHT)

    # Normalize grid position
    norm_x = grid_x / GRID_COLS
    norm_y = grid_y / GRID_ROWS

    degree = player["degree"] / 360.0
    can_draw = 1.0 if player["canDraw"] else 0.0

    visited_cells.add((grid_x, grid_y))
    coverage_ratio = len(visited_cells) / (GRID_ROWS * GRID_COLS)

    return [norm_x, norm_y, degree, can_draw, coverage_ratio]

# Evaluate a genome
async def evaluate_genome(genome, config, server_uri):
    net = neat.nn.FeedForwardNetwork.create(genome, config)
    visited_cells = set()

    try:
        async with websockets.connect(server_uri) as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                if data["event"] == "STATE_UPDATE":
                    state = process_state_grid(data, visited_cells)
                    output = net.activate(state)
                    action_index = int(np.argmax(output))
                    await websocket.send(json.dumps({"action": ACTIONS[action_index]}))

                elif data["event"] == "GAME_OVER":
                    # Fitness: number of unique cells visited (coverage)
                    return len(visited_cells) / (GRID_ROWS * GRID_COLS)

    except Exception as e:
        print(f"Error during evaluation: {e}")
        return 0.0

# NEAT evaluation wrapper
def eval_genomes(genomes, config):
    loop = asyncio.get_event_loop()
    for genome_id, genome in genomes:
        genome.fitness = loop.run_until_complete(
            evaluate_genome(genome, config, "ws://localhost:9080/agent-client")
        )

# Main NEAT training loop
def run_neat():
    config_path = os.path.join(os.path.dirname(__file__), "neat-config.txt")
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )

    # Resume from latest checkpoint if available
    latest = None
    for f in sorted(os.listdir(), reverse=True):
        if f.startswith("neat-checkpoint-"):
            latest = f
            break

    if latest:
        print(f"Resuming from checkpoint: {latest}")
        p = neat.Checkpointer.restore_checkpoint(latest)
    else:
        p = neat.Population(config)

    p.add_reporter(neat.StdOutReporter(True))
    p.add_reporter(neat.StatisticsReporter())
    p.add_reporter(neat.Checkpointer(generation_interval=1, filename_prefix='neat-checkpoint-'))

    winner = p.run(eval_genomes, 50)

    # Save the winning genome
    with open("best_genome_neat.pkl", "wb") as f:
        pickle.dump(winner, f)

# Run the best saved genome
def run_best_genome():
    config_path = os.path.join(os.path.dirname(__file__), "neat-config.txt")
    config = neat.Config(
        neat.DefaultGenome,
        neat.DefaultReproduction,
        neat.DefaultSpeciesSet,
        neat.DefaultStagnation,
        config_path
    )

    with open("best_genome_neat.pkl", "rb") as f:
        genome = pickle.load(f)
    net = neat.nn.FeedForwardNetwork.create(genome, config)

    visited_cells = set()

    async def play():
        async with websockets.connect("ws://localhost:9080/agent-client") as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                if data["event"] == "STATE_UPDATE":
                    state = process_state_grid(data, visited_cells)
                    output = net.activate(state)
                    action_index = int(np.argmax(output))
                    await websocket.send(json.dumps({"action": ACTIONS[action_index]}))

                elif data["event"] == "GAME_OVER":
                    print(f"Coverage (grid cells): {len(visited_cells)} out of {GRID_ROWS * GRID_COLS}")
                    print(f"Coverage ratio: {len(visited_cells) / (GRID_ROWS * GRID_COLS) * 100:.2f}%")
                    break

    asyncio.run(play())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_best_genome()
    else:
        run_neat()
