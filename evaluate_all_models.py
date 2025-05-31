import os
import torch
import asyncio
import websockets
import json
import csv
import numpy as np
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class GAAgentNN(nn.Module):
    def __init__(self, state_size, action_size):
        super(GAAgentNN, self).__init__()
        self.fc1 = nn.Linear(state_size, 24)
        self.fc2 = nn.Linear(24, 24)
        self.fc3 = nn.Linear(24, action_size)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)

def get_flat_weights(model):
    return torch.cat([p.data.view(-1) for p in model.parameters()])

def set_flat_weights(model, flat):
    pointer = 0
    for param in model.parameters():
        numel = param.numel()
        param.data.copy_(flat[pointer:pointer + numel].view(param.size()))
        pointer += numel

def process_state(game_data, bounds):
    player = game_data["player"]
    x = player["x"] / bounds["right"]
    y = player["y"] / bounds["bottom"]
    degree = player["degree"] / 360.0
    coverage = game_data["coverage"] / 100.0
    return np.array([x, y, degree, coverage], dtype=np.float32)

def select_action(model, state):
    state_tensor = torch.tensor(state, dtype=torch.float32).unsqueeze(0).to(device)
    with torch.no_grad():
        q_values = model(state_tensor)
    return torch.argmax(q_values).item()
async def run_all_models(models_dir="results/models", output_csv="test_result_real_game.csv"):
    state_size = 4
    action_size = 3
    server_uri = "ws://localhost:9080/agent-client"
    bounds = {"top": 0, "right": 800, "bottom": 600, "left": 0}

    model = GAAgentNN(state_size, action_size).to(device)

    model_files = sorted([f for f in os.listdir(models_dir) if f.endswith(".pt")])

    # Open CSV for writing
    with open(output_csv, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["model_file", "coverage"])

        for model_file in model_files:
            path = os.path.join(models_dir, model_file)
            weights = torch.load(path)
            set_flat_weights(model, weights)

            print(f"\nEvaluating model: {model_file}")

            try:
                async with websockets.connect(server_uri) as websocket:
                    while True:
                        msg = await websocket.recv()
                        data = json.loads(msg)

                        if data["event"] == "STATE_UPDATE":
                            state = process_state(data, bounds)
                            action_index = select_action(model, state)
                            action = ["LEFT", "RIGHT", "FORWARD"][action_index]
                            await websocket.send(json.dumps({"action": action}))

                        elif data["event"] == "GAME_OVER":
                            coverage = data["coverage"]
                            print(f"Coverage for {model_file}: {coverage}%")
                            writer.writerow([model_file, coverage])
                            await websocket.send(json.dumps({"action": "RESET"}))
                            break

            except Exception as e:
                print(f"Failed to evaluate {model_file}: {e}")
                writer.writerow([model_file, "ERROR"])
if __name__ == "__main__":
    asyncio.run(run_all_models())
