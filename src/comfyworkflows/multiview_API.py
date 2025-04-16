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
        # Update image paths and force reload
        image_dir = "C:\\CODING\\VIBE\\VIBE_Forming\\input\\COMFYINPUTS\\blenderRender"
        image_nodes = {
            "153": "front.png",  # Front view
            "146": "left.png",   # Left view
            "151": "right.png",  # Right view
            "147": "back.png"    # Back view
        }
        
        # Add timestamp to ensure images are reloaded
        timestamp = int(time.time())
        
        # Update all image nodes with correct paths and force reload
        for node_id, filename in image_nodes.items():
            if node_id in prompt and "inputs" in prompt[node_id]:
                # Check if file exists
                file_path = os.path.join(image_dir, filename)
                if os.path.exists(file_path):
                    prompt[node_id]["inputs"]["image"] = file_path
                    
                    # Add or update reload parameters to force fresh load
                    if "reload_mode" in prompt[node_id]["inputs"]:
                        prompt[node_id]["inputs"]["reload_mode"] = f"always-{timestamp}"
                    elif "force_reload" in prompt[node_id]["inputs"]:
                        prompt[node_id]["inputs"]["force_reload"] = True
                    
                    print(f"Set node {node_id} to load {file_path} with reload enabled")
                else:
                    print(f"WARNING: Image not found at {file_path}")
        
        # Define consistent KSampler node IDs in all the workflows
        # These are the node IDs for the MultiViewFINAL1.json workflow
        sampler_nodes = {
            "3": {"seed": random.randint(0, 999999999), "steps": 8, "cfg": 2.2},  
            "35": {"seed": random.randint(0, 999999999), "steps": 8, "cfg": 2.2},
            "147": {"seed": random.randint(0, 999999999), "steps": 8, "cfg": 2.2}
        }
        
        # Apply consistent settings to all KSampler nodes
        for node_id, settings in sampler_nodes.items():
            if node_id in prompt and "inputs" in prompt[node_id]:
                # Apply all settings
                for param, value in settings.items():
                    prompt[node_id]["inputs"][param] = value
                print(f"Set {len(settings)} parameters for KSampler node {node_id}")
                
                # Ensure scheduler is consistent
                if "scheduler" in prompt[node_id]["inputs"]:
                    prompt[node_id]["inputs"]["scheduler"] = "simple"
                    
                # Ensure sampler_name is consistent
                if "sampler_name" in prompt[node_id]["inputs"]:
                    prompt[node_id]["inputs"]["sampler_name"] = "lcm"
        
        # Ensure consistent filename for export nodes without timestamps
        if "123" in prompt and "inputs" in prompt["123"]:  # Hy3DExportMesh node
            # Set a consistent model name
            if "filename_prefix" in prompt["123"]["inputs"]:
                prompt["123"]["inputs"]["filename_prefix"] = "model"  # Consistent name for 3D model
                print("Set consistent filename prefix for 3D model export node")
                
            # Make sure file_format is set to glb
            if "file_format" in prompt["123"]["inputs"]:
                prompt["123"]["inputs"]["file_format"] = "glb"
                print("Set file format to glb for 3D model export node")
                
            # Set output path if needed
            if "output_path" in prompt["123"]["inputs"]:
                # Only set if it's empty or invalid
                current_path = prompt["123"]["inputs"]["output_path"]
                if not current_path or not os.path.exists(current_path):
                    prompt["123"]["inputs"]["output_path"] = TARGET_OUTPUT
                    print(f"Set output path to {TARGET_OUTPUT} for 3D model export node")
                
            # Ensure save_file is enabled
            prompt["123"]["inputs"]["save_file"] = True
            print("Enabled save_file for 3D model export node")
        else:
            print("Warning: Node 123 (3D export node) not found in workflow")
        
        # Force reload of the text file by updating dictionary_name parameter
        prompt_txt_path = os.path.join("C:\\CODING\\VIBE\\VIBE_Forming\\input\\COMFYINPUTS\\textOptions", "prompt.txt")
        
        if "102" in prompt and "inputs" in prompt["102"]:  # Load Text File node
            if "file_path" in prompt["102"]["inputs"] and os.path.exists(prompt_txt_path):
                try:
                    # Add timestamp to dictionary_name to force reload
                    timestamp = int(time.time())
                    
                    # Keep the original file path but change the dictionary_name
                    if "dictionary_name" in prompt["102"]["inputs"]:
                        original_dict_name = prompt["102"]["inputs"]["dictionary_name"]
                        prompt["102"]["inputs"]["dictionary_name"] = f"{original_dict_name}_{timestamp}"
                        print(f"Added timestamp to dictionary_name to force reload: {prompt['102']['inputs']['dictionary_name']}")
                    else:
                        # If no dictionary_name exists, add one with timestamp
                        prompt["102"]["inputs"]["dictionary_name"] = f"forced_reload_{timestamp}"
                        print(f"Added new dictionary_name with timestamp: {prompt['102']['inputs']['dictionary_name']}")
                        
                except Exception as e:
                    print(f"Error setting up text file reload: {str(e)}")
        else:
            print("Warning: Node 102 (Load Text File node) not found in workflow")
        
        # Set Hy3DGenerateMeshMultiView parameters
        if "161" in prompt and "inputs" in prompt["161"]:  # Updated node ID for MultiViewFINAL1
            # Use consistent mesh generation settings
            mesh_settings = {
                "seed": random.randint(0, 999999999),
                "scheduler": "FlowMatchEulerDiscreteScheduler",
                "steps": 30,
                "guidance_scale": 5.5
            }
            
            # Apply all settings
            for param, value in mesh_settings.items():
                if param in prompt["161"]["inputs"]:
                    prompt["161"]["inputs"][param] = value
            
            print(f"Set optimal mesh generation parameters for node 161")
        
        # Queue the prompt
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
    
    # Verify input image directory and files
    input_image_dir = "C:\\CODING\\VIBE\\VIBE_Forming\\input\\COMFYINPUTS\\blenderRender"
    required_images = ["front.png", "left.png", "right.png", "back.png"]
    
    # Create input directory if it doesn't exist
    if not os.path.exists(input_image_dir):
        print(f"Creating input image directory: {input_image_dir}")
        try:
            os.makedirs(input_image_dir, exist_ok=True)
            print(f"Successfully created directory: {input_image_dir}")
        except Exception as e:
            print(f"ERROR: Failed to create input directory: {str(e)}")
            sys.exit(1)
    
    # Check each required image
    missing_images = []
    for image_name in required_images:
        image_path = os.path.join(input_image_dir, image_name)
        if not os.path.exists(image_path):
            missing_images.append(image_name)
            print(f"WARNING: Required image not found: {image_path}")
        else:
            # Verify the image is readable
            try:
                with open(image_path, "rb") as f:
                    f.read(10)  # Read first 10 bytes to verify file is accessible
                print(f"Found and verified image: {image_path}")
            except Exception as e:
                print(f"ERROR: Cannot read image {image_path}: {str(e)}")
                missing_images.append(image_name)
    
    if missing_images:
        print(f"WARNING: Missing {len(missing_images)} required images: {', '.join(missing_images)}")
        print("The mesh generation may not work correctly without all required images.")
        
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
    json_path = os.path.join(current_dir, "MultiViewFINAL1.json")
    
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
        important_nodes = ['123', '190', '161']  # 3D mesh export and preview nodes
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
            if '123' in outputs and 'model_file' in outputs['123']:
                model_file = outputs['123']['model_file']
                print(f"Mesh generation completed, file: {model_file}")
                
                if copy_mesh_to_target(COMFYUI_OUTPUT, TARGET_OUTPUT):
                    print("Mesh successfully copied to target location")
                else:
                    print("Failed to copy mesh to target location")
                    sys.exit(1)
            else:
                print("No mesh was generated in the expected output nodes")
                print("Available output nodes:", list(outputs.keys()))
                
                # Check if any GLB file was generated despite missing the expected nodes
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
