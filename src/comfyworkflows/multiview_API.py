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
import socket
import traceback

# Server configuration
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# Paths
COMFYUI_OUTPUT = "C:\\ComfyUI_windows_portable_nvidia\\ComfyUI_windows_portable\\ComfyUI\\output"
TARGET_OUTPUT = "C:\\CODING\\VIBE\\VIBE_Forming\\output\\generated\\Models"

def check_comfyui_server():
    """Check if the ComfyUI server is running"""
    try:
        host, port = server_address.split(':')
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        if result == 0:
            print(f"ComfyUI server is running at {server_address}")
            return True
        else:
            print(f"ERROR: ComfyUI server is not running at {server_address}")
            return False
    except Exception as e:
        print(f"Error checking ComfyUI server: {str(e)}")
        return False

def queue_prompt(prompt):
    """Send a prompt to the ComfyUI server"""
    try:
        # Modify the workflow to prevent caching
        if "45" in prompt and "inputs" in prompt["45"]:
            prompt["45"]["inputs"]["seed"] = random.randint(0, 999999999)  # Random seed for KSampler
        else:
            print("Warning: Node 45 not found for setting random seed")
        
        # Ensure consistent filename for export nodes without timestamps
        if "76" in prompt and "inputs" in prompt["76"]:  # Hy3DExportMesh node
            if "filename_prefix" in prompt["76"]["inputs"]:
                prompt["76"]["inputs"]["filename_prefix"] = "model"  # Consistent name for 3D model
                
            # Make sure overwrite mode is enabled if available
            if "overwrite_mode" in prompt["76"]["inputs"]:
                prompt["76"]["inputs"]["overwrite_mode"] = "true"
                print("Enabled overwrite mode for 3D model export node")
        else:
            print("Warning: Node 76 (3D export node) not found in workflow")
        
        # Check other save nodes and set overwrite mode
        save_nodes = ['33', '63', '82', '64', '83', '93', '76']
        for node_id in save_nodes:
            if node_id in prompt and 'inputs' in prompt[node_id]:
                if 'output_path' in prompt[node_id]['inputs']:
                    prompt[node_id]['inputs']['output_path'] = TARGET_OUTPUT
                    print(f"Set node {node_id} output path to: {TARGET_OUTPUT}")
                
                # Make sure overwrite mode is enabled
                if 'overwrite_mode' in prompt[node_id]['inputs']:
                    prompt[node_id]['inputs']['overwrite_mode'] = "true"
                    print(f"Enabled overwrite mode for node {node_id}")
        
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        
        # Print request size for debugging
        print(f"Sending prompt request (size: {len(data)} bytes)")
        
        req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
        req.add_header('Content-Type', 'application/json')
        
        try:
            response = urllib.request.urlopen(req, timeout=10)
            result = json.loads(response.read())
            print(f"Prompt queued successfully: {result}")
            return result
        except urllib.error.URLError as url_error:
            print(f"URLError: {str(url_error)}")
            print("Please ensure ComfyUI is running and accessible.")
            sys.exit(1)
        except Exception as request_error:
            print(f"Error during HTTP request: {str(request_error)}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error preparing prompt: {str(e)}")
        traceback.print_exc()
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
        target_path = os.path.join(target_dir, "current_mesh.glb")
        
        shutil.copy2(source_path, target_path)
        print(f"Successfully copied mesh from {source_path} to {target_path}")
        return True
    except Exception as e:
        print(f"Error copying mesh: {str(e)}")
        return False

def main():
    # Check if ComfyUI is running
    if not check_comfyui_server():
        print("ERROR: ComfyUI server is not running. Please start ComfyUI first.")
        sys.exit(1)
        
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
    json_path = os.path.join(current_dir, "VIBEMultiView.json")
    
    print(f"Looking for JSON file at: {json_path}")
    
    # Load the workflow JSON file
    try:
        if not os.path.exists(json_path):
            print(f"ERROR: Workflow JSON file not found at: {json_path}")
            sys.exit(1)
            
        with open(json_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        print("Successfully loaded workflow JSON")
        
        # Print key nodes for debugging
        print(f"Workflow has {len(workflow)} nodes")
        important_nodes = ['76', '84']  # 3D mesh export related nodes
        for node in important_nodes:
            if node in workflow:
                print(f"Found node {node}: {workflow[node]['class_type']}")
            else:
                print(f"WARNING: Node {node} not found in workflow")
                
    except json.JSONDecodeError as json_error:
        print(f"JSON decode error: {json_error}")
        print("The workflow file exists but contains invalid JSON")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        traceback.print_exc()
        sys.exit(1)
    
    # Create websocket connection
    try:
        ws = websocket.WebSocket()
        ws.connect(f"ws://{server_address}/ws?clientId={client_id}")
        print("Successfully connected to ComfyUI websocket")
    except Exception as ws_error:
        print(f"Error connecting to websocket: {str(ws_error)}")
        print("Please ensure ComfyUI is running and websocket server is enabled")
        sys.exit(1)
    
    try:
        # Queue the prompt
        result = queue_prompt(workflow)
        prompt_id = result['prompt_id']
        print(f"Prompt queued with ID: {prompt_id}")
        
        # Wait for execution to complete
        execution_timeout = time.time() + 600  # 10 minutes timeout (increased from 5)
        execution_started = False
        
        while time.time() < execution_timeout:
            try:
                out = ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        execution_started = True
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            print("Execution completed!")
                            break
                        elif data['node'] is not None:
                            print(f"Executing node: {data['node']}")
                    elif message['type'] == 'execution_error':
                        print(f"Execution error: {message['data']}")
                        print("This is usually caused by a configuration issue in the workflow")
                        break
                    elif message['type'] == 'progress':
                        execution_started = True
                        print(f"Progress: {message['data']['value']}/{message['data']['max']}")
                else:
                    # Binary data (preview image)
                    continue
            except websocket.WebSocketTimeoutException:
                print("Websocket timeout - retrying...")
                continue
            except Exception as recv_error:
                print(f"Error receiving websocket message: {str(recv_error)}")
                break
                
        if not execution_started:
            print("Execution never started. ComfyUI might be busy or unresponsive.")
            sys.exit(1)
        
        # Get the execution history
        try:
            history = get_history(prompt_id)
            if prompt_id not in history:
                print(f"Error: Prompt ID {prompt_id} not found in execution history")
                sys.exit(1)
                
            history_data = history[prompt_id]
            print(f"Execution status: {history_data.get('status', 'unknown')}")
            
            # Check for outputs
            if 'outputs' not in history_data or not history_data['outputs']:
                print("Error: No outputs found in execution history")
                sys.exit(1)
                
            outputs = history_data['outputs']
            print(f"Found {len(outputs)} output nodes")
            
            # Check for 3D mesh output and copy it to target location
            if '84' in outputs and 'model_file' in outputs['84']:
                model_file = outputs['84']['model_file']
                print(f"Mesh generation completed, file: {model_file}")
                
                if copy_mesh_to_target(COMFYUI_OUTPUT, TARGET_OUTPUT):
                    print("Mesh successfully copied to target location")
                else:
                    print("Failed to copy mesh to target location")
                    sys.exit(1)
            else:
                print("No mesh was generated in this execution")
                print("Available output nodes:", list(outputs.keys()))
                
                # Check if any GLB file was generated despite missing node 84
                if copy_mesh_to_target(COMFYUI_OUTPUT, TARGET_OUTPUT):
                    print("Found and copied a mesh file anyway")
                else:
                    print("No mesh files found")
                    sys.exit(1)
                    
        except Exception as history_error:
            print(f"Error processing execution history: {str(history_error)}")
            traceback.print_exc()
            sys.exit(1)
            
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            ws.close()
        except:
            pass

if __name__ == "__main__":
    try:
        main()
        print("Script completed successfully")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: Unhandled exception: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
