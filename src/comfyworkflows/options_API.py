#This script generates design options through ComfyUI using direct HTTP requests

import uuid
import json
import urllib.request
import os
import sys
import time
import shutil
import base64
import random

# Server configuration
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

# Define absolute paths
BASE_DIR = r"C:\CODING\VIBE\VIBE_Forming"
OUTPUT_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "ImageOPTIONS")

print(f"Script starting, output directory set to: {OUTPUT_DIR}")

def queue_prompt(prompt):
    """Send a prompt to the ComfyUI server"""
    try:
        # Modify the workflow to prevent caching
        prompt["45"]["inputs"]["seed"] = random.randint(0, 999999999)  # Random seed for KSampler
        
        # Set consistent filename prefixes without timestamps
        prompt["33"]["inputs"]["filename_prefix"] = "A"  # First output
        prompt["63"]["inputs"]["filename_prefix"] = "B"  # Second output
        prompt["82"]["inputs"]["filename_prefix"] = "C"  # Third output
        
        # Explicitly update all save paths and ensure overwrite is enabled
        save_nodes = ['33', '63', '82', '64', '83', '93']
        for node_id in save_nodes:
            if node_id in prompt and 'inputs' in prompt[node_id]:
                if 'output_path' in prompt[node_id]['inputs']:
                    prompt[node_id]['inputs']['output_path'] = OUTPUT_DIR
                    print(f"Set node {node_id} output path to: {OUTPUT_DIR}")
                
                # Make sure overwrite mode is enabled
                if 'overwrite_mode' in prompt[node_id]['inputs']:
                    prompt[node_id]['inputs']['overwrite_mode'] = "true"
                    print(f"Enabled overwrite mode for node {node_id}")
        
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"http://{server_address}/prompt", data=data)
        req.add_header('Content-Type', 'application/json')
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

def get_image_from_history(prompt_id, node_id):
    """Get image data from history"""
    try:
        history = get_history(prompt_id)
        if prompt_id not in history:
            print(f"No history found for prompt {prompt_id}")
            return None
        
        outputs = history[prompt_id]['outputs']
        if str(node_id) not in outputs:
            print(f"No output found for node {node_id}")
            return None
            
        node_output = outputs[str(node_id)]
        if not node_output or 'images' not in node_output:
            print(f"No images found in output of node {node_id}")
            return None
            
        return node_output['images']
    except Exception as e:
        print(f"Error getting image from history: {str(e)}")
        return None

def save_image_from_url(image_url, output_path):
    """Save an image from a URL to the specified path"""
    try:
        print(f"Downloading image from {image_url}")
        print(f"Saving to {output_path}")
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with urllib.request.urlopen(image_url) as response:
            with open(output_path, 'wb') as f:
                shutil.copyfileobj(response, f)
                
        # Verify the file was actually saved
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"Successfully saved image to {output_path} (size: {file_size} bytes)")
            return True
        else:
            print(f"ERROR: File not found after saving: {output_path}")
            return False
    except Exception as e:
        print(f"Error saving image: {str(e)}")
        return False

def save_image_from_base64(image_data, output_path):
    """Save an image from base64 data to the specified path"""
    try:
        print(f"Saving image from base64 data to {output_path}")
        image_bytes = base64.b64decode(image_data)
        with open(output_path, 'wb') as f:
            f.write(image_bytes)
        print(f"Successfully saved image to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving base64 image: {str(e)}")
        return False

def main():
    # Check if output directory exists
    if not os.path.exists(OUTPUT_DIR):
        print(f"Creating output directory: {OUTPUT_DIR}")
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            print(f"Successfully created directory: {OUTPUT_DIR}")
        except Exception as e:
            print(f"ERROR: Failed to create directory: {str(e)}")
            sys.exit(1)
    else:
        print(f"Output directory already exists: {OUTPUT_DIR}")
    
    # Test write permissions
    try:
        test_file = os.path.join(OUTPUT_DIR, "test_write.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print("Successfully verified write permissions")
    except Exception as e:
        print(f"Error: Cannot write to output directory: {str(e)}")
        sys.exit(1)
    
    # Load the workflow JSON file
    try:
        # Get the absolute path to the JSON file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "VIBEOptions.json")
        
        print(f"Attempting to load JSON file from: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        print("Successfully loaded workflow file")
        
        # Update save paths in workflow to point to the correct output directory
        save_nodes = ['33', '63', '82', '64', '83', '93']
        for node_id in save_nodes:
            if node_id in workflow and 'inputs' in workflow[node_id] and 'output_path' in workflow[node_id]['inputs']:
                workflow[node_id]['inputs']['output_path'] = OUTPUT_DIR
                print(f"Updated output path for node {node_id}")
                
    except Exception as e:
        print(f"Error loading workflow file: {str(e)}")
        sys.exit(1)
    
    try:
        # Queue the prompt
        result = queue_prompt(workflow)
        prompt_id = result['prompt_id']
        print(f"Prompt queued with ID: {prompt_id}")
        
        # Track nodes that should produce images
        image_nodes = ['33', '63', '82']  # Only track the main save nodes
        node_to_letter = {'33': 'A', '63': 'B', '82': 'C'}  # Map nodes to letters
        
        # Poll for completion by checking history endpoint
        max_attempts = 120  # 10 minutes (5 sec interval)
        for attempt in range(max_attempts):
            try:
                print(f"Checking prompt status (attempt {attempt+1}/{max_attempts})...")
                # Get the execution history
                history_url = f"http://{server_address}/history/{prompt_id}"
                with urllib.request.urlopen(history_url) as response:
                    history_data = json.loads(response.read().decode('utf-8'))
                
                # Check if the execution is complete
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    outputs = history_data[prompt_id]["outputs"]
                    # Check if all image nodes have completed
                    all_nodes_done = True
                    for node_id in image_nodes:
                        if node_id not in outputs:
                            all_nodes_done = False
                            break
                    
                    if all_nodes_done:
                        print("All image nodes completed!")
                        break
            except Exception as e:
                print(f"Error checking prompt status: {e}")
            
            # Wait before checking again
            time.sleep(5)
        
        # Wait a moment for files to be written
        time.sleep(2)
        
        # List all directories to check for images
        print("\nChecking for images in potential directories:")
        potential_dirs = [
            OUTPUT_DIR,
            ".",  # Current directory
            os.path.join(BASE_DIR, "output"),
            os.path.join(BASE_DIR, "input"),
            r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"
        ]
        
        for check_dir in potential_dirs:
            if os.path.exists(check_dir):
                print(f"Directory {check_dir} exists, contents:")
                try:
                    files = os.listdir(check_dir)
                    for file in files:
                        if file.endswith(".png"):
                            print(f"  Found image: {file}")
                except Exception as e:
                    print(f"  Error listing directory: {e}")
            else:
                print(f"Directory {check_dir} does not exist")
        
        # Try to save images from history for each node
        for node_id in image_nodes:
            print(f"\nProcessing node {node_id}")
            images = get_image_from_history(prompt_id, node_id)
            if images:
                print(f"Found {len(images)} images for node {node_id}")
                for idx, image_data in enumerate(images):
                    filename = f"{node_to_letter[node_id]}.png"  # Use letter instead of node number
                    filepath = os.path.join(OUTPUT_DIR, filename)
                    print(f"Attempting to save {filename}")
                    
                    # Try both output and temp paths
                    for image_type in ['output', 'temp']:
                        try:
                            image_url = f"http://{server_address}/view?filename={image_data['filename']}&subfolder={image_data['subfolder']}&type={image_type}"
                            if save_image_from_url(image_url, filepath):
                                print(f"Successfully saved {filename}")
                                break
                        except Exception as e:
                            print(f"Error with {image_type} URL: {e}")
                    else:
                        print(f"Failed to save image from node {node_id}")
            else:
                print(f"No images found for node {node_id}")
        
        # Final check of output directory
        if os.path.exists(OUTPUT_DIR):
            output_files = os.listdir(OUTPUT_DIR)
            print(f"\nFinal files in {OUTPUT_DIR}: {output_files}")
            
            # Ensure the images are renamed to match exactly what main.py expects
            for letter in ['A', 'B', 'C']:
                # Check for any files that need to be renamed to the correct format
                for filename in os.listdir(OUTPUT_DIR):
                    if filename.startswith(letter) and filename != f"{letter}.png":
                        source_path = os.path.join(OUTPUT_DIR, filename)
                        target_path = os.path.join(OUTPUT_DIR, f"{letter}.png")
                        try:
                            # If the destination already exists, remove it
                            if os.path.exists(target_path):
                                os.remove(target_path)
                            # Copy the file to the correct name
                            shutil.copy2(source_path, target_path)
                            print(f"Copied {filename} to {letter}.png")
                        except Exception as e:
                            print(f"Error renaming {filename}: {e}")
            
            # Copy images to the directory that Blender's main.py is expecting
            blender_image_dir = os.path.join(BASE_DIR, "input", "options")
            print(f"\nCopying images to Blender image directory: {blender_image_dir}")
            
            # Create the directory if it doesn't exist
            os.makedirs(blender_image_dir, exist_ok=True)
            
            # Copy each image
            for letter in ['A', 'B', 'C']:
                source_path = os.path.join(OUTPUT_DIR, f"{letter}.png")
                target_path = os.path.join(blender_image_dir, f"{letter}.png")
                
                if os.path.exists(source_path):
                    try:
                        shutil.copy2(source_path, target_path)
                        print(f"Successfully copied {letter}.png to {blender_image_dir}")
                    except Exception as e:
                        print(f"Error copying {letter}.png to Blender directory: {e}")
                else:
                    print(f"Source image {source_path} does not exist")
        else:
            print(f"\nOutput directory {OUTPUT_DIR} does not exist!")
        
    except Exception as e:
        print(f"Error during execution: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
