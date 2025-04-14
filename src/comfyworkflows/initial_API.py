#This is an example that uses the websockets api to know when a prompt execution is done
#Once the prompt execution is done it downloads the images using the /history endpoint

import websocket
import uuid
import json
import urllib.request
import os
import sys
import time
import shutil
import random

# Server configuration
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# Paths
COMFYUI_OUTPUT = "C:\\ComfyUI_windows_portable_nvidia\\ComfyUI_windows_portable\\ComfyUI\\output"
TARGET_OUTPUT = "C:\\CODING\\VIBE\\VIBE_Forming\\output\\generated\\Models"
GENERATED_MESH_PATH = os.path.join(TARGET_OUTPUT, "initial_mesh.glb")

def queue_prompt(prompt):
    """Send a prompt to the ComfyUI server"""
    try:
        # Modify the workflow to prevent caching
        prompt["98"]["inputs"]["seed"] = random.randint(0, 999999999)  # Random seed for Hy3DGenerateMesh
        
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except Exception as e:
        print(f"Error queueing prompt: {str(e)}")
        sys.exit(1)

def get_history(prompt_id):
    """Get the execution history for a prompt"""
    try:
        with urllib.request.urlopen(f"http://{server_address}/history/{prompt_id}") as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        sys.exit(1)

def copy_mesh_to_target(comfyui_output_dir, target_dir):
    """Copy the latest generated mesh from ComfyUI output to target directory"""
    try:
        # Ensure target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Find the latest .glb file in ComfyUI output
        glb_files = [f for f in os.listdir(comfyui_output_dir) if f.endswith('.glb')]
        if not glb_files:
            print("No .glb files found in ComfyUI output directory")
            return False
            
        # Sort by modification time to get the latest
        latest_glb = max(glb_files, key=lambda x: os.path.getmtime(os.path.join(comfyui_output_dir, x)))
        
        # Copy to target location
        source_path = os.path.join(comfyui_output_dir, latest_glb)
        target_path = GENERATED_MESH_PATH
        
        shutil.copy2(source_path, target_path)
        print(f"Successfully copied mesh from {source_path} to {target_path}")
        return True
    except Exception as e:
        print(f"Error copying mesh: {e}")
        return False

def main():
    # Check if output directory exists
    if not os.path.exists(TARGET_OUTPUT):
        print(f"Creating output directory: {TARGET_OUTPUT}")
        os.makedirs(TARGET_OUTPUT, exist_ok=True)
    
    # Test write permissions
    try:
        test_file = os.path.join(TARGET_OUTPUT, "test_write.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print("Successfully verified write permissions")
    except Exception as e:
        print(f"Error: Cannot write to output directory: {str(e)}")
        sys.exit(1)
    
    # Get the absolute path to the JSON file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "initial.json")
    
    print(f"Looking for JSON file at: {json_path}")
    
    # Load the workflow JSON file
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        print("Successfully loaded workflow JSON")
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return
    
    # Create websocket connection
    ws = websocket.WebSocket()
    ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
    
    try:
        # Queue the prompt
        result = queue_prompt(workflow)
        prompt_id = result['prompt_id']
        print(f"Prompt queued with ID: {prompt_id}")
        
        # Wait for execution to complete
        execution_timeout = time.time() + 300  # 5 minutes timeout
        while time.time() < execution_timeout:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        print("Execution completed!")
                        break
                    elif data['node'] is not None:
                        print(f"Executing node: {data['node']}")
                elif message['type'] == 'execution_error':
                    print(f"Execution error: {message['data']}")
                    break
                elif message['type'] == 'progress':
                    print(f"Progress: {message['data']['value']}/{message['data']['max']}")
            else:
                continue  # Skip binary data (previews)
        
        # Get the execution history
        history = get_history(prompt_id)[prompt_id]
        print("Execution history:", json.dumps(history, indent=2))
        
        # Check for 3D mesh output and copy it to target location
        if '103' in history['outputs'] and 'model_file' in history['outputs']['103']:
            print("Mesh generation completed, copying to target location...")
            if copy_mesh_to_target(COMFYUI_OUTPUT, TARGET_OUTPUT):
                print("Mesh successfully copied to target location")
            else:
                print("Failed to copy mesh to target location")
        else:
            print("No mesh was generated in this execution")
        
    finally:
        ws.close()

if __name__ == "__main__":
    main()
