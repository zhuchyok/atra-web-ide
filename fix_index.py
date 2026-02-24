import os
import json
import safetensors.torch

base_path = '/Users/bikos/Documents/atra-web-ide/training_data/fused_model_dequantized'
index_path = os.path.join(base_path, 'model.safetensors.index.json')

files = sorted([f for f in os.listdir(base_path) if f.endswith('.safetensors')])
weight_map = {}
total_size = 0

for fname in files:
    file_path = os.path.join(base_path, fname)
    print(f"Processing {fname}...")
    with safetensors.torch.safe_open(file_path, framework="pt") as f:
        for key in f.keys():
            weight_map[key] = fname
    total_size += os.path.getsize(file_path)

new_index = {
    "metadata": {
        "total_size": total_size
    },
    "weight_map": weight_map
}

with open(index_path, 'w') as f:
    json.dump(new_index, f, indent=4)

print(f"Fixed index saved to {index_path}")
print(f"Total tensors indexed: {len(weight_map)}")
