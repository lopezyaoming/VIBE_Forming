import os
import json
import shutil
import time

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
            if "output_path" not in node["inputs"]:
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