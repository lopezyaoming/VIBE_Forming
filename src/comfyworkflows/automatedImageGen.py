import os
import random
import sys
from typing import Sequence, Mapping, Any, Union
import time
import traceback
import json
import shutil

# Set ComfyUI path directly
COMFYUI_PATH = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
if os.path.exists(COMFYUI_PATH):
    sys.path.append(COMFYUI_PATH)
    print(f"Added ComfyUI path: {COMFYUI_PATH}")
else:
    print(f"Warning: ComfyUI path not found at {COMFYUI_PATH}")

try:
    import torch
except ImportError:
    print("Error: PyTorch not found. Please install it.")
    sys.exit(1)

# Try to import necessary modules
try:
    from nodes import NODE_CLASS_MAPPINGS
    print("Successfully imported NODE_CLASS_MAPPINGS")
except ImportError:
    print("Error: Could not import NODE_CLASS_MAPPINGS from nodes module.")
    print("Make sure ComfyUI is properly installed and the path is correct.")
    NODE_CLASS_MAPPINGS = {}  # Create an empty dict to avoid further errors


def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Returns the value at the given index of a sequence or mapping.

    If the object is a sequence (like list or string), returns the value at the given index.
    If the object is a mapping (like a dictionary), returns the value at the index-th key.

    Some return a dictionary, in these cases, we look for the "results" key

    Args:
        obj (Union[Sequence, Mapping]): The object to retrieve the value from.
        index (int): The index of the value to retrieve.

    Returns:
        Any: The value at the given index.

    Raises:
        IndexError: If the index is out of bounds for the object and the object is not a mapping.
    """
    try:
        return obj[index]
    except KeyError:
        return obj["result"][index]


def find_path(name: str, path: str = None) -> str:
    """
    Recursively looks at parent folders starting from the given path until it finds the given name.
    Returns the path as a Path object if found, or None otherwise.
    """
    # If no path is given, use the current working directory
    if path is None:
        path = os.getcwd()

    # Check if the current directory contains the name
    if name in os.listdir(path):
        path_name = os.path.join(path, name)
        print(f"{name} found: {path_name}")
        return path_name

    # Get the parent directory
    parent_directory = os.path.dirname(path)

    # If the parent directory is the same as the current directory, we've reached the root and stop the search
    if parent_directory == path:
        return None

    # Recursively call the function with the parent directory
    return find_path(name, parent_directory)


def add_comfyui_directory_to_sys_path() -> None:
    """
    Add 'ComfyUI' to the sys.path
    """
    # Use the hardcoded path instead of searching
    comfyui_path = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
    if os.path.isdir(comfyui_path):
        sys.path.append(comfyui_path)
        print(f"'{comfyui_path}' added to sys.path")
    else:
        print(f"WARNING: ComfyUI path not found at {comfyui_path}")
        # Fallback to original search method
        comfyui_path = find_path("ComfyUI")
        if comfyui_path is not None and os.path.isdir(comfyui_path):
            sys.path.append(comfyui_path)
            print(f"'{comfyui_path}' added to sys.path")
        else:
            print("WARNING: Could not find ComfyUI directory")


def add_extra_model_paths() -> None:
    """
    Parse the optional extra_model_paths.yaml file and add the parsed paths to the sys.path.
    """
    try:
        # Try to find the ComfyUI-specific utils or main module
        comfyui_path = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
        if not os.path.exists(comfyui_path):
            print(f"ComfyUI path not found at {comfyui_path}")
            return
            
        # Add ComfyUI directory to sys.path if not already there
        if comfyui_path not in sys.path:
            sys.path.append(comfyui_path)
            
        try:
            from main import load_extra_path_config
        except ImportError:
            print("Could not import load_extra_path_config from main.py. Looking in utils.extra_config instead.")
            try:
                from utils.extra_config import load_extra_path_config
            except ImportError:
                print("Could not find utils.extra_config. Skipping extra model paths.")
                return

        extra_model_paths = find_path("extra_model_paths.yaml")
        
        if extra_model_paths is not None:
            load_extra_path_config(extra_model_paths)
        else:
            print("Could not find the extra_model_paths config file. Skipping.")
            
    except Exception as e:
        print(f"Error in add_extra_model_paths: {e}")
        print("Skipping extra model paths.")


add_comfyui_directory_to_sys_path()
add_extra_model_paths()


def import_custom_nodes() -> None:
    """Find all custom nodes in the custom_nodes folder and add those node objects to NODE_CLASS_MAPPINGS

    This function sets up a new asyncio event loop, initializes the PromptServer,
    creates a PromptQueue, and initializes the custom nodes.
    """
    try:
        # Ensure ComfyUI is in path
        comfyui_path = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable"
        if comfyui_path not in sys.path:
            sys.path.append(comfyui_path)
            
        # Try importing required modules
        try:
            import asyncio
            import execution
            from nodes import init_extra_nodes
            import server
        except ImportError as e:
            print(f"Failed to import ComfyUI modules: {e}")
            print("Make sure ComfyUI is properly installed and the path is correct.")
            return

        # Creating a new event loop and setting it as the default loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Creating an instance of PromptServer with the loop
        server_instance = server.PromptServer(loop)
        execution.PromptQueue(server_instance)

        # Initializing custom nodes
        init_extra_nodes()
        print("Successfully initialized custom nodes")
    except Exception as e:
        print(f"Error in import_custom_nodes: {e}")
        print("Could not initialize custom nodes.")


def load_json_file(file_path):
    """Load a JSON file and return its content"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading JSON file {file_path}: {e}")
        return None


def save_json_file(file_path, data):
    """Save data to a JSON file"""
    try:
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=2)
        print(f"Successfully saved JSON file: {file_path}")
        return True
    except Exception as e:
        print(f"Error saving JSON file {file_path}: {e}")
        return False


def update_paths_in_vibeoptions(vibe_options, multiview):
    """Update paths in VIBEOptions.json to match multiview.json"""
    
    # Get the base directory from multiview.json
    base_forming_dir = "C:\\CODING\\VIBE\\VIBE_Forming"
    
    # Update output paths for saved images
    for node_id in vibe_options:
        node = vibe_options[node_id]
        if "class_type" in node and node["class_type"] == "Save Text File":
            # Update text file save paths
            if "path" in node["inputs"]:
                old_path = node["inputs"]["path"]
                # If the path contains VIBE_Massing, replace with VIBE_Forming
                if "VIBE_Massing" in old_path:
                    new_path = old_path.replace("VIBE_Massing", "VIBE_Forming")
                    node["inputs"]["path"] = new_path
        
        elif "class_type" in node and node["class_type"] == "Image Save":
            # Update image save paths
            if "output_path" in node["inputs"]:
                # Update output path to match the format in multiview.json
                node["inputs"]["output_path"] = f"{base_forming_dir}\\input\\COMFYINPUTS\\ImageOPTIONS"
    
    return vibe_options


def update_paths_in_vibemultiview(vibe_multiview, multiview):
    """Update paths in VIBEMultiView.json to match multiview.json"""
    
    # Get the base directory from multiview.json
    base_forming_dir = "C:\\CODING\\VIBE\\VIBE_Forming"
    
    # Update LoadImage nodes to use full paths
    for node_id in vibe_multiview:
        node = vibe_multiview[node_id]
        if "class_type" in node and node["class_type"] == "LoadImage":
            # Update the image paths to full paths
            if "image" in node["inputs"]:
                image_name = node["inputs"]["image"]
                # Only update if it's a simple filename without a path
                if not "\\" in image_name:
                    title = node.get("_meta", {}).get("title", "")
                    if title == "Load FRONT":
                        node["inputs"]["image"] = f"{base_forming_dir}\\input\\COMFYINPUTS\\blenderRender\\FRONT.png"
                    elif title == "Load LEFT":
                        node["inputs"]["image"] = f"{base_forming_dir}\\input\\COMFYINPUTS\\blenderRender\\LEFT.png"
                    elif title == "Load RIGHT":
                        node["inputs"]["image"] = f"{base_forming_dir}\\input\\COMFYINPUTS\\blenderRender\\RIGHT.png"
                    elif title == "Load BACK":
                        node["inputs"]["image"] = f"{base_forming_dir}\\input\\COMFYINPUTS\\blenderRender\\BACK.png"
        
        # Update the Hy3DExportMesh node paths
        elif "class_type" in node and node["class_type"] == "Hy3DExportMesh":
            node["inputs"]["output_path"] = f"{base_forming_dir}\\output\\generated\\Models"
        
        # Update LineArtPreprocessor resolution to match multiview.json (1024)
        elif "class_type" in node and node["class_type"] == "LineArtPreprocessor":
            if "resolution" in node["inputs"]:
                node["inputs"]["resolution"] = 1024
        
        # Update any Load Text File paths
        elif "class_type" in node and node["class_type"] == "Load Text File":
            if "file_path" in node["inputs"]:
                old_path = node["inputs"]["file_path"]
                if "VIBE_Massing" in old_path:
                    new_path = old_path.replace("VIBE_Massing", "VIBE_Forming")
                    node["inputs"]["file_path"] = new_path
    
    return vibe_multiview


def main():
    try:
        print("Starting automated JSON path update...")
        
        # Define file paths
        current_dir = os.path.dirname(os.path.abspath(__file__))
        vibe_options_path = os.path.join(current_dir, "VIBEOptions.json")
        vibe_multiview_path = os.path.join(current_dir, "VIBEMultiView.json")
        multiview_path = os.path.join(current_dir, "multiview.json")
        options_path = os.path.join(current_dir, "options.json")
        
        # Load JSON files
        vibe_options = load_json_file(vibe_options_path)
        vibe_multiview = load_json_file(vibe_multiview_path)
        multiview = load_json_file(multiview_path)
        options = load_json_file(options_path)
        
        if all([vibe_options, vibe_multiview, multiview, options]):
            # Create backups
            backup_dir = os.path.join(current_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            shutil.copy2(vibe_options_path, os.path.join(backup_dir, f"VIBEOptions_{timestamp}.json"))
            shutil.copy2(vibe_multiview_path, os.path.join(backup_dir, f"VIBEMultiView_{timestamp}.json"))
            
            # Update the JSON files
            updated_vibe_options = update_paths_in_vibeoptions(vibe_options, multiview)
            updated_vibe_multiview = update_paths_in_vibemultiview(vibe_multiview, multiview)
            
            # Save the updated JSON files
            if save_json_file(vibe_options_path, updated_vibe_options) and save_json_file(vibe_multiview_path, updated_vibe_multiview):
                print("Successfully updated all JSON files!")
            else:
                print("Failed to save one or more JSON files.")
        else:
            print("Failed to load one or more JSON files. Cannot proceed.")
    
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
        main()