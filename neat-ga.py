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

# Process state with 5 features (no dx, dy)
def process_state_5(game_data):
    player = game_data["player"]
    x = player["x"] / BOUNDS["right"]
    y = player["y"] / BOUNDS["bottom"]
    degree = player["degree"] / 360.0
    can_draw = 1.0 if player["canDraw"] else 0.0
    coverage = game_data["coverage"] / 100.0
    return [x, y, degree, can_draw, coverage]

# Evaluate a genome
async def evaluate_genome(genome, config, server_uri):
    net = neat.nn.FeedForwardNetwork.create(genome, config)
    try:
        async with websockets.connect(server_uri) as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data["event"] == "STATE_UPDATE" or data["event"] == "INITIAL_STATE":
                    state = process_state_5(data)
                    output = net.activate(state)
                    action_index = int(np.argmax(output))
                    await websocket.send(json.dumps({"action": ACTIONS[action_index]}))
                elif data["event"] == "GAME_OVER":
                    return data["coverage"]
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

    winner = p.run(eval_genomes, 50000)

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

    async def play():
        async with websockets.connect("ws://localhost:9080/agent-client") as websocket:
            await websocket.send(json.dumps({"action": "RESET"}))
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                if data["event"] == "STATE_UPDATE" or data["event"] == "INITIAL_STATE":
                    state = process_state_5(data)
                    output = net.activate(state)
                    action_index = int(np.argmax(output))
                    await websocket.send(json.dumps({"action": ACTIONS[action_index]}))
                elif data["event"] == "GAME_OVER":
                    print(f"Coverage: {data['coverage']}%")
                    break

    asyncio.run(play())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_best_genome()
    else:
        run_neat()
