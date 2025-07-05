import bpy
import os
import logging
import time
import math
import mathutils
import subprocess
import sys
import json
import urllib.request
import random
import shutil
from bpy.props import StringProperty, EnumProperty, PointerProperty, IntProperty, FloatProperty, BoolProperty
from bpy.types import Panel, Operator, PropertyGroup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Project paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Go up 3 levels to reach project root
RENDER_OUTPUT_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "blenderRender")
GENERATED_MESH_PATH = os.path.join(BASE_DIR, "output", "generated", "Models", "current_mesh.glb")
TEXT_OPTIONS_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "textOptions")
INPUT_TEXT_FILE = os.path.join(BASE_DIR, "input", "input.txt")
OPTIONS_API_SCRIPT = os.path.join(BASE_DIR, "src", "comfyworkflows", "options_API.py")
RENDER_REQUEST_FILE = os.path.join(BASE_DIR, "render_request.txt")
RENDER_COMPLETE_FILE = os.path.join(BASE_DIR, "render_complete.txt")
IMPORT_REQUEST_FILE = os.path.join(BASE_DIR, "import_request.txt")
IMPORT_COMPLETE_FILE = os.path.join(BASE_DIR, "import_complete.txt")
LIVE_DATA_FILE = os.path.join(BASE_DIR, "output", "live_hand_data.json")  # JSON file from capture script

# Render configuration
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

# ComfyUI server configuration
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_OUTPUT_DIR = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"

# Text prompt configuration
PROMPT_FILE = "prompt.txt"

# Communication files for integration with UI

# Custom request property group
class CustomRequestProperties(PropertyGroup):
    custom_prompt: StringProperty(
        name="Custom Prompt",
        description="Enter your custom request for generating 3D models",
        default="",
        maxlen=500
    )

# Text prompt property group
class PromptProperties(PropertyGroup):
    prompt_items = [
        ("A", "Prompt A", "Use text prompt A"),
        ("B", "Prompt B", "Use text prompt B"),
        ("C", "Prompt C", "Use text prompt C")
    ]
    
    # Selection for text prompt
    active_prompt: EnumProperty(
        name="Text Prompt",
        description="Select the text prompt to use for generation",
        items=prompt_items,
        default="A"
    )
    
    # Display the current prompt text
    show_prompt_text: BoolProperty(
        name="Show Prompt Text",
        description="Show the content of the selected prompt",
        default=False
    )

# Remesh stages property group
class RemeshProperties(PropertyGroup):
    # Toggle for enabling the remesh stages
    enable_remesh: BoolProperty(
        name="Enable Remesh",
        description="Enable staged remesh processing on mesh import",
        default=False
    )
    
    # Current remesh stage (1, 2, or 3)
    current_stage: IntProperty(
        name="Remesh Stage",
        description="Current remesh processing stage",
        default=1,
        min=1,
        max=3
    )
    
    # Remesh type
    remesh_types = [
        ("BLOCKS", "Blocks", "Apply blocks remesh"),
        ("SMOOTH", "Smooth", "Apply smooth remesh"),
        ("SHARP", "Sharp", "Apply sharp remesh")
    ]
    
    remesh_type: EnumProperty(
        name="Remesh Type",
        description="Type of remesh to apply",
        items=remesh_types,
        default="SHARP"
    )

# Add this new class for refreshing images
class IMAGE_OT_refresh(bpy.types.Operator):
    bl_idname = "image.refresh"
    bl_label = "Refresh Images"
    bl_description = "Reload all images from disk"
    
    def execute(self, context):
        logging.info("Manual image refresh requested...")
        
        # Use the common refresh function
        refresh_images_from_disk()
        
        self.report({'INFO'}, "Images refreshed")
        return {'FINISHED'}

class IMAGE_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'

    def draw(self, context):
        layout = self.layout
        
        # Add refresh button at the top
        layout.operator("image.refresh", text="Refresh Images", icon='FILE_REFRESH')
        
        # Add custom request section
        box = layout.box()
        box.label(text="Custom Request:", icon='TEXT')
        box.prop(context.scene.custom_request_properties, "custom_prompt", text="")
        box.operator("request.submit", text="Submit Request", icon='PLAY')
        
        # Add a separator after the refresh button
        layout.separator(factor=0.5)
        
        # Image directory
        image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
        image_names = ['A.png', 'B.png', 'C.png']

        # Create a horizontal layout
        row = layout.row()
        
        # Load and display images side by side
        for img_name in image_names:
            # Create a column for each image
            col = row.column(align=True)  # Align items in column
            col.scale_x = 1.0
            col.scale_y = 1.0
            
            # Get or load image
            img = bpy.data.images.get(img_name)
            if not img:
                try:
                    img_path = os.path.join(image_dir, img_name)
                    if os.path.exists(img_path):
                        img = bpy.data.images.load(img_path)
                        img.name = img_name
                        if not img.packed_file:
                            img.pack()
                except Exception as e:
                    col.label(text=f"Error: {str(e)}")
                    continue
            
            if img:
                # Ensure preview is generated
                if img.preview is None:
                    img.preview_ensure()
                    
                if img.preview and img.preview.icon_id:
                    # Show the image preview
                    col.template_icon(icon_value=img.preview.icon_id, scale=8.0)
                    
                    # Add a "Select" button below each image
                    option_letter = img_name.split('.')[0]  # A, B, or C
                    op = col.operator("option.select", text=f"Select {option_letter}")
                    op.option = option_letter
        
        # Add a separator
        layout.separator()
        
        # Show currently selected text prompt
        props = context.scene.prompt_properties
        box = layout.box()
        box.label(text="Current Text Prompt:", icon='TEXT')
        box.label(text=f"Prompt {props.active_prompt}")
        
        # Add toggle for showing prompt content
        box.prop(props, "show_prompt_text", text="Show Prompt Content")
        
        # Show the prompt content if toggle is on
        if props.show_prompt_text:
            prompt_text = get_prompt_content(f"{props.active_prompt}_0001.txt")
            if prompt_text:
                text_box = box.box()
                # Show first 100 characters with ellipsis
                if len(prompt_text) > 100:
                    display_text = prompt_text[:100] + "..."
                else:
                    display_text = prompt_text
                text_box.label(text=display_text)
        
        # Add a separator for generation buttons
        layout.separator()
        
        # Generation and terminate buttons
        row = layout.row(align=True)
        row.operator("object.generate_iteration", text="Generate New Iteration", icon='CAMERA_DATA')
        
        # Add remesh toggle button showing the current stage
        props = context.scene.remesh_properties
        stage_text = f"Remesh ({props.current_stage})"
        remesh_button = row.operator("object.toggle_remesh", text=stage_text, icon='OUTLINER_OB_MESH')
        
        # Show the current state with different button colors
        if props.enable_remesh:
            row.alert = True  # Make the button red when enabled
        
        # Add a separator before terminate button
        layout.separator(factor=0.5)
        layout.operator("option.terminate_script", text="Terminate Script", icon='X')

# Remesh settings panel
class REMESH_PT_settings_panel(bpy.types.Panel):
    bl_label = "Remesh Settings"
    bl_idname = "REMESH_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'
    bl_options = {'DEFAULT_CLOSED'}  # Panel starts collapsed
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.remesh_properties
        
        # Remesh enable toggle
        layout.prop(props, "enable_remesh", text="Enable Staged Remesh")
        
        # Current stage display
        box = layout.box()
        box.label(text=f"Current Stage: {props.current_stage}")
        
        if props.current_stage == 1:
            box.label(text="Octree Depth: 3")
        elif props.current_stage == 2:
            box.label(text="Octree Depth: 5")
        else:  # stage 3
            box.label(text="No remesh applied")
        
        # Remesh type selection
        layout.prop(props, "remesh_type", text="Remesh Type")
        
        # Help text
        help_box = layout.box()
        help_box.label(text="How It Works:", icon='INFO')
        help_box.label(text="Stage 1: Octree depth 3")
        help_box.label(text="Stage 2: Octree depth 5")
        help_box.label(text="Stage 3: No remesh applied")
        help_box.label(text="Each import advances the stage")

class OPTION_OT_select(bpy.types.Operator):
    bl_idname = "option.select"
    bl_label = "Select Option"
    bl_description = "Select this design option and apply corresponding text prompt"
    
    option: StringProperty()
    
    def execute(self, context):
        logging.info(f"Selected option: {self.option}")
        
        # Save selection to output directory
        output_dir = "C:/CODING/VIBE/VIBE_Forming/output"
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, "selected_option.txt"), "w") as f:
            f.write(f"Selected Option: {self.option}\n")
            f.write(f"Timestamp: {time.time()}\n")
        
        # Store the option value in a variable for the closure
        option_value = self.option
        
        # Also apply the corresponding text prompt
        success = copy_text_file(f"{option_value}_0001.txt", PROMPT_FILE)
        
        if success:
            logging.info(f"Applied text prompt {option_value}")
        else:
            logging.error(f"Failed to apply text prompt {option_value}")
        
        # Update the active prompt in the UI to reflect the selection
        context.scene.prompt_properties.active_prompt = option_value
        
        # Show a message box using a closure to capture the option value
        def draw(popup, context):
            popup.layout.label(text=f"Selected Option {option_value}")
            popup.layout.label(text="Result saved to output directory")
            popup.layout.label(text=f"Text prompt {option_value} applied")
            
        bpy.context.window_manager.popup_menu(draw, title="Selection Confirmed", icon='INFO')
        
        return {'FINISHED'}

class OPTION_OT_terminate_script(bpy.types.Operator):
    bl_idname = "option.terminate_script"
    bl_label = "Terminate Script"
    bl_description = "Unregister the addon and stop the script"
    
    def execute(self, context):
        logging.info("Terminating script...")
        unregister()
        self.report({'INFO'}, "Script terminated")
        return {'FINISHED'}

# Generate new iteration operator
class OBJECT_OT_generate_iteration(bpy.types.Operator):
    bl_idname = "object.generate_iteration"
    bl_label = "Generate New Iteration"
    bl_description = "Render views, process through ComfyUI, and import the resulting mesh"
    
    def execute(self, context):
        # Check if there's an active selection first
        active_obj = context.active_object
        if not active_obj or active_obj.type != 'MESH':
            # Instead of cancelling, just log a warning and continue
            self.report({'WARNING'}, "No active mesh found. Proceeding without active mesh reference.")
            logging.warning("No active mesh found. Proceeding without active mesh reference.")
            # Continue with the operation instead of returning CANCELLED
            
        # Step 1: Render multi-view images
        logging.info("Starting new iteration generation...")
        render_success = render_multiview()
        if not render_success:
            self.report({'ERROR'}, "Failed to render multi-views")
            return {'CANCELLED'}
            
        # Step 2: Process renders through ComfyUI
        api_success = run_comfyui_workflow()
        if not api_success:
            self.report({'ERROR'}, "Failed to process through ComfyUI")
            return {'CANCELLED'}
            
        # Step 3: Import the generated mesh
        import_success = import_generated_mesh()
        if not import_success:
            self.report({'ERROR'}, "Failed to import generated mesh")
            return {'CANCELLED'}
            
        self.report({'INFO'}, "Successfully generated new iteration")
        return {'FINISHED'}

# Remesh toggle operator
class OBJECT_OT_toggle_remesh(bpy.types.Operator):
    bl_idname = "object.toggle_remesh"
    bl_label = "Toggle Remesh"
    bl_description = "Toggle the staged remesh functionality"
    
    def execute(self, context):
        # Toggle the enable_remesh property
        props = context.scene.remesh_properties
        props.enable_remesh = not props.enable_remesh
        
        status = "enabled" if props.enable_remesh else "disabled"
        stage = props.current_stage
        
        # Show a message about the current status
        self.report({'INFO'}, f"Remesh {status}. Will be applied at stage {stage} on next import")
        logging.info(f"Remesh {status}. Will be applied at stage {stage} on next import")
        
        # Update the remesh state file for UI
        try:
            remesh_state_path = os.path.join(os.path.dirname(bpy.data.filepath), "remesh_state.txt")
            with open(remesh_state_path, "w") as f:
                f.write(f"enabled={str(props.enable_remesh).lower()}\n")
                f.write(f"stage={props.current_stage}\n")
                f.write(f"type={props.remesh_type}\n")
                f.write(f"timestamp={time.time()}\n")
            logging.info(f"Updated remesh state file: {remesh_state_path}")
        except Exception as e:
            logging.error(f"Error writing remesh state file: {str(e)}")
        
        return {'FINISHED'}

def get_prompt_content(prompt_file):
    """Get the content of a text prompt file"""
    try:
        file_path = os.path.join(TEXT_OPTIONS_DIR, prompt_file)
        if not os.path.exists(file_path):
            logging.error(f"Prompt file not found: {file_path}")
            return "File not found"
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Error reading prompt file: {e}")
        return "Error reading file"

def copy_text_file(source_file, target_file):
    """Copy the contents of source file to target file"""
    try:
        source_path = os.path.join(TEXT_OPTIONS_DIR, source_file)
        target_path = os.path.join(TEXT_OPTIONS_DIR, target_file)
        
        if not os.path.exists(source_path):
            logging.error(f"Source file not found: {source_path}")
            return False
            
        with open(source_path, 'r', encoding='utf-8') as source:
            content = source.read()
            
        with open(target_path, 'w', encoding='utf-8') as target:
            target.write(content)
            
        logging.info(f"Successfully copied {source_file} to {target_file}")
        return True
    except Exception as e:
        logging.error(f"Error copying file: {e}")
        return False

def run_comfyui_workflow():
    """Process renders through ComfyUI using direct HTTP requests instead of websockets"""
    try:
        logging.info("Starting ComfyUI workflow processing...")
        
        # Generate a unique client ID for this session
        client_id = f"blender_{random.randint(1000, 9999)}"
        
        # Load the workflow JSON
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)
        json_path = os.path.join(parent_dir, "comfyworkflows", "multiview.json")
        
        if not os.path.exists(json_path):
            logging.error(f"Workflow JSON not found at {json_path}")
            return False
            
        logging.info(f"Loading workflow from {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            workflow = json.load(f)
        
        # Update the seed in the workflow to prevent caching
        try:
            workflow["83"]["inputs"]["seed"] = random.randint(0, 999999999)
            logging.info("Updated random seed in workflow")
        except KeyError:
            logging.warning("Could not update seed in workflow (node 83 not found)")
        
        # Queue the prompt with the workflow
        prompt_data = {"prompt": workflow, "client_id": client_id}
        json_data = json.dumps(prompt_data).encode('utf-8')
        
        # Send the prompt to ComfyUI
        try:
            req = urllib.request.Request(f"http://{COMFYUI_SERVER}/prompt", data=json_data)
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req) as response:
                prompt_result = json.loads(response.read().decode('utf-8'))
                prompt_id = prompt_result.get('prompt_id')
                if not prompt_id:
                    logging.error("No prompt ID received from ComfyUI")
                    return False
                logging.info(f"Prompt queued with ID: {prompt_id}")
        except Exception as e:
            logging.error(f"Error sending prompt to ComfyUI: {e}")
            return False
        
        # Poll for completion by checking history endpoint
        max_attempts = 120  # 10 minutes (5 sec interval)
        for attempt in range(max_attempts):
            try:
                logging.info(f"Checking prompt status (attempt {attempt+1}/{max_attempts})...")
                history_url = f"http://{COMFYUI_SERVER}/history/{prompt_id}"
                with urllib.request.urlopen(history_url) as response:
                    history_data = json.loads(response.read().decode('utf-8'))
                    
                # Check if the execution is complete
                if prompt_id in history_data and "outputs" in history_data[prompt_id]:
                    outputs = history_data[prompt_id]["outputs"]
                    if "84" in outputs and "model_file" in outputs["84"]:
                        logging.info("Mesh generation completed!")
                        
                        # Extract the model file path
                        model_file_path = outputs["84"]["model_file"]
                        logging.info(f"Generated model file: {model_file_path}")
                        
                        # Copy the model file to our target location
                        copy_mesh_to_target(COMFYUI_OUTPUT_DIR, os.path.dirname(GENERATED_MESH_PATH))
                        return True
            except Exception as e:
                logging.error(f"Error checking prompt status: {e}")
            
            # Wait before checking again
            time.sleep(5)
        
        logging.error("Timed out waiting for ComfyUI to process")
        return False
    except Exception as e:
        logging.error(f"Error processing ComfyUI workflow: {e}")
        return False

def copy_mesh_to_target(comfyui_output_dir, target_dir):
    """Copy the latest generated mesh from ComfyUI output to target directory"""
    try:
        # Ensure target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Find the latest .glb file in ComfyUI output
        glb_files = [f for f in os.listdir(comfyui_output_dir) if f.endswith('.glb')]
        if not glb_files:
            logging.error("No .glb files found in ComfyUI output directory")
            return False
            
        # Sort by modification time to get the latest
        latest_glb = max(glb_files, key=lambda x: os.path.getmtime(os.path.join(comfyui_output_dir, x)))
        
        # Copy to target location
        source_path = os.path.join(comfyui_output_dir, latest_glb)
        target_path = os.path.join(target_dir, "current_mesh.glb")
        
        shutil.copy2(source_path, target_path)
        logging.info(f"Successfully copied mesh from {source_path} to {target_path}")
        return True
    except Exception as e:
        logging.error(f"Error copying mesh: {e}")
        return False

def import_generated_mesh():
    """Import the generated mesh into Blender"""
    try:
        if not os.path.exists(GENERATED_MESH_PATH):
            logging.error(f"Generated mesh not found at {GENERATED_MESH_PATH}")
            return False
            
        logging.info(f"Importing mesh from {GENERATED_MESH_PATH}")
        
        # Check if there's an active selection first
        active_obj = bpy.context.active_object
        has_active_mesh = active_obj and active_obj.type == 'MESH'
        
        # Initialize previous_obj and previous dimensions
        previous_obj = None
        previous_max_dim = 1.0  # Default if no previous object
        previous_x_larger_than_y = True  # Default orientation assumption
        
        if has_active_mesh:
            # Store the reference to the previously active object
            previous_obj = active_obj
            
            # Get the max dimension of the previous object
            previous_max_dim = max(previous_obj.dimensions.x, previous_obj.dimensions.y, previous_obj.dimensions.z)
            
            # Store which dimension is larger (x or y)
            previous_x_larger_than_y = previous_obj.dimensions.x >= previous_obj.dimensions.y
            
            logging.info(f"Previous object max dimension: {previous_max_dim}")
            logging.info(f"Previous object X > Y: {previous_x_larger_than_y}")
        else:
            logging.warning("No active mesh found. Importing without hiding any mesh.")
            
        # Hide all existing mesh objects before importing the new one
        logging.info("Hiding selected existing mesh objects...")
        existing_meshes = []
        
        # Keep track of objects to skip (base objects)
        protected_objects = []
        
        # Get a clean list of existing mesh objects to avoid reference errors later
        try:
            # Create a safe copy of object names to avoid iterator issues
            existing_mesh_names = [obj.name for obj in bpy.data.objects if obj.type == 'MESH']
            logging.info(f"Found {len(existing_mesh_names)} existing mesh objects")
            
            # First identify protected objects
            for obj_name in existing_mesh_names:
                # Skip objects named 'base' or containing 'base' in their name (case insensitive)
                if 'base' in obj_name.lower():
                    protected_objects.append(obj_name)
                    logging.info(f"Protected object (will stay visible): {obj_name}")
            
            # Process each mesh by name to avoid reference errors
            for obj_name in existing_mesh_names:
                # Skip if the object is protected
                if obj_name in protected_objects:
                    continue
                    
                # Only hide selected or previously generated objects
                try:
                    # Check if the object still exists in the scene
                    if obj_name in bpy.data.objects:
                        obj = bpy.data.objects[obj_name]
                        # Store selection state to ensure we can check it safely
                        is_selected = False
                        try:
                            is_selected = obj.select_get()
                        except ReferenceError:
                            logging.warning(f"Reference error when checking selection of {obj_name}")
                            continue
                        except Exception as select_err:
                            logging.warning(f"Error when checking selection of {obj_name}: {str(select_err)}")
                            continue
                            
                        # Check if this was the previous object (the active object)
                        is_previous = False
                        try:
                            is_previous = (has_active_mesh and active_obj and obj.name == active_obj.name)
                        except ReferenceError:
                            is_previous = False
                            logging.warning(f"Reference error when checking if {obj_name} was the previous object")
                        except Exception as prev_err:
                            logging.warning(f"Error when checking if {obj_name} was the previous object: {str(prev_err)}")
                        
                        if is_selected or is_previous:
                            try:
                                # Double-check the object still exists before hiding
                                if obj_name in bpy.data.objects:
                                    obj = bpy.data.objects[obj_name]  # Get a fresh reference
                                    obj.hide_viewport = True
                                    obj.hide_render = True
                                    existing_meshes.append(obj_name)
                                    logging.info(f"Hidden selected mesh: {obj_name}")
                            except ReferenceError:
                                logging.warning(f"Reference error when hiding {obj_name}")
                            except Exception as hide_err:
                                logging.warning(f"Error when hiding {obj_name}: {str(hide_err)}")
                except Exception as e:
                    logging.error(f"Failed to hide mesh {obj_name}: {str(e)}")
                    import traceback
                    logging.error(traceback.format_exc())
        except Exception as e:
            logging.error(f"Error processing existing meshes: {str(e)}")
            
        logging.info(f"Successfully hidden {len(existing_meshes)} meshes")
            
        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')
        
        # Get the list of objects before import
        objects_before = set(bpy.context.scene.objects)
        
        # Import the GLB file with specific import options
        try:
            logging.info(f"Attempting to import {GENERATED_MESH_PATH}")
            
            # Make sure the file exists and has size
            file_size = os.path.getsize(GENERATED_MESH_PATH)
            logging.info(f"GLB file size: {file_size} bytes")
            
            if file_size == 0:
                logging.error("GLB file exists but is empty (0 bytes)")
                return False
                
            # Import with more detailed options and error catching
            try:
                # First try to use import options that exclude empty objects
                bpy.ops.import_scene.gltf(
                    filepath=GENERATED_MESH_PATH,
                    import_pack_images=True,
                    merge_vertices=True,
                    import_cameras=False,
                    import_lights=False
                )
                logging.info("Successfully imported glTF with advanced options")
            except TypeError:
                # Fall back to basic import if the version doesn't support those options
                bpy.ops.import_scene.gltf(filepath=GENERATED_MESH_PATH)
                logging.info("Successfully imported glTF with basic options")
                
        except Exception as import_error:
            logging.error(f"Error during import: {import_error}")
            # Try with pure filepath
            try:
                logging.info("Trying alternative import method...")
                bpy.ops.import_scene.gltf(filepath=str(GENERATED_MESH_PATH))
                logging.info("Alternative import method succeeded")
            except Exception as alt_error:
                logging.error(f"Alternative import also failed: {alt_error}")
                return False
        
        # Get the list of objects after import
        objects_after = set(bpy.context.scene.objects)
        
        # Find the newly added objects
        imported_objects = list(objects_after - objects_before)
        logging.info(f"Imported {len(imported_objects)} new objects")
        
        if not imported_objects:
            logging.error("No objects were imported")
            return False
        
        # Find all imported mesh objects, regardless of hierarchy
        all_imported_meshes = []
        empties_to_remove = []
        
        # Identify meshes and empty container objects
        for obj in imported_objects:
            if obj.type == 'MESH' and hasattr(obj.data, 'vertices') and len(obj.data.vertices) > 0:
                all_imported_meshes.append(obj)
                logging.info(f"Found mesh: {obj.name} with {len(obj.data.vertices)} vertices")
            elif obj.type == 'EMPTY' and (obj.name.lower() == 'world' or obj.name.lower() == 'scene' or obj.name.lower().startswith('empty')):
                # This is likely a container object we want to remove
                empties_to_remove.append(obj)
                logging.info(f"Found empty container: {obj.name}")
                
                # Check for mesh children and add them to our list
                for child in obj.children:
                    if child.type == 'MESH' and child not in all_imported_meshes:
                        all_imported_meshes.append(child)
                        logging.info(f"Found mesh child: {child.name} with {len(child.data.vertices) if hasattr(child.data, 'vertices') else 0} vertices")
            
        if not all_imported_meshes:
            logging.error("No valid mesh objects found in the import")
            return False
            
        # Find the mesh with the most vertices
        main_mesh = max(all_imported_meshes, key=lambda obj: len(obj.data.vertices) if hasattr(obj.data, 'vertices') else 0)
        logging.info(f"Selected main mesh: {main_mesh.name} with {len(main_mesh.data.vertices)} vertices")
        
        # Parent all mesh objects to main_mesh if they're not already in a hierarchy
        for mesh_obj in all_imported_meshes:
            if mesh_obj != main_mesh and mesh_obj.parent in empties_to_remove:
                # Clear parent but keep transform
                original_matrix = mesh_obj.matrix_world.copy()
                mesh_obj.parent = None
                mesh_obj.matrix_world = original_matrix
                
                # Make it a child of main_mesh
                mesh_obj.parent = main_mesh
                logging.info(f"Re-parented {mesh_obj.name} to {main_mesh.name}")
        
        # Now delete all empty container objects
        for empty in empties_to_remove:
            bpy.data.objects.remove(empty, do_unlink=True)
            logging.info(f"Removed empty container: {empty.name}")
        
        # Hide the previous object if it exists (double-check in case our initial hiding missed it)
        if has_active_mesh and previous_obj:
            try:
                # Make sure the previous object reference is still valid
                if previous_obj.name in bpy.data.objects:
                    previous_obj.hide_viewport = True
                    previous_obj.hide_render = True
                    logging.info(f"Hidden previous active object: {previous_obj.name}")
                    
                    # Also hide any children the previous object might have
                    for child in previous_obj.children:
                        if child.type == 'MESH':
                            child.hide_viewport = True
                            child.hide_render = True
                            logging.info(f"Hidden child object: {child.name}")
            except ReferenceError:
                logging.warning("Previous object reference no longer valid, cannot hide it")
            except Exception as e:
                logging.error(f"Error hiding previous object: {str(e)}")
        
        # Set the main mesh as active
        bpy.context.view_layer.objects.active = main_mesh
        main_mesh.select_set(True)
        
        # Ensure the main mesh and its children are visible
        try:
            if main_mesh.name in bpy.data.objects:  # Verify the object still exists
                main_mesh.hide_viewport = False
                main_mesh.hide_render = False
                logging.info(f"Made main mesh visible: {main_mesh.name}")
            
                # Make sure any children are also visible (with error protection)
                try:
                    # First check if children_recursive property exists and is accessible
                    if hasattr(main_mesh, 'children_recursive'):
                        for child in main_mesh.children_recursive:
                            try:
                                if child.type == 'MESH':
                                    child.hide_viewport = False
                                    child.hide_render = False
                                    logging.info(f"Made child mesh visible: {child.name}")
                            except ReferenceError:
                                logging.warning(f"Reference error while trying to access child of {main_mesh.name}")
                            except Exception as child_error:
                                logging.error(f"Error processing child: {str(child_error)}")
                except ReferenceError:
                    logging.warning("Reference error while accessing children_recursive")
                except Exception as children_error:
                    logging.error(f"Error accessing children: {str(children_error)}")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - cannot update visibility")
        except Exception as e:
            logging.error(f"Error setting main mesh visibility: {str(e)}")
        
        # Set the object's origin to its geometry center
        try:
            if main_mesh.name in bpy.data.objects:  # Check if the object still exists
                # Set origin to geometry
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
                logging.info("Set object origin to geometry center")
                
                # Center the object at the world origin
                main_mesh.location = (0, 0, 0)
                logging.info("Centered object at world origin")
            else:
                logging.warning("Main mesh no longer exists - skipping origin and location setting")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - skipping origin and location setting")
        except Exception as e:
            logging.error(f"Error setting object origin and location: {str(e)}")
        
        # Calculate and apply scaling to match the previous object's max dimension
        try:
            if main_mesh.name in bpy.data.objects:  # Check if the object still exists
                current_max_dim = max(main_mesh.dimensions.x, main_mesh.dimensions.y, main_mesh.dimensions.z)
                logging.info(f"Current mesh max dimension: {current_max_dim}")
                
                if current_max_dim > 0:
                    # If a previous object exists, use its dimensions for scaling
                    if has_active_mesh and previous_obj:
                        scale_factor = previous_max_dim / current_max_dim
                    else:
                        # Default scaling if no previous object
                        scale_factor = 1.0 / current_max_dim  # Scale to unit size
                        
                    logging.info(f"Calculated scale factor: {scale_factor}")
                    
                    # Apply scaling to main mesh
                    main_mesh.scale = (scale_factor, scale_factor, scale_factor)
                    
                    # Apply the scale
                    try:
                        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                        logging.info(f"Applied scaling factor {scale_factor}")
                    except Exception as apply_error:
                        logging.error(f"Error applying transform: {str(apply_error)}")
                    
                    # Check if we need to rotate the model based on X and Y dimensions
                    current_x_larger_than_y = main_mesh.dimensions.x >= main_mesh.dimensions.y
                    
                    # If previous object exists and dimension orientation doesn't match
                    if has_active_mesh and previous_obj and (current_x_larger_than_y != previous_x_larger_than_y):
                        logging.info("X/Y dimension orientation mismatch detected, rotating object 45 degrees")
                        
                        # Rotate 45 degrees counterclockwise around Z axis
                        # Convert degrees to radians (45 degrees = π/4 radians)
                        rotation_angle = math.radians(45)
                        
                        # Rotate the object
                        main_mesh.rotation_euler.z += rotation_angle
                        
                        # Apply the rotation
                        try:
                            bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
                            logging.info("Applied 45 degree counterclockwise rotation")
                        except Exception as rot_error:
                            logging.error(f"Error applying rotation: {str(rot_error)}")
                else:
                    logging.warning("Imported mesh has zero dimensions, couldn't scale properly")
            else:
                logging.warning("Main mesh no longer exists - skipping scaling and rotation")
        except ReferenceError:
            logging.warning("Main mesh reference is no longer valid - skipping scaling and rotation")
        except Exception as e:
            logging.error(f"Error during scaling and rotation: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
        
        # Apply staged remesh if enabled
        if bpy.context.scene.remesh_properties.enable_remesh:
            stage = bpy.context.scene.remesh_properties.current_stage
            remesh_type = bpy.context.scene.remesh_properties.remesh_type
            
            logging.info(f"Applying staged remesh: Stage {stage}, Type {remesh_type}")
            
            # Store the main_mesh name so we can look it up again if needed
            main_mesh_name = ""
            
            # Make sure main_mesh still exists and is valid before applying remesh
            try:
                # Verify main_mesh is still a valid reference
                if not main_mesh or not hasattr(main_mesh, 'name'):
                    logging.error("Cannot apply remesh: Invalid main mesh reference")
                    return False
                    
                # Store the name for later reference
                main_mesh_name = main_mesh.name
                
                # Verify the object exists in the scene
                if main_mesh_name in bpy.data.objects:
                    # Get a fresh reference to the mesh
                    mesh_obj = bpy.data.objects[main_mesh_name]
                    
                    # Make sure it's a mesh
                    if mesh_obj.type == 'MESH':
                        # Deselect all objects and select only our target mesh
                        bpy.ops.object.select_all(action='DESELECT')
                        mesh_obj.select_set(True)
                        bpy.context.view_layer.objects.active = mesh_obj
                        
                        # Now apply the remesh using the fresh reference
                        remesh_result = apply_staged_remesh(mesh_obj, stage, remesh_type)
                        
                        if remesh_result:
                            # Increment stage for next import
                            next_stage = stage + 1
                            if next_stage > 3:
                                next_stage = 1  # Reset to stage 1 if we're past stage 3
                                
                            bpy.context.scene.remesh_properties.current_stage = next_stage
                            logging.info(f"Incremented remesh stage to {next_stage}")
                        else:
                            logging.error("Failed to apply remesh")
                    else:
                        logging.error(f"Cannot apply remesh: Object {main_mesh_name} is not a mesh")
                else:
                    logging.error(f"Cannot apply remesh: Object {main_mesh_name} not found in the scene")
            except ReferenceError:
                logging.error("Cannot apply remesh: Main mesh reference is no longer valid")
                
                # If we stored the name, try to use it to get a fresh reference
                if main_mesh_name and main_mesh_name in bpy.data.objects:
                    logging.info(f"Attempting remesh with fresh reference to {main_mesh_name}")
                    mesh_obj = bpy.data.objects[main_mesh_name]
                    remesh_result = apply_staged_remesh(mesh_obj, stage, remesh_type)
                    
                    if remesh_result:
                        next_stage = stage + 1
                        if next_stage > 3:
                            next_stage = 1
                        bpy.context.scene.remesh_properties.current_stage = next_stage
                        logging.info(f"Recovered and incremented remesh stage to {next_stage}")
            except Exception as e:
                logging.error(f"Error preparing for remesh: {str(e)}")
                import traceback
                logging.error(traceback.format_exc())
        
        # Make sure the main_mesh still exists before returning
        try:
            # Store the mesh name first to avoid reference errors
            mesh_name = ""
            
            # Carefully extract the name
            try:
                if main_mesh and hasattr(main_mesh, 'name'):
                    mesh_name = main_mesh.name
                else:
                    logging.error("Main mesh reference is invalid")
                    # Try to find any active mesh as a fallback
                    if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                        logging.info(f"Using active mesh as fallback: {bpy.context.active_object.name}")
                        return True
                    return False
            except ReferenceError:
                logging.error("Cannot access main mesh name (reference error)")
                # Try to find any active mesh as a fallback
                if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                    logging.info(f"Using active mesh as fallback: {bpy.context.active_object.name}")
                    return True
                return False
            
            # Ensure the object is still in the Blender data using the stored name
            if mesh_name and mesh_name in bpy.data.objects:
                # Double-check it's a mesh
                if bpy.data.objects[mesh_name].type == 'MESH':
                    logging.info(f"Successfully imported and processed mesh: {mesh_name}")
                    return True
                else:
                    logging.error(f"Object {mesh_name} exists but is no longer a mesh")
            else:
                if mesh_name:
                    logging.error(f"Object {mesh_name} no longer exists in the scene")
                else:
                    logging.error("No valid mesh name could be determined")
                
            # Try to find another active mesh
            if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                logging.info(f"Found alternative active mesh: {bpy.context.active_object.name}")
                return True
                
            return False
        except ReferenceError:
            logging.error("Main mesh was removed during processing")
            # Try to find another active mesh
            if bpy.context.active_object and bpy.context.active_object.type == 'MESH':
                logging.info(f"Found alternative active mesh: {bpy.context.active_object.name}")
                return True
            return False
        except Exception as e:
            logging.error(f"Error in final mesh verification: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    except Exception as e:
        logging.error(f"Error importing generated mesh: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def apply_staged_remesh(main_mesh, stage, remesh_type):
    """Apply a remesh modifier based on the current stage
    
    Args:
        main_mesh: The mesh object to apply the remesh to
        stage: The current remesh stage (1, 2, or 3)
        remesh_type: The type of remesh to apply (BLOCKS, SMOOTH, SHARP)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logging.info(f"Starting remesh process - Stage {stage}, Type: {remesh_type}")
        
        # Verify we have a valid mesh object
        if not main_mesh:
            logging.error("Cannot apply remesh: No mesh provided")
            return False
        
        # Get the name now while reference is still valid
        mesh_name = ""
        try:
            # Check if this is even a blender object
            if not hasattr(main_mesh, 'name'):
                logging.error("Cannot apply remesh: Invalid object (not a Blender object)")
                return False
                
            mesh_name = main_mesh.name
            logging.info(f"Applying remesh to object: {mesh_name}")
        except ReferenceError:
            logging.error("Cannot apply remesh: Cannot access object name (reference error)")
            return False
        except Exception as name_error:
            logging.error(f"Cannot access object properties: {str(name_error)}")
            return False
            
        # Verify the object still exists in the scene using the name
        if mesh_name not in bpy.data.objects:
            logging.error(f"Cannot apply remesh: Object '{mesh_name}' not found in scene")
            return False
            
        # Get a fresh reference to the object
        mesh_obj = bpy.data.objects.get(mesh_name)
        if not mesh_obj:
            logging.error(f"Cannot apply remesh: Failed to get object '{mesh_name}'")
            return False
            
        # Verify it's a mesh
        if mesh_obj.type != 'MESH':
            logging.error(f"Cannot apply remesh: Object '{mesh_name}' is not a mesh")
            return False
            
        logging.info(f"Object verification passed for '{mesh_name}'")
        
        # Early exit for stage 3 (no remesh)
        if stage == 3:
            logging.info("Stage 3: No remesh applied (as configured)")
            return True
            
        # Select and make the mesh active - use the fresh reference
        try:
            # Deselect all objects first
            logging.info("Deselecting all objects")
            bpy.ops.object.select_all(action='DESELECT')
            
            # Select our target mesh
            logging.info(f"Selecting mesh: {mesh_obj.name}")
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
        except Exception as select_error:
            logging.error(f"Failed to select mesh: {str(select_error)}")
            return False
        
        # Remove any existing remesh modifiers
        try:
            mod_count = 0
            modifiers_to_remove = []
            
            # Create a safe copy of modifiers to avoid reference errors
            for mod in mesh_obj.modifiers:
                if mod.type == 'REMESH':
                    modifiers_to_remove.append(mod.name)
                    
            for mod_name in modifiers_to_remove:
                mod = mesh_obj.modifiers.get(mod_name)
                if mod:
                    mesh_obj.modifiers.remove(mod)
                    mod_count += 1
            if mod_count > 0:
                logging.info(f"Removed {mod_count} existing remesh modifiers")
        except Exception as mod_error:
            logging.error(f"Error removing existing modifiers: {str(mod_error)}")
            # Continue anyway - this isn't fatal
        
        # Create a new remesh modifier
        try:
            logging.info("Creating new remesh modifier")
            remesh_mod = mesh_obj.modifiers.new(name="StageRemesh", type='REMESH')
            
            # Set the remesh mode based on type
            if remesh_type == 'BLOCKS':
                remesh_mod.mode = 'BLOCKS'
            elif remesh_type == 'SMOOTH':
                remesh_mod.mode = 'SMOOTH'
            else:  # Default to SHARP
                remesh_mod.mode = 'SHARP'
            
            # Set octree depth based on stage
            if stage == 1:
                remesh_mod.octree_depth = 3
            else:  # stage 2
                remesh_mod.octree_depth = 5
            
            # Set remove disconnected to False
            remesh_mod.use_remove_disconnected = False
            
            logging.info(f"Applied {remesh_type} remesh with octree depth {remesh_mod.octree_depth}")
        except Exception as create_error:
            logging.error(f"Failed to create remesh modifier: {str(create_error)}")
            return False
        
        # Apply the modifier with robust error handling
        try:
            logging.info("Applying remesh modifier")
            # Ensure we're in object mode
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
                
            # Do a final check that the object and modifier still exist
            if mesh_name in bpy.data.objects and "StageRemesh" in bpy.data.objects[mesh_name].modifiers:
                # Apply the modifier
                bpy.ops.object.modifier_apply(modifier="StageRemesh")
                logging.info("Remesh modifier applied successfully!")
            else:
                logging.error("Object or modifier no longer exists, cannot apply")
                return False
        except Exception as apply_error:
            logging.error(f"Error applying modifier: {str(apply_error)}")
            # Try a different approach - sometimes the modifier apply fails
            try:
                logging.info("Trying alternate method: convert to mesh")
                # Check if the object still exists
                if mesh_name in bpy.data.objects:
                    # Ensure object is still selected
                    mesh_obj = bpy.data.objects[mesh_name]  # Get fresh reference
                    mesh_obj.select_set(True)
                    bpy.context.view_layer.objects.active = mesh_obj
                    
                    # Ensure we're in object mode
                    if bpy.context.mode != 'OBJECT':
                        bpy.ops.object.mode_set(mode='OBJECT')
                        
                    # Try converting to mesh
                    bpy.ops.object.convert(target='MESH')
                    logging.info("Applied remesh by converting to mesh")
                else:
                    logging.error("Object no longer exists for alternative method")
                    return False
            except Exception as convert_error:
                logging.error(f"Failed to apply remesh: {str(convert_error)}")
                return False
        
        # Verify the mesh still exists after remeshing - get fresh reference
        try:
            # Use a safe approach to check existence
            if mesh_name in bpy.data.objects:
                final_obj = bpy.data.objects[mesh_name]
                if final_obj.type == 'MESH':
                    logging.info(f"Remesh successfully applied to {mesh_name}")
                    return True
                else:
                    logging.error(f"Object {mesh_name} exists but is no longer a mesh")
            else:
                logging.error(f"Object {mesh_name} no longer exists after remeshing")
            return False
        except Exception as verify_error:
            logging.error(f"Error verifying mesh after remesh: {str(verify_error)}")
            return False
    except Exception as e:
        logging.error(f"Error applying remesh: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

def render_multiview():
    """
    Render multiple views using the RenderCam camera:
    - front view (frame 1)
    - right view (frame 2)
    - back view (frame 3)
    - left view (frame 4)
    """
    try:
        # Create output directory
        os.makedirs(RENDER_OUTPUT_DIR, exist_ok=True)
        logging.info(f"Render output directory created: {RENDER_OUTPUT_DIR}")
        
        # Get the render camera
        render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
        if not render_cam:
            logging.error(f"Render camera not found: {RENDER_CAMERA_NAME}")
            # Try to create a camera if it doesn't exist
            try:
                bpy.ops.object.camera_add(location=(0, -10, 0), rotation=(math.radians(90), 0, 0))
                render_cam = bpy.context.active_object
                render_cam.name = RENDER_CAMERA_NAME
                logging.info(f"Created new render camera: {RENDER_CAMERA_NAME}")
                
                # Set camera properties for better rendering
                render_cam.data.type = 'PERSP'
                render_cam.data.lens = 50
                render_cam.data.clip_start = 0.1
                render_cam.data.clip_end = 100
            except Exception as e:
                logging.error(f"Failed to create render camera: {e}")
                return False
            
        # Store current camera and frame
        current_camera = bpy.context.scene.camera
        current_frame = bpy.context.scene.frame_current
        
        # Set render camera as active camera
        bpy.context.scene.camera = render_cam
        
        # Configure render settings
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.resolution_x = 512
        bpy.context.scene.render.resolution_y = 512
        
        # Render each frame
        for frame, filename in RENDER_FRAMES.items():
            try:
                # Set frame
                bpy.context.scene.frame_current = frame
                
                # Set output path
                output_path = os.path.join(RENDER_OUTPUT_DIR, filename)
                bpy.context.scene.render.filepath = output_path
                
                # Render
                logging.info(f"Rendering frame {frame} to {output_path}")
                bpy.ops.render.render(write_still=True)
                
                if os.path.exists(output_path):
                    logging.info(f"Successfully rendered {filename}")
                else:
                    logging.warning(f"Render file not found after rendering: {output_path}")
                    
            except Exception as frame_error:
                logging.error(f"Error rendering frame {frame}: {frame_error}")
        
        # Restore original camera and frame
        bpy.context.scene.camera = current_camera
        bpy.context.scene.frame_current = current_frame
        
        logging.info("Multi-view render completed")
        return True
    except Exception as e:
        logging.error(f"Error in multi-view render: {e}")
        # Restore original camera and frame if possible
        try:
            if 'current_camera' in locals():
                bpy.context.scene.camera = current_camera
            if 'current_frame' in locals():
                bpy.context.scene.frame_current = current_frame
        except:
            pass
        return False

# Create and configure RenderCam function
def ensure_render_camera():
    """Create and configure the RenderCam if it doesn't exist"""
    render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
    
    if not render_cam:
        logging.info(f"Creating render camera: {RENDER_CAMERA_NAME}")
        bpy.ops.object.camera_add(location=(0, -10, 0), rotation=(math.radians(90), 0, 0))
        render_cam = bpy.context.active_object
        render_cam.name = RENDER_CAMERA_NAME
        
        # Configure camera settings
        render_cam.data.type = 'PERSP'
        render_cam.data.lens = 50
        render_cam.data.clip_start = 0.1
        render_cam.data.clip_end = 100
        
        # Create animation for the camera to rotate around
        render_cam.animation_data_create()
        render_cam.animation_data.action = bpy.data.actions.new(name="RenderCamAction")
        
        # Create the rotation track
        rot_curves = []
        for i in range(3):  # X, Y, Z
            fcurve = render_cam.animation_data.action.fcurves.new(data_path="rotation_euler", index=i)
            rot_curves.append(fcurve)
        
        # Set keyframes for each view
        # Frame 1: Front View (0 degrees)
        rot_curves[2].keyframe_points.insert(1, 0)
        # Frame 2: Right View (90 degrees)
        rot_curves[2].keyframe_points.insert(2, math.radians(90))
        # Frame 3: Back View (180 degrees)
        rot_curves[2].keyframe_points.insert(3, math.radians(180))
        # Frame 4: Left View (270 degrees)
        rot_curves[2].keyframe_points.insert(4, math.radians(270))
        # Frame 5: Back to Front (360/0 degrees)
        rot_curves[2].keyframe_points.insert(5, math.radians(360))
        
        logging.info("Render camera configured with rotation animation")
    else:
        logging.info(f"Render camera {RENDER_CAMERA_NAME} already exists")
    
    return render_cam

# Load images from disk function (internal, not exposed as an operator)
def load_images():
    # Define the path
    image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
    alt_image_dir = os.path.join(BASE_DIR, "input", "options")  # Alternative path format
    
    # Debug information
    logging.info(f"Attempting to load images from: {image_dir}")
    
    # Check if directory exists
    if not os.path.exists(image_dir):
        # Try alternative path format
        if os.path.exists(alt_image_dir):
            logging.info(f"Using alternative path format: {alt_image_dir}")
            image_dir = alt_image_dir
        else:
            logging.error(f"Image directory not found at: {image_dir} or {alt_image_dir}")
            # Try to create the directory
            try:
                os.makedirs(image_dir, exist_ok=True)
                logging.info(f"Created image directory: {image_dir}")
            except Exception as e:
                logging.error(f"Failed to create image directory: {e}")
                return []
    
    # Log directory contents
    try:
        dir_contents = os.listdir(image_dir)
        logging.info(f"Directory contents of {image_dir}: {dir_contents}")
    except Exception as e:
        logging.error(f"Error listing directory contents: {e}")
    
    # List of image names to look for
    image_names = ['A.png', 'B.png', 'C.png']
    
    # Check which ComfyUI output directory also exists
    comfyui_output = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"
    if os.path.exists(comfyui_output):
        try:
            comfyui_files = os.listdir(comfyui_output)
            logging.info(f"ComfyUI output directory contents: {comfyui_files}")
            # Look for any image files that could be copied
            for file in comfyui_files:
                if file.endswith('.png') and file.startswith(('A', 'B', 'C')):
                    source_path = os.path.join(comfyui_output, file)
                    target_path = os.path.join(image_dir, file[0] + '.png')  # Just use the first letter + .png
                    try:
                        shutil.copy2(source_path, target_path)
                        logging.info(f"Copied {file} from ComfyUI output to {target_path}")
                    except Exception as e:
                        logging.error(f"Failed to copy file: {e}")
        except Exception as e:
            logging.error(f"Error checking ComfyUI output: {e}")
    
    loaded_images = []
    for img_name in image_names:
        img_path = os.path.join(image_dir, img_name)
        logging.info(f"Attempting to load image from: {img_path}")
        
        if os.path.exists(img_path):
            try:
                # Try to load image if not already loaded
                if img_name not in bpy.data.images:
                    img = bpy.data.images.load(filepath=img_path, check_existing=False)
                    img.name = img_name
                    if not img.packed_file:
                        img.pack()
                    loaded_images.append(img)
                    logging.info(f"Successfully loaded image: {img_name}")
                else:
                    # Reload the image from disk
                    bpy.data.images[img_name].reload()
                    loaded_images.append(bpy.data.images[img_name])
                    logging.info(f"Reloaded existing image: {img_name}")
            except Exception as e:
                logging.error(f"Exception loading {img_path}: {str(e)}")
        else:
            logging.error(f"Image file not found: {img_path}")
    
    return loaded_images

# Create required directories
def ensure_directories():
    dirs = [
        os.path.join(BASE_DIR, "input", "options"),
        os.path.join(BASE_DIR, "input", "COMFYINPUTS", "blenderRender"),
        os.path.join(BASE_DIR, "input", "COMFYINPUTS", "textOptions"),
        os.path.join(BASE_DIR, "output"),
        os.path.join(BASE_DIR, "output", "generated", "Models")
    ]
    
    # Also try backslash versions as alternative
    alt_dirs = [
        os.path.join(BASE_DIR, "input", "options"),
        os.path.join(BASE_DIR, "input", "COMFYINPUTS", "blenderRender"),
        os.path.join(BASE_DIR, "input", "COMFYINPUTS", "textOptions"),
        os.path.join(BASE_DIR, "output"),
        os.path.join(BASE_DIR, "output", "generated", "Models")
    ]
    
    # Combine the sets
    all_dirs = dirs + alt_dirs
    
    for dir_path in all_dirs:
        try:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                logging.info(f"Created directory: {dir_path}")
            else:
                # Test write permissions
                try:
                    test_file = os.path.join(dir_path, "test_write.tmp")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    logging.info(f"Directory exists with write permission: {dir_path}")
                except Exception as e:
                    logging.error(f"Directory exists but has no write permission: {dir_path} - {e}")
        except Exception as e:
            logging.error(f"Failed to create directory: {dir_path} - {e}")
    
    # Log the current state of key directories
    key_dirs = [
        os.path.join(BASE_DIR, "input", "options"),
        os.path.join(BASE_DIR, "input", "options")
    ]
    
    for dir_path in key_dirs:
        if os.path.exists(dir_path):
            try:
                files = os.listdir(dir_path)
                logging.info(f"Contents of {dir_path}: {files}")
            except Exception as e:
                logging.error(f"Error listing contents of {dir_path}: {e}")
    
    # Create default prompt files if they don't exist
    default_prompts = {
        "A_0001.txt": "A sleek, futuristic sculpture with smooth curves and metallic surfaces, resembling a abstract interpretation of motion and energy.",
        "B_0001.txt": "An organic, biomechanical structure with intricate details and flowing forms, inspired by natural patterns and biological systems.",
        "C_0001.txt": "A crystalline geometric composition with sharp angles and faceted surfaces, showcasing mathematical precision and architectural complexity."
    }
    
    for filename, content in default_prompts.items():
        file_path = os.path.join(TEXT_OPTIONS_DIR, filename)
        if not os.path.exists(file_path):
            try:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logging.info(f"Created default prompt file: {filename}")
            except Exception as e:
                logging.error(f"Failed to create default prompt file {filename}: {e}")

def check_remesh_state():
    """Check the remesh state from the UI and update Blender properties"""
    try:
        # Use global BASE_DIR
        remesh_state_path = os.path.join(BASE_DIR, "remesh_state.txt")
        
        if not os.path.exists(remesh_state_path):
            logging.info("No remesh state file found")
            return
            
        # Parse the state file
        enabled = False
        stage = 1
        remesh_type = "SHARP"
        
        with open(remesh_state_path, "r") as f:
            for line in f:
                if line.startswith("enabled="):
                    enabled_text = line.strip().split("=")[1].lower()
                    enabled = (enabled_text == "true")
                elif line.startswith("stage="):
                    try:
                        stage = int(line.strip().split("=")[1])
                    except:
                        stage = 1
                elif line.startswith("type="):
                    remesh_type = line.strip().split("=")[1].upper()
        
        # Make sure the scene exists and has remesh_properties before updating
        if not hasattr(bpy.context, 'scene') or not bpy.context.scene:
            logging.error("Cannot update remesh state: No active scene")
            return
            
        if not hasattr(bpy.context.scene, 'remesh_properties'):
            logging.error("Cannot update remesh state: remesh_properties not found in scene")
            return
        
        # Update Blender properties
        try:
            bpy.context.scene.remesh_properties.enable_remesh = enabled
            bpy.context.scene.remesh_properties.current_stage = stage
            
            # Set remesh type if it's a valid value
            if remesh_type in ["BLOCKS", "SMOOTH", "SHARP"]:
                bpy.context.scene.remesh_properties.remesh_type = remesh_type
                
            logging.info(f"Updated remesh state: enabled={enabled}, stage={stage}, type={remesh_type}")
        except Exception as props_error:
            logging.error(f"Error updating remesh properties: {str(props_error)}")
        
        # Write back with updated values (in case Blender changed them)
        try:
            with open(remesh_state_path, "w") as f:
                f.write(f"enabled={str(bpy.context.scene.remesh_properties.enable_remesh).lower()}\n")
                f.write(f"stage={bpy.context.scene.remesh_properties.current_stage}\n")
                f.write(f"type={bpy.context.scene.remesh_properties.remesh_type}\n")
                f.write(f"timestamp={time.time()}\n")
        except Exception as write_error:
            logging.error(f"Error writing back remesh state: {str(write_error)}")
        
    except Exception as e:
        logging.error(f"Error checking remesh state: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())

def check_image_updates(operator_report_func, process):
    # Check if process is still running
    if process.poll() is None:
        # Process is still running, check again later
        logging.info("Still processing options...")
        return 2.0  # Check again in 2 seconds
    
    # Process completed, get output
    stdout, stderr = process.communicate()
    
    # Log the output
    if stdout:
        logging.info(f"options_API.py output: {stdout}")
    if stderr:
        logging.error(f"options_API.py errors: {stderr}")
    
    # Check return code
    if process.returncode != 0:
        if operator_report_func:
            try:
                operator_report_func({'ERROR'}, f"Error generating options: {stderr}")
            except ReferenceError:
                # If operator reference is no longer valid, just log the error
                logging.error(f"Error generating options: {stderr}")
    else:
        logging.info("Successfully generated new options")
        try:
            # Refresh images in UI
            refresh_images_from_disk()
            
            # Try to show a notification if the operator is still valid
            if operator_report_func:
                try:
                    operator_report_func({'INFO'}, "Images refreshed successfully")
                except ReferenceError:
                    # Just log if operator reference is no longer valid
                    logging.info("Images refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing images: {e}")
    
    return None  # Don't run again

# Function to refresh images from disk
def refresh_images_from_disk():
    """Refresh all option images from disk"""
    logging.info("Refreshing images from disk...")
    
    # Define the image directory
    image_dir = "C:/CODING/VIBE/VIBE_Forming/input/options"
    image_names = ['A.png', 'B.png', 'C.png']
    
    # Check if images exist on disk
    for img_name in image_names:
        img_path = os.path.join(image_dir, img_name)
        if os.path.exists(img_path):
            logging.info(f"Found image on disk: {img_path}")
            
            # Get existing image or create new one
            if img_name in bpy.data.images:
                # If the image already exists in Blender, reload it
                img = bpy.data.images[img_name]
                img.reload()
                logging.info(f"Reloaded existing image: {img_name}")
            else:
                # If not, load it from disk
                try:
                    img = bpy.data.images.load(img_path, check_existing=True)
                    img.name = img_name
                    if not img.packed_file:
                        img.pack()
                    logging.info(f"Loaded new image: {img_name}")
                except Exception as e:
                    logging.error(f"Error loading image {img_name}: {e}")
        else:
            logging.warning(f"Image not found on disk: {img_path}")
    
    # Force a redraw of all UI areas to show the updated images
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()
    
    logging.info("Image refresh completed")

# Add a new operator for submitting custom requests
class REQUEST_OT_submit(bpy.types.Operator):
    bl_idname = "request.submit"
    bl_label = "Submit Request"
    bl_description = "Submit custom request to generate new options"
    
    def execute(self, context):
        custom_prompt = context.scene.custom_request_properties.custom_prompt
        
        if not custom_prompt.strip():
            self.report({'ERROR'}, "Please enter a prompt before submitting")
            return {'CANCELLED'}
        
        logging.info(f"Submitting custom request: {custom_prompt}")
        
        # Step 1: Write to input.txt
        try:
            with open(INPUT_TEXT_FILE, 'w', encoding='utf-8') as f:
                f.write(custom_prompt)
            logging.info(f"Successfully wrote custom prompt to {INPUT_TEXT_FILE}")
        except Exception as e:
            logging.error(f"Failed to write to input.txt: {e}")
            self.report({'ERROR'}, f"Failed to save custom prompt: {str(e)}")
            return {'CANCELLED'}
        
        # Step 2: Render views
        render_success = render_multiview()
        if not render_success:
            self.report({'ERROR'}, "Failed to render multi-views")
            return {'CANCELLED'}
        
        # Step 3: Run options_API.py
        try:
            # Use absolute paths for both the script and working directory
            base_dir = BASE_DIR
            comfyworkflows_dir = os.path.join(base_dir, "src", "comfyworkflows")
            options_api_script = os.path.join(comfyworkflows_dir, "options_API.py")
            
            # Verify the paths exist
            if not os.path.exists(comfyworkflows_dir):
                logging.error(f"Comfyworkflows directory does not exist: {comfyworkflows_dir}")
                self.report({'ERROR'}, f"Directory not found: {comfyworkflows_dir}")
                return {'CANCELLED'}
            
            if not os.path.exists(options_api_script):
                logging.error(f"Script not found: {options_api_script}")
                self.report({'ERROR'}, f"Script not found: {options_api_script}")
                return {'CANCELLED'}
            
            # Create process to run options_API.py
            python_exe = sys.executable
            
            # Set up the command
            cmd = [python_exe, options_api_script]
            
            # Log the command for debugging
            logging.info(f"Running command: {' '.join(cmd)} in directory: {comfyworkflows_dir}")
            
            # Start the process
            process = subprocess.Popen(
                cmd, 
                cwd=comfyworkflows_dir,  # Set working directory to the comfyworkflows directory
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Display a message that processing has started
            self.report({'INFO'}, "Generating options, please wait...")
            
            # Create a report function that will use a weak reference to the operator
            report_func = self.report
            
            # Use a timer to periodically check if images have been updated
            bpy.app.timers.register(lambda: check_image_updates(report_func, process), first_interval=2.0)
            
            return {'FINISHED'}
            
        except Exception as e:
            logging.error(f"Failed to run options_API.py: {e}")
            self.report({'ERROR'}, f"Failed to generate options: {str(e)}")
            return {'CANCELLED'}

# Check for render requests from UI
def check_render_requests():
    """Check if there's a render request from the UI and process it"""
    if os.path.exists(RENDER_REQUEST_FILE):
        logging.info(f"Found render request file: {RENDER_REQUEST_FILE}")
        try:
            # Read request details
            with open(RENDER_REQUEST_FILE, 'r') as f:
                request_details = f.read()
                
            logging.info(f"Request details: {request_details}")
            
            # Delete the request file
            os.remove(RENDER_REQUEST_FILE)
            
            # Process the render
            success = render_multiview()
            
            # Write completion status
            with open(RENDER_COMPLETE_FILE, 'w') as f:
                if success:
                    f.write("SUCCESS")
                    logging.info("Render completed successfully")
                else:
                    f.write("ERROR: Render failed")
                    logging.info("Render failed")
                    
            return True
        except Exception as e:
            logging.error(f"Error processing render request: {e}")
            
            # Write error status
            try:
                with open(RENDER_COMPLETE_FILE, 'w') as f:
                    f.write(f"ERROR: {str(e)}")
            except:
                pass
                
            return False
    
    return False

# Check for import requests from UI
def check_import_requests():
    """Check for requests to import generated models"""
    try:
        # Use the global BASE_DIR, not a local definition
        request_path = os.path.join(BASE_DIR, "import_request.txt")
        
        if not os.path.exists(request_path):
            return False
            
        # Read the request file
        with open(request_path, "r") as f:
            request_content = f.read()
            
        # Delete the request file
        try:
            os.remove(request_path)
            logging.info(f"Deleted import request file")
        except Exception as e:
            logging.warning(f"Could not delete request file: {str(e)}")
        
        logging.info(f"Found import request: {request_content}")
        
        # Check remesh state from UI
        check_remesh_state()
        
        # Process the import
        success = import_generated_mesh()
        
        # Write completion status
        status_message = "SUCCESS" if success else "FAILURE"
        with open(os.path.join(BASE_DIR, "import_complete.txt"), "w") as f:
            f.write(f"Status: {status_message}\n")
            f.write(f"Timestamp: {time.time()}\n")
            
        return success
    except Exception as e:
        logging.error(f"Error checking import requests: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False

# Timer function to check for render and import requests
def check_requests_timer():
    """Timer function to periodically check for requests"""
    try:
        render_processed = check_render_requests()
        import_processed = check_import_requests()
        
        if render_processed:
            logging.info("Processed render request")
        if import_processed:
            logging.info("Processed import request")
            
        # Return the time interval for the next check (in seconds)
        return 2.0  # Check every 2 seconds
    except Exception as e:
        logging.error(f"Error in request timer: {e}")
        return 5.0  # Try again after 5 seconds if there was an error

# Registration function
def register():
    ensure_directories()
    
    # Register property groups
    bpy.utils.register_class(CustomRequestProperties)
    bpy.utils.register_class(PromptProperties)
    bpy.utils.register_class(RemeshProperties)
    bpy.types.Scene.prompt_properties = PointerProperty(type=PromptProperties)
    bpy.types.Scene.custom_request_properties = PointerProperty(type=CustomRequestProperties)
    bpy.types.Scene.remesh_properties = PointerProperty(type=RemeshProperties)
    
    # Register operators and panels
    bpy.utils.register_class(IMAGE_PT_display_panel)
    bpy.utils.register_class(OPTION_OT_select)
    bpy.utils.register_class(REQUEST_OT_submit)
    bpy.utils.register_class(IMAGE_OT_refresh)
    bpy.utils.register_class(OPTION_OT_terminate_script)
    bpy.utils.register_class(OBJECT_OT_generate_iteration)
    bpy.utils.register_class(OBJECT_OT_toggle_remesh)
    bpy.utils.register_class(REMESH_PT_settings_panel)

    # Create render camera
    ensure_render_camera()
    
    # Check the remesh state from UI
    check_remesh_state()
    
    # Load images on startup
    try:
        load_images()
        logging.info("Initial image loading completed")
    except Exception as e:
        logging.error(f"Failed to load images: {e}")
    
    # Apply default prompt A if prompt.txt doesn't exist
    prompt_path = os.path.join(TEXT_OPTIONS_DIR, PROMPT_FILE)
    if not os.path.exists(prompt_path):
        copy_text_file("A_0001.txt", PROMPT_FILE)
        logging.info("Applied default prompt A")
        
    # Start timer to check for render requests
    bpy.app.timers.register(check_requests_timer, first_interval=1.0)
        
    # Register additional Massing components
    try:
        register_massing()
    except Exception as e:
        logging.error(f"Error registering Massing components: {e}")
    logging.info("Successfully registered VIBE panel")

# Unregistration function
def unregister():
    try:
        # Unregister property groups
        del bpy.types.Scene.prompt_properties
        del bpy.types.Scene.custom_request_properties
        del bpy.types.Scene.remesh_properties
        
        # Unregister operators and panels
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(OPTION_OT_select)
        bpy.utils.unregister_class(REQUEST_OT_submit)
        bpy.utils.unregister_class(IMAGE_OT_refresh)
        bpy.utils.unregister_class(OPTION_OT_terminate_script)
        bpy.utils.unregister_class(OBJECT_OT_generate_iteration)
        bpy.utils.unregister_class(OBJECT_OT_toggle_remesh)
        bpy.utils.unregister_class(REMESH_PT_settings_panel)
        
        # Additionally unregister massing components
        try:
            unregister_massing()
        except Exception as e:
            logging.error(f"Error unregistering Massing components: {e}")
        logging.info("Successfully unregistered VIBE panel")
    except Exception as e:
        logging.error(f"Failed to unregister panel: {e}")

import bpy
import json
import math
import mathutils
import os
import time
import logging
import bmesh
from bpy.app.handlers import persistent
from pathlib import Path

# Global variables
original_volume = 1.0  # Default value in case calculation fails
view_layer_processed_objects = {}  # Track objects we've already tried to fix
VIEW_LAYER_PROCESS_TIMEOUT = 5.0  # Only try to fix an object's view layer every 5 seconds

# === IMAGE DISPLAY PANEL ===
class IMAGE_PT_reload_all(bpy.types.Operator):
    bl_idname = "image.reload_all"
    bl_label = "Reload All Images"
    bl_description = "Force reload all images from disk"
    
    def execute(self, context):
        # Use absolute path with forward slashes
        image_dir = "C:/CODING/VIBE/VIBE_Massing/output/generated/ImageOptions"
        image_names = ['A.png', 'B.png', 'C.png']
        
        logging.info(f"Reloading images from directory: {image_dir}")
        logging.info(f"Current working directory: {os.getcwd()}")
        
        # First remove existing images
        for img_name in image_names:
            if img_name in bpy.data.images:
                try:
                    bpy.data.images.remove(bpy.data.images[img_name])
                    logging.info(f"Removed existing image: {img_name}")
                except Exception as e:
                    logging.error(f"Error removing image {img_name}: {str(e)}")
        
        # Load fresh copies
        loaded_images = []
        for img_name in image_names:
            img_path = os.path.join(image_dir, img_name)
            logging.info(f"Attempting to load image from: {img_path}")
            
            if os.path.exists(img_path):
                logging.info(f"File exists: {img_path}")
                try:
                    # Try to load image
                    img = bpy.data.images.load(filepath=img_path, check_existing=False)
                    if img:
                        img.name = img_name
                        # Force reload
                        img.reload()
                        # Pack into .blend file
                        if not img.packed_file:
                            img.pack()
                        loaded_images.append(img)
                        logging.info(f"Successfully loaded image: {img_name} (size: {img.size[0]}x{img.size[1]})")
                    else:
                        logging.error(f"Failed to load image {img_name}: load returned None")
                except Exception as e:
                    logging.error(f"Exception loading {img_path}: {str(e)}")
            else:
                logging.error(f"Image file not found: {img_path}")
        
        logging.info(f"Successfully loaded {len(loaded_images)} images")
        logging.info(f"Images in bpy.data.images: {[img.name for img in bpy.data.images]}")
        
        # Force UI refresh
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
                logging.info("Tagged VIEW_3D area for redraw")
            
        return {'FINISHED'}

class IMAGE_MASSING_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_MASSING_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE Massing'

    def draw(self, context):
        layout = self.layout
        
        # Refresh button in a small row at top
        layout.operator("image.reload_all", text="Refresh All Images", icon='FILE_REFRESH')
        
        # Image directory
        image_dir = "C:/CODING/VIBE/VIBE_Massing/output/generated/ImageOptions"
        image_names = ['A.png', 'B.png', 'C.png']

        # Create a horizontal layout
        row = layout.row()
        
        # Load and display images side by side
        for img_name in image_names:
            # Create a column for each image
            col = row.column(align=True)  # Align items in column
            col.scale_x = 1.0
            col.scale_y = 1.0
            
            # Get or load image
            img = bpy.data.images.get(img_name)
            if not img:
                try:
                    img_path = os.path.join(image_dir, img_name)
                    if os.path.exists(img_path):
                        img = bpy.data.images.load(img_path)
                        img.name = img_name
                        if not img.packed_file:
                            img.pack()
                except Exception as e:
                    col.label(text=f"Error: {str(e)}")
                    continue
            
            if img:
                # Ensure preview is generated
                if img.preview is None:
                    img.preview_ensure()
                    
                if img.preview and img.preview.icon_id:
                    # Show the image preview
                    col.template_icon(icon_value=img.preview.icon_id, scale=8.0)
                    
                    # Add a "You like it?" button below each image
                    op = col.operator("option.select", text="You like it?")
                    op.option = img_name.split('.')[0]  # Pass A, B, or C as the option

def register_image_panel():
    try:
        logging.info("Registering image panel...")
        # Clear any existing images first
        for img_name in ['A.png', 'B.png', 'C.png']:
            if img_name in bpy.data.images:
                try:
                    bpy.data.images.remove(bpy.data.images[img_name])
                    logging.info(f"Removed existing image: {img_name}")
                except Exception as e:
                    logging.error(f"Error removing image {img_name}: {str(e)}")
        
        bpy.utils.register_class(IMAGE_PT_reload_all)
        bpy.utils.register_class(IMAGE_MASSING_PT_display_panel)
        logging.info("Successfully registered image panel classes")
        
        # Try to load images immediately after registration
        try:
            bpy.ops.image.reload_all('EXEC_DEFAULT')
            logging.info("Initial image reload completed")
        except Exception as e:
            logging.error(f"Failed to perform initial image reload: {e}")
            
    except Exception as e:
        logging.error(f"Failed to register image panel: {e}")

def unregister_image_panel():
    try:
        bpy.utils.unregister_class(IMAGE_MASSING_PT_display_panel)
        bpy.utils.unregister_class(IMAGE_PT_reload_all)
        logging.info("Successfully unregistered image panel")
    except Exception as e:
        logging.error(f"Failed to unregister image panel: {e}")

# === CONFIGURATION ===
LIVE_DATA_FILE = "C:/CODING/VIBE/VIBE_Massing/output/live_hand_data.json"  # JSON file from capture script

# Deformation parameters
FINGER_INFLUENCE_RADIUS = 3.0        
FINGER_FORCE_STRENGTH = 0.55        
ANCHOR_FORCE_MULTIPLIER = 3.0        
MAX_DISPLACEMENT_PER_FRAME = 0.25    
MASS_COHESION_FACTOR = 0.62          
DEFORM_TIMESTEP = 0.05               
VOLUME_LOWER_LIMIT = 0.8             
VOLUME_UPPER_LIMIT = 1.2             

# Velocity-based deformation parameters
VELOCITY_TRACKING_FRAMES = 3         
VELOCITY_MAX_SPEED = 2.0             
VELOCITY_MIN_SPEED = 0.05            
VELOCITY_FORCE_MULTIPLIER = 0.15     
VELOCITY_SMOOTHING = 0.3             
VELOCITY_DIRECTION_WEIGHT = 0.8      

# Smoothing and anchor parameters
SMOOTHING_ALPHA = 0.1       
ROTATION_SPEED = 45

# Radius constants for influence areas
FINGER_AOE_RADIUS = 5.0     
ANCHOR_AOE_RADIUS = 5.0     

# Mapping scales (from normalized space to mesh space)
SCALE_X = 20.0              
SCALE_Y = 20.0              
SCALE_Z = 20.0              

# Debug visualization settings
MAX_FINGERS = 5             
MAX_FINGER_ORBS = 10        
MAX_ANCHOR_ORBS = 10        
ENABLE_DEBUG_ORBS = True    

# Remesh settings
REMESH_TYPES = ["Blocks", "Smooth", "Sharp", "Voxel", "NONE"]
DEFAULT_VOXEL_SIZE = 0.1
DEFAULT_OCTREE_DEPTH = 2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Global list for objects created by this script (for cleanup)
created_objects = []

# Name of the primary mesh that is deformed
DEFORM_OBJ_NAME = "DeformingMesh"

# Render configuration
RENDER_OUTPUT_DIR = os.path.join(BASE_DIR, "input", "COMFYINPUTS", "blenderRender")
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

# === OBJECT INITIALIZATION ===

def ensure_object_exists(name, create_func):
    obj = bpy.data.objects.get(name)
    if not obj:
        logging.info(f"Creating missing object: {name}")
        obj = create_func()
        obj.name = name
    else:
        logging.info(f"Found existing object: {name}")
    return obj

def create_default_mesh():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    update_remesh_modifier(obj, "Blocks")
    return obj

def create_orb_template(radius=0.2, segments=8):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, rings=segments)
    obj = bpy.context.active_object
    if "Orb_Material" not in bpy.data.materials:
        mat = bpy.data.materials.new("Orb_Material")
        mat.diffuse_color = (0.2, 0.8, 1.0, 0.7)
    else:
        mat = bpy.data.materials["Orb_Material"]
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj

def create_anchor_template(radius=0.4, segments=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, rings=segments)
    obj = bpy.context.active_object
    if "Anchor_Material" not in bpy.data.materials:
        mat = bpy.data.materials.new("Anchor_Material")
        mat.diffuse_color = (1.0, 0.3, 0.3, 0.8)
    else:
        mat = bpy.data.materials["Anchor_Material"]
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return obj

def compute_mesh_volume(obj: bpy.types.Object) -> float:
    mesh = obj.data
    volume = 0.0
    for poly in mesh.polygons:
        verts = [obj.matrix_world @ mesh.vertices[i].co for i in poly.vertices]
        for i in range(1, len(verts) - 1):
            v0, v1, v2 = verts[0], verts[i], verts[i+1]
            volume += v0.dot(v1.cross(v2)) / 6.0
    return abs(volume)

def map_to_3d_space(x_norm: float, y_norm: float, z_val: float) -> mathutils.Vector:
    mesh_x = -z_val * SCALE_X
    mesh_y = -(x_norm - 0.5) * SCALE_Y
    mesh_z = (0.5 - y_norm) * SCALE_Z
    return mathutils.Vector((mesh_x, mesh_y, mesh_z))

def map_to_camera_relative_space(x_norm: float, y_norm: float, z_val: float) -> mathutils.Vector:
    """Maps normalized coordinates to 3D space relative to camera view
    
    This function uses the Camera object to ensure mapping is always
    consistent from the user's perspective regardless of environment rotation.
    Includes a 45-degree rotation to the right to better align with user's perspective.
    """
    # Get basic mapping first (standard coordinate conversion)
    point = mathutils.Vector((-z_val * SCALE_X, -(x_norm - 0.5) * SCALE_Y, (0.5 - y_norm) * SCALE_Z))
    
    # Look for the Camera object (not RenderCam)
    camera = bpy.data.objects.get("Camera")
    if camera is not None:
        # Get the camera's world matrix, which includes its position and orientation
        cam_matrix = camera.matrix_world
        
        # Create a coordinate system based on the camera's orientation
        # The camera looks along the -Z axis in its local space
        cam_forward = -cam_matrix.to_3x3().col[2].normalized()  # -Z axis (forward direction)
        cam_right = cam_matrix.to_3x3().col[0].normalized()     # X axis (right direction)
        cam_up = cam_matrix.to_3x3().col[1].normalized()        # Y axis (up direction)
        
        # Apply 45-degree rotation around the camera's up axis (clockwise when looking down)
        angle_rad = math.radians(45)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        # Rotate the right and forward vectors around the up vector
        cam_right_rotated = cam_right * cos_angle + cam_forward * sin_angle
        cam_forward_rotated = -cam_right * sin_angle + cam_forward * cos_angle
        
        # Create a new point in camera-relative coordinates with the 45-degree rotation
        cam_relative_point = (
            cam_right_rotated * point.x +    # Right/left of camera (X) with 45° rotation
            cam_up * point.z +               # Above/below camera (Z mapped to Y)
            cam_forward_rotated * point.y    # Forward/back from camera (Y mapped to Z) with 45° rotation
        )
        
        logging.debug(f"Camera-relative mapping with 45° rotation: {point} -> {cam_relative_point}")
        return cam_relative_point
    
    # Fallback to older Env-based rotation if Camera isn't available
    env = bpy.data.objects.get("Env")
    if env is not None:
        # Create rotation matrix from environment's Z rotation
        angle_z = env.rotation_euler.z
        cos_z = math.cos(-angle_z)  # Negative to counteract the rotation
        sin_z = math.sin(-angle_z)
        
        # Apply rotation around Z axis to maintain camera-relative position
        x_rot = point.x * cos_z - point.y * sin_z
        y_rot = point.x * sin_z + point.y * cos_z
        
        return mathutils.Vector((x_rot, y_rot, point.z))
    
    # If neither Camera nor Env exists, return standard mapping
    return point

def recenter_mesh(mesh_obj):
    if not mesh_obj:
        logging.warning("recenter_mesh called with None object")
        return
    
    global view_layer_processed_objects
    current_time = time.time()
    
    # Check if we've tried to process this object recently to avoid flickering
    if mesh_obj.name in view_layer_processed_objects:
        last_process_time = view_layer_processed_objects[mesh_obj.name]
        # Only try again if enough time has passed
        if current_time - last_process_time < VIEW_LAYER_PROCESS_TIMEOUT:
            return
    
    try:
        # First verify the object still exists in bpy.data.objects
        if mesh_obj.name not in bpy.data.objects:
            logging.warning(f"Object {mesh_obj.name} no longer exists in bpy.data.objects")
            return
            
        # Check if the object is in the current view layer
        obj_in_view_layer = False
        for obj in bpy.context.view_layer.objects:
            if obj == mesh_obj:
                obj_in_view_layer = True
                break
        
        if not obj_in_view_layer:
            # Record that we're processing this object now
            view_layer_processed_objects[mesh_obj.name] = current_time
            
            # Try to add the object to the view layer if it's not there
            try:
                # First make sure it's linked to a collection that's in the view layer
                if not mesh_obj.users_collection:
                    bpy.context.scene.collection.objects.link(mesh_obj)
                    logging.info(f"Linked {mesh_obj.name} to scene collection")
                
                # Now ensure it's visible in the view layer
                for col in mesh_obj.users_collection:
                    if col.hide_viewport:
                        col.hide_viewport = False
                        logging.info(f"Made collection {col.name} visible in viewport")
                
                mesh_obj.hide_viewport = False
                logging.info(f"Made {mesh_obj.name} visible in viewport")
                
                # Verify object is now in the view layer
                obj_in_view_layer = False
                for obj in bpy.context.view_layer.objects:
                    if obj == mesh_obj:
                        obj_in_view_layer = True
                        break
                        
                if not obj_in_view_layer:
                    logging.warning(f"Object {mesh_obj.name} still not in view layer after linking attempt")
                    return
            except Exception as e:
                logging.error(f"Could not add {mesh_obj.name} to view layer: {e}")
                return
        
        # Now set as active and recenter
        bpy.context.view_layer.objects.active = mesh_obj
        bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_VOLUME', center='MEDIAN')
        logging.debug(f"Recentered {mesh_obj.name}")
    except Exception as e:
        logging.error(f"Error in recenter_mesh for {mesh_obj.name}: {e}")
        import traceback
        logging.error(traceback.format_exc())

def cleanup_created_objects() -> None:
    global created_objects
    logging.info(f"Cleaning up {len(created_objects)} created objects...")
    for obj in created_objects:
        try:
            if obj and obj.name in bpy.data.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as e:
            logging.error(f"Error removing object {obj.name if obj else 'None'}: {e}")
    created_objects = []
    patterns = ["fingerOrbs_new", "anchorOrb_new"]
    for obj in list(bpy.data.objects):
        for pattern in patterns:
            if pattern in obj.name:
                try:
                    bpy.data.objects.remove(obj, do_unlink=True)
                except Exception as e:
                    logging.error(f"Error removing pattern object {obj.name}: {e}")
    logging.info("Cleanup complete.")

def update_remesh_modifier(obj, remesh_type):
    if not obj:
        return
    for mod in list(obj.modifiers):
        if mod.type in ['REMESH', 'BEVEL']:
            obj.modifiers.remove(mod)
    if remesh_type != "NONE":
        remesh_mod = obj.modifiers.new(name="Remesh", type='REMESH')
        if remesh_type == "Blocks":
            remesh_mod.mode = 'BLOCKS'
        elif remesh_type == "Voxel":
            remesh_mod.mode = 'VOXEL'
            remesh_mod.voxel_size = DEFAULT_VOXEL_SIZE
        elif remesh_type == "Sharp":
            remesh_mod.mode = 'SHARP'
            remesh_mod.octree_depth = DEFAULT_OCTREE_DEPTH
        elif remesh_type == "Smooth":
            remesh_mod.mode = 'SMOOTH'
            remesh_mod.octree_depth = DEFAULT_OCTREE_DEPTH
            remesh_mod.use_smooth_shade = True
        
        # Ensure "remove_disconnected" is disabled for all remesh types
        try:
            remesh_mod.remove_disconnected = False
            logging.info("Successfully disabled 'remove_disconnected' for remesh modifier")
        except AttributeError:
            try:
                # Alternative attribute name in some Blender versions
                remesh_mod.use_remove_disconnected = False
                logging.info("Successfully disabled 'use_remove_disconnected' for remesh modifier")
            except:
                logging.warning("Could not disable 'remove_disconnected' - property may not exist in this Blender version")
        
        logging.info(f"Remesh updated to type: {remesh_type}")
    else:
        logging.info("Remesh disabled (NONE)")
    bevel_mod = obj.modifiers.new(name="Bevel", type='BEVEL')
    bevel_mod.width = 0.05
    bevel_mod.segments = 5
    bevel_mod.profile = 0.7
    bevel_mod.limit_method = 'NONE'
    bevel_mod.miter_outer = 'MITER_SHARP'
    bevel_mod.offset_type = 'PERCENT'
    bevel_mod.width_pct = 50
    logging.info("Bevel modifier added: width=0.05, segments=5, profile=0.7 (convex), offset_type=PERCENT")

def insert_deformation_keyframe(mesh_obj):
    if not mesh_obj:
        return
    
    global view_layer_processed_objects
    current_time = time.time()
    
    # Check if we've tried to process this object recently to avoid flickering
    if mesh_obj.name in view_layer_processed_objects:
        last_process_time = view_layer_processed_objects[mesh_obj.name]
        # Only try again if enough time has passed
        if current_time - last_process_time < VIEW_LAYER_PROCESS_TIMEOUT:
            return
    
    try:
        # Check if the object is in the current view layer
        obj_in_view_layer = False
        for obj in bpy.context.view_layer.objects:
            if obj == mesh_obj:
                obj_in_view_layer = True
                break
        
        if not obj_in_view_layer:
            # Record that we're processing this object now
            view_layer_processed_objects[mesh_obj.name] = current_time
            
            # Try to add the object to the view layer if it's not there
            try:
                # First make sure it's linked to a collection that's in the view layer
                if not mesh_obj.users_collection:
                    bpy.context.scene.collection.objects.link(mesh_obj)
                    logging.info(f"Linked {mesh_obj.name} to scene collection for keyframing")
                
                # Now ensure it's visible in the view layer
                for col in mesh_obj.users_collection:
                    if col.hide_viewport:
                        col.hide_viewport = False
                        logging.info(f"Made collection {col.name} visible in viewport for keyframing")
                
                mesh_obj.hide_viewport = False
                logging.info(f"Made {mesh_obj.name} visible in viewport for keyframing")
            except Exception as e:
                logging.error(f"Could not add {mesh_obj.name} to view layer for keyframing: {e}")
                return
        
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            mesh_obj.keyframe_insert(data_path="location")
            mesh_obj.keyframe_insert(data_path="rotation_euler")
            mesh_obj.keyframe_insert(data_path="scale")
            logging.debug(f"Inserted keyframes for {mesh_obj.name}")
        except Exception as e:
            logging.error(f"Failed to insert keyframes: {e}")
    except Exception as e:
        logging.error(f"Error in insert_deformation_keyframe for {mesh_obj.name}: {e}")

# Initialize required objects
try:
    # Templates and references for finger movement visualization
    # Ensure we have the necessary objects for our application
    
    # Create objects if needed
    deform_obj = ensure_object_exists(DEFORM_OBJ_NAME, create_default_mesh)
    finger_orb_template = ensure_object_exists("fingerOrb", lambda: create_orb_template())
    anchor_orb_template = ensure_object_exists("anchorOrb", lambda: create_anchor_template())
    
    # Don't recenter during initialization - will be handled by the modal operator
    # with a controlled interval to prevent flickering
    
    finger_orb_template.hide_viewport = True
    anchor_orb_template.hide_viewport = True
    
    try:
        mesh = deform_obj.data
        if mesh and hasattr(mesh, 'vertices') and len(mesh.vertices) > 0:
            original_vertices = [v.co.copy() for v in mesh.vertices]
            calculated_volume = compute_mesh_volume(deform_obj)
            if calculated_volume > 0:
                original_volume = calculated_volume
                logging.info(f"Original mesh volume: {original_volume:.3f}")
            else:
                logging.warning(f"Calculated volume is invalid: {calculated_volume}, using default value of {original_volume}")
        else:
            logging.warning(f"Mesh for {DEFORM_OBJ_NAME} is invalid, using default volume value of {original_volume}")
    except Exception as e:
        logging.error(f"Error calculating original volume: {e}, using default value of {original_volume}")
    
    logging.info("All objects in scene: " + ", ".join(obj.name for obj in bpy.data.objects))
except Exception as e:
    logging.error(f"Error during object initialization: {e}")

# ================================================================
# NEW FUNCTIONALITY: Create a Cube Outside and Then Join It In
# ================================================================

def create_cube_object(fingertips) -> bpy.types.Object:
    """
    Create a new cube object outside DeformingMesh.
    Its corners are positioned at the thumb and pinky fingertips, making
    the cube larger and more directly controlled by hand position.
    """
    if not fingertips or len(fingertips) < 5:
        return None
        
    # Get thumb and pinky positions
    thumb_pos = fingertips[0]
    pinky_pos = fingertips[4]
    thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
    pinky_3d = map_to_camera_relative_space(pinky_pos["x"], pinky_pos["y"], pinky_pos["z"])
    
    # Create a cube between these two points
    # First, calculate center and dimensions
    center = (thumb_3d + pinky_3d) / 2.0
    size_vector = thumb_3d - pinky_3d
    size = size_vector.length
    
    # Create cube at center
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    cube = bpy.context.active_object
    
    # Scale and orient the cube to match the fingertips
    if size < 0.001:  # Ensure minimum size
        size = 0.001
        
    # Scale to match the distance between fingers
    cube.scale = (size, size, size)
    
    # Rotate 45 degrees around Z for visual consistency
    cube.rotation_euler.z = math.radians(45)
    cube.name = "Cube"
    
    logging.info(f"Created new cube at {center} with size {size:.4f} and 45° rotation.")
    return cube

def update_cube_object(cube, thumb_tip, pinky_tip):
    """
    Update the cube's size and position dynamically based on the thumb and pinky fingertips.
    The cube will stretch between these two points in 3D space.
    """
    if not cube:
        return
        
    # Get 3D positions of thumb and pinky
    thumb_3d = map_to_camera_relative_space(thumb_tip["x"], thumb_tip["y"], thumb_tip["z"])
    pinky_3d = map_to_camera_relative_space(pinky_tip["x"], pinky_tip["y"], pinky_tip["z"])
    
    # Calculate new center
    new_center = (thumb_3d + pinky_3d) / 2.0
    
    # Calculate size based on distance between fingertips
    size_vector = thumb_3d - pinky_3d
    size = size_vector.length
    
    # Ensure a minimum size
    if size < 0.001:
        size = 0.001
    
    # Update cube location and scale
    cube.location = new_center
    cube.scale = (size, size, size)
    
    # Maintain rotation
    cube.rotation_euler.z = math.radians(45)
    
    logging.info(f"Updated cube: center={new_center}, size={size:.4f}")
    return cube

def join_cube_to_deformingmesh(cube_obj):
    """
    Join the cube object into the DeformingMesh object.
    """
    deform_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
    if not deform_obj or not cube_obj:
        return
    bpy.ops.object.select_all(action='DESELECT')
    deform_obj.select_set(True)
    cube_obj.select_set(True)
    bpy.context.view_layer.objects.active = deform_obj
    bpy.ops.object.join()
    logging.info("Cube joined to DeformingMesh.")

# ================================================================
# REAL-TIME MODAL OPERATOR
# ================================================================

class REALTIME_OT_update_mesh(bpy.types.Operator):
    bl_idname = "wm.realtime_update_mesh"
    bl_label = "Real-time Mesh Update Operator"

    _timer = None

    right_fingertips = None
    left_fingertips = None
    smoothed_right_fingertips = None
    smoothed_left_fingertips = None

    _anchors = []
    smoothed_anchors = []

    mode = "none"        # Modes: none, rotate, deform, scale, create, anchor, remesh, render
    last_command = "none"
    prev_mode = "none"

    deform_active = False
    render_created_objects = []

    rotation_value = 0.0
    rotation_speed = 0.0
    last_rotation_update = 0.0
    last_recenter_time = 0.0  # Track when we last recentered to avoid flickering

    current_scale = mathutils.Vector((1.0, 1.0, 1.0))
    scale_axis = "XYZ"
    scale_start_thumb_z = None

    current_remesh_index = 0
    remesh_last_toggle_time = 0

    finger_orbs = []
    anchor_orbs = []

    prev_right_fingertips = None
    prev_left_fingertips = None
    finger_velocities = None
    last_velocity_update = 0
    use_velocity_forces = True

    # For "create" mode
    create_triggered = False
    created_cube = None

    def anchored_points(self) -> list:
        return self.smoothed_anchors

    def smooth_points(self, new_points, old_points, alpha=SMOOTHING_ALPHA):
        if not old_points or len(old_points) != len(new_points):
            return new_points.copy() if new_points else []
        smoothed = []
        for i, new_point in enumerate(new_points):
            old_point = old_points[i]
            sp = {
                'x': (1.0 - alpha) * old_point['x'] + alpha * new_point['x'],
                'y': (1.0 - alpha) * old_point['y'] + alpha * new_point['y'],
                'z': (1.0 - alpha) * old_point.get('z', 0) + alpha * new_point.get('z', 0)
            }
            smoothed.append(sp)
        return smoothed

    def safely_create_debug_orb(self, template_name):
        global created_objects
        try:
            template = bpy.data.objects.get(template_name)
            if template is None:
                logging.warning(f"Template '{template_name}' not found, creating fallback")
                if "anchor" in template_name.lower():
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, segments=12)
                else:
                    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.2, segments=8)
                new_orb = bpy.context.active_object
            else:
                new_orb = template.copy()
                if template.data:
                    new_orb.data = template.data.copy()
                bpy.context.collection.objects.link(new_orb)
            new_orb.hide_viewport = False
            created_objects.append(new_orb)
            return new_orb
        except Exception as e:
            logging.error(f"Error creating debug orb: {e}")
            try:
                size = 0.6 if "anchor" in template_name.lower() else 0.3
                bpy.ops.mesh.primitive_cube_add(size=size)
                new_orb = bpy.context.active_object
                created_objects.append(new_orb)
                return new_orb
            except Exception as e2:
                logging.error(f"Fallback cube creation failed: {e2}")
                return None

    def update_fixed_debug_orbs(self, mapped_points, orb_list, template_name, max_count, color=None):
        try:
            if not orb_list:
                logging.info(f"Creating {max_count} debug orbs for {template_name}")
                for _ in range(max_count):
                    new_orb = self.safely_create_debug_orb(template_name)
                    if new_orb:
                        if color and new_orb.material_slots and len(new_orb.material_slots) > 0:
                            if new_orb.material_slots[0].material:
                                new_orb.material_slots[0].material.diffuse_color = color
                        orb_list.append(new_orb)
            if len(orb_list) < max_count:
                additional_needed = max_count - len(orb_list)
                logging.info(f"Need {additional_needed} more orbs for {template_name}")
                for _ in range(additional_needed):
                    new_orb = self.safely_create_debug_orb(template_name)
                    if new_orb:
                        orb_list.append(new_orb)
            for i, orb in enumerate(orb_list):
                if i < len(mapped_points) and orb:
                    try:
                        orb.location = mapped_points[i]
                        orb.hide_viewport = False
                    except Exception as ex:
                        logging.error(f"Error setting orb {i} position: {ex}")
                elif orb:
                    orb.hide_viewport = True
        except Exception as e:
            logging.error(f"Error updating debug orbs: {e}")

    def rotate_mesh(self, angle_degrees):
        angle_radians = math.radians(angle_degrees)
        rotation_matrix = mathutils.Matrix.Rotation(angle_radians, 4, 'Z')
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        for i, v in enumerate(mesh.vertices):
            original_pos = original_vertices[i]
            v.co = rotation_matrix @ original_pos
        mesh.update()
        recenter_mesh(mesh_obj)
        insert_deformation_keyframe(mesh_obj)

    def calculate_finger_velocities(self, current_fingertips, previous_fingertips, delta_time):
        if not current_fingertips or not previous_fingertips or len(current_fingertips) != len(previous_fingertips):
            return [mathutils.Vector((0, 0, 0)) for _ in range(len(current_fingertips) if current_fingertips else 0)]
        velocities = []
        for i, (curr, prev) in enumerate(zip(current_fingertips, previous_fingertips)):
            curr_pos = map_to_camera_relative_space(curr["x"], curr["y"], curr["z"])
            prev_pos = map_to_camera_relative_space(prev["x"], prev["y"], prev["z"])
            if delta_time > 0:
                velocity = (curr_pos - prev_pos) / delta_time
            else:
                velocity = mathutils.Vector((0, 0, 0))
            speed = velocity.length
            if speed > VELOCITY_MAX_SPEED:
                velocity = velocity.normalized() * VELOCITY_MAX_SPEED
            if speed < VELOCITY_MIN_SPEED:
                velocity = mathutils.Vector((0, 0, 0))
            velocities.append(velocity)
        if self.finger_velocities and len(self.finger_velocities) == len(velocities):
            for i, (curr_vel, prev_vel) in enumerate(zip(velocities, self.finger_velocities)):
                velocities[i] = curr_vel * VELOCITY_SMOOTHING + prev_vel * (1 - VELOCITY_SMOOTHING)
        return velocities

    def create_render_copy(self):
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.error("DeformingMesh not found, cannot create render copy")
            return None
        try:
            render_copy = mesh_obj.copy()
            if mesh_obj.data:
                render_copy.data = mesh_obj.data.copy()
            render_copy.name = f"Render_{len(self.render_created_objects):03d}"
            bpy.context.collection.objects.link(render_copy)
            render_copy.location = mesh_obj.location.copy()
            render_copy.rotation_euler = mesh_obj.rotation_euler.copy()
            render_copy.scale = mesh_obj.scale.copy()
            self.render_created_objects.append(render_copy)
            logging.info(f"Created render copy: {render_copy.name}")
            return render_copy
        except Exception as e:
            logging.error(f"Error creating render copy: {e}")
            return None

    def deform_mesh_with_velocity(self, fingertips, velocities, anchors=None):
        if not fingertips or not velocities:
            return
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        if not mesh:
            logging.error(f"Mesh data for {DEFORM_OBJ_NAME} is None")
            return
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        finger_points = []
        for tip in fingertips:
            # Always use camera-relative mapping for consistent experience
            pos = map_to_camera_relative_space(tip["x"], tip["y"], tip["z"])
            finger_points.append(pos)
        anchor_points = []
        if anchors:
            for anchor in anchors:
                # Always use camera-relative mapping for consistent experience
                pos = map_to_camera_relative_space(anchor["x"], anchor["y"], anchor["z"])
                anchor_points.append(pos)
        if ENABLE_DEBUG_ORBS:
            self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
        def smooth_falloff(distance, radius):
            if distance >= radius:
                return 0.0
            normalized = distance / radius
            return (1.0 - normalized**2)**2
        world_matrix = mesh_obj.matrix_world
        world_matrix_inv = world_matrix.inverted()
        vertex_displacements = {}
        for v in bm.verts:
            v_world = world_matrix @ v.co
            net_displacement = mathutils.Vector((0, 0, 0))
            for finger_pos in finger_points:
                to_finger = finger_pos - v_world
                dist = to_finger.length
                if dist < FINGER_INFLUENCE_RADIUS:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS)
                    direction = to_finger.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH
                    net_displacement += force
            for anchor_pos in anchor_points:
                to_anchor = anchor_pos - v_world
                dist = to_anchor.length
                if dist < FINGER_INFLUENCE_RADIUS * 1.2:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS * 1.2)
                    direction = to_anchor.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH * ANCHOR_FORCE_MULTIPLIER
                    net_displacement += force
            if net_displacement.length > 0.0001:
                if net_displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                    net_displacement = net_displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
                vertex_displacements[v.index] = net_displacement
            else:
                vertex_displacements[v.index] = mathutils.Vector((0, 0, 0))
        smoothed_displacements = {}
        for v in bm.verts:
            if v.index not in vertex_displacements:
                continue
            original_displacement = vertex_displacements[v.index]
            neighbor_verts = [e.other_vert(v) for e in v.link_edges]
            if not neighbor_verts:
                smoothed_displacements[v.index] = original_displacement
                continue
            neighbor_avg = mathutils.Vector((0, 0, 0))
            for nv in neighbor_verts:
                if nv.index in vertex_displacements:
                    neighbor_avg += vertex_displacements[nv.index]
            if len(neighbor_verts) > 0:
                neighbor_avg /= len(neighbor_verts)
            smoothed_displacement = original_displacement.lerp(neighbor_avg, MASS_COHESION_FACTOR)
            smoothed_displacements[v.index] = smoothed_displacement
        for v in bm.verts:
            if v.index in smoothed_displacements:
                v_world = world_matrix @ v.co
                v_world += smoothed_displacements[v.index] * DEFORM_TIMESTEP
                v.co = world_matrix_inv @ v_world
        bm.to_mesh(mesh)
        mesh.update()
        
        try:
            current_volume = compute_mesh_volume(mesh_obj)
            volume_ratio = current_volume / original_volume
            logging.debug(f"Current volume: {current_volume:.3f}, Ratio: {volume_ratio:.3f}")
            
            if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
                if volume_ratio < VOLUME_LOWER_LIMIT:
                    target_ratio = VOLUME_LOWER_LIMIT
                    logging.debug(f"Volume too small: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                else:
                    target_ratio = VOLUME_UPPER_LIMIT
                    logging.debug(f"Volume too large: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                scale_factor = (target_ratio / volume_ratio) ** (1/3)
                bm_corrected = bmesh.new()
                bm_corrected.from_mesh(mesh)
                total = mathutils.Vector((0, 0, 0))
                for v in bm_corrected.verts:
                    total += v.co
                centroid = total / len(bm_corrected.verts)
                for v in bm_corrected.verts:
                    v.co = centroid + (v.co - centroid) * scale_factor
                bm_corrected.to_mesh(mesh)
                mesh.update()
                bm_corrected.free()
                
                corrected_volume = compute_mesh_volume(mesh_obj)
                corrected_ratio = corrected_volume / original_volume
                logging.debug(f"Volume after correction: {corrected_volume:.3f}, Ratio: {corrected_ratio:.3f}")
        except Exception as e:
            logging.error(f"Error during volume calculations/correction: {e}")
        
        recenter_mesh(mesh_obj)
        bm.free()
        insert_deformation_keyframe(mesh_obj)

    def scale_mesh(self, fingertips, axis="XYZ"):
        if not fingertips or len(fingertips) < 5:
            return
            
        # Get thumb position and ring finger position
        thumb_pos = fingertips[0]
        ring_pos = fingertips[3]
        
        # Always use camera-relative coordinates for calculations
        thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
        ring_3d = map_to_camera_relative_space(ring_pos["x"], ring_pos["y"], ring_pos["z"])
        
        # Store initial thumb z position when entering scale mode
        if self.prev_mode != "scale" and self.mode == "scale":
            self.scale_start_thumb_z = thumb_3d.z
            logging.info(f"Scale mode entered, reference z: {self.scale_start_thumb_z:.4f}")
        
        # If we have a reference z position, use it to calculate the scale factor
        if hasattr(self, 'scale_start_thumb_z'):
            # Calculate scale factor based on relative change in z position
            # This makes scaling more intuitive and less sensitive
            z_diff = abs(thumb_3d.z - self.scale_start_thumb_z)
            # Use a slower scaling factor (2.0 instead of 5.0)
            scale_factor = 1.0 + (z_diff * 2.0)
            
            # Cap the scale factor at 3.0 to prevent excessive scaling
            scale_factor = min(scale_factor, 3.0)
        else:
            # Fallback to distance-based scaling with reduced sensitivity
            distance = (thumb_3d - ring_3d).length
            scale_factor = 1.0 + (distance * 2.0)
            scale_factor = min(scale_factor, 3.0)
        
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        
        new_scale = mesh_obj.scale.copy()
        if axis == "X" or axis == "XYZ":
            new_scale.x = scale_factor
        if axis == "Y" or axis == "XYZ":
            new_scale.y = scale_factor
        if axis == "Z" or axis == "XYZ":
            new_scale.z = scale_factor
        
        mesh_obj.scale = new_scale
        self.current_scale = new_scale
        self.scale_axis = axis
        
        # Add visual feedback for scale factor
        # Update finger orb colors to show scale intensity (blue->green->yellow->red)
        if ENABLE_DEBUG_ORBS and self.finger_orbs:
            # Normalize the scale factor to 0-1 range (1.0 to 3.0 becomes 0.0 to 1.0)
            norm_scale = (scale_factor - 1.0) / 2.0
            # Create color gradient based on scale factor: blue -> green -> yellow -> red
            if norm_scale < 0.33:
                # Blue to green (0.0 - 0.33)
                sub_norm = norm_scale / 0.33
                color = (0.0, sub_norm, 1.0, 0.7)
            elif norm_scale < 0.66:
                # Green to yellow (0.33 - 0.66)
                sub_norm = (norm_scale - 0.33) / 0.33
                color = (sub_norm, 1.0, 1.0 - sub_norm, 0.7)
            else:
                # Yellow to red (0.66 - 1.0)
                sub_norm = (norm_scale - 0.66) / 0.34
                color = (1.0, 1.0 - sub_norm, 0.0, 0.7)
            
            # Apply color to finger orbs to give visual feedback
            for orb in self.finger_orbs:
                if orb.material_slots and orb.material_slots[0].material:
                    orb.material_slots[0].material.diffuse_color = color
        
        # Display scale factor as text in 3D view
        self.display_scale_info(scale_factor, axis)
        
        recenter_mesh(mesh_obj)
        logging.info(f"Applied scale: {new_scale} on axis {axis}, factor: {scale_factor:.2f}")
        insert_deformation_keyframe(mesh_obj)

    def apply_scale(self):
        """Apply the current scale to the mesh object, resetting scale to 1"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return False
            
        try:
            # Select the object and make it active
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
            
            # Apply scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            
            # Update original vertices reference after applying scale
            global original_vertices
            original_vertices = [v.co.copy() for v in mesh_obj.data.vertices]
            
            logging.info("Scale applied to mesh object")
            return True
        except Exception as e:
            logging.error(f"Failed to apply scale: {e}")
            return False

    def display_scale_info(self, scale_factor, axis):
        """Display scale information temporarily in the 3D view"""
        # Create or update text object in 3D view
        text_name = "ScaleInfo"
        text_obj = bpy.data.objects.get(text_name)
        
        if text_obj is None:
            # Create text object if it doesn't exist
            if "Text" not in bpy.data.curves:
                text_data = bpy.data.curves.new(name="Text", type='FONT')
            else:
                text_data = bpy.data.curves["Text"]
            
            text_obj = bpy.data.objects.new(text_name, text_data)
            bpy.context.collection.objects.link(text_obj)
            
            # Position in top-right of view
            text_obj.location = (-5, 0, 8)
            text_obj.scale = (0.5, 0.5, 0.5)
            
            # Set color and alignment
            text_data.body_format[0].use_bold = True
            if not text_obj.material_slots:
                mat = bpy.data.materials.new(name="TextMaterial")
                text_obj.data.materials.append(mat)
                mat.diffuse_color = (1.0, 1.0, 1.0, 1.0)
        
        # Update text content
        text_obj.data.body = f"Scale: {scale_factor:.2f}x [{axis}]"
        
        # Make visible
        text_obj.hide_viewport = False
        
        # Schedule hiding after delay (will be updated continuously while in scale mode)
        self.scale_info_shown_time = time.time()

    def apply_sculpt_brush(self, fingertips, brush_type="GRAB"):
        """Map finger movements directly to Blender's sculpt brushes"""
        if not fingertips or len(fingertips) < 5:
            return
            
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
            
        # Switch to sculpt mode
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
            
        # Get the sculpt brush
        brush = bpy.context.tool_settings.sculpt.brush
        
        # Set the brush type based on finger position or a predefined mapping
        # For example, we could determine brush type by how many fingers are extended
        brush.sculpt_tool = brush_type
        
        # Calculate brush size based on distance between thumb and pinky
        if len(fingertips) >= 5:
            thumb_pos = fingertips[0]
            pinky_pos = fingertips[4]
            distance = math.sqrt(
                (thumb_pos["x"] - pinky_pos["x"]) ** 2 +
                (thumb_pos["y"] - pinky_pos["y"]) ** 2 +
                (thumb_pos["z"] - pinky_pos["z"]) ** 2
            )
            # Map the distance to a reasonable brush size range (5-50)
            brush_size = 5 + distance * 45
            brush.size = int(min(max(brush_size, 5), 50))
            
            # Calculate brush strength based on z-position (depth)
            # Deeper hand position = stronger brush effect
            avg_z = sum(tip["z"] for tip in fingertips) / len(fingertips)
            # Map z to a reasonable strength range (0.1-1.0)
            strength = 0.1 + avg_z * 0.9
            brush.strength = min(max(strength, 0.1), 1.0)
            
            logging.info(f"Sculpt brush applied: {brush_type}, size={brush.size}, strength={brush.strength:.2f}")
            
    def toggle_dynamic_topology(self):
        """Enable/disable dynamic topology for adaptive mesh detail"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
            
        # Switch to sculpt mode
        bpy.context.view_layer.objects.active = mesh_obj
        if bpy.context.mode != 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
            
        # Toggle dynamic topology
        try:
            if not hasattr(mesh_obj, "use_dynamic_topology_sculpting"):
                # In newer Blender versions, we need to check the scene settings
                if not bpy.context.scene.tool_settings.sculpt.use_dyntopo:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology enabled")
                else:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology disabled")
            else:
                # In older Blender versions
                if not mesh_obj.use_dynamic_topology_sculpting:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    logging.info("Dynamic topology enabled")
                else:
                    bpy.ops.sculpt.dynamic_topology_toggle()
                    
            # Configure dynamic topology settings
            if hasattr(bpy.context.scene.tool_settings.sculpt, "detail_type_method"):
                bpy.context.scene.tool_settings.sculpt.detail_type_method = 'CONSTANT'
                bpy.context.scene.tool_settings.sculpt.constant_detail = 12
                logging.info("Dynamic topology detail set to 12")
                
        except Exception as e:
            logging.error(f"Error toggling dynamic topology: {e}")
    
    def determine_brush_type(self, fingertips):
        """Determine sculpt brush type based on finger positions"""
        if not fingertips or len(fingertips) < 5:
            return "GRAB"  # Default brush
            
        # Count extended fingers (fingers that are straightened)
        # A simple heuristic: if finger tip's y position is less than thumb's y position,
        # the finger is considered extended
        thumb_y = fingertips[0]["y"]
        extended_count = sum(1 for tip in fingertips[1:] if tip["y"] < thumb_y)
        
        # Map extended fingers count to brush types
        brush_map = {
            0: "GRAB",     # Fist (no fingers extended) = grab brush
            1: "CLAY",     # One finger extended = clay brush
            2: "SMOOTH",   # Two fingers extended = smooth brush
            3: "CREASE",   # Three fingers extended = crease brush
            4: "FLATTEN"   # Four fingers extended = flatten brush
        }
        
        brush_type = brush_map.get(extended_count, "GRAB")
        logging.debug(f"Detected {extended_count} extended fingers, selected brush: {brush_type}")
        return brush_type
    
    def multi_select_objects(self, left_fingertips, right_fingertips):
        """Select multiple objects with bimanual gestures"""
        if not left_fingertips or not right_fingertips:
            return
            
        # Use index fingers of both hands to define a selection box
        left_index = left_fingertips[1]
        right_index = right_fingertips[1]
        
        # Map to 3D space with camera-relative coordinates
        left_pos = map_to_camera_relative_space(left_index["x"], left_index["y"], left_index["z"])
        right_pos = map_to_camera_relative_space(right_index["x"], right_index["y"], right_index["z"])
        
        # Calculate min/max coordinates to define a selection box
        min_x = min(left_pos.x, right_pos.x)
        max_x = max(left_pos.x, right_pos.x)
        min_y = min(left_pos.y, right_pos.y)
        max_y = max(left_pos.y, right_pos.y)
        min_z = min(left_pos.z, right_pos.z)
        max_z = max(left_pos.z, right_pos.z)
        
        # Ensure the box has some minimum size
        min_size = 0.5
        if max_x - min_x < min_size:
            center_x = (max_x + min_x) / 2
            min_x = center_x - min_size/2
            max_x = center_x + min_size/2
        if max_y - min_y < min_size:
            center_y = (max_y + min_y) / 2
            min_y = center_y - min_size/2
            max_y = center_y + min_size/2
        if max_z - min_z < min_size:
            center_z = (max_z + min_z) / 2
            min_z = center_z - min_size/2
            max_z = center_z + min_size/2
        
        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')
        
        # Find objects that intersect with the selection box
        for obj in bpy.context.visible_objects:
            if obj.type != 'MESH':
                continue
                
            # Check if object's bounding box intersects with our selection box
            obj_bb = obj.bound_box
            obj_min = mathutils.Vector((min(v[0] for v in obj_bb), min(v[1] for v in obj_bb), min(v[2] for v in obj_bb)))
            obj_max = mathutils.Vector((max(v[0] for v in obj_bb), max(v[1] for v in obj_bb), max(v[2] for v in obj_bb)))
            
            # Transform to world space
            obj_min = obj.matrix_world @ obj_min
            obj_max = obj.matrix_world @ obj_max
            
            # Check for intersection (simple AABB test)
            if (obj_min.x <= max_x and obj_max.x >= min_x and
                obj_min.y <= max_y and obj_max.y >= min_y and
                obj_min.z <= max_z and obj_max.z >= min_z):
                obj.select_set(True)
        
        # Set active object to any selected object
        selected_objects = bpy.context.selected_objects
        if selected_objects:
            bpy.context.view_layer.objects.active = selected_objects[0]
            logging.info(f"Selected {len(selected_objects)} objects with selection box")
        else:
            logging.info("No objects found within selection box")
            
    def apply_boolean_operation(self, operation="UNION"):
        """Apply boolean operation between selected objects"""
        selected_objects = bpy.context.selected_objects
        if len(selected_objects) < 2:
            logging.warning("Need at least 2 selected objects for boolean operation")
            return
            
        # The active object will be the target
        target = bpy.context.active_object
        if target not in selected_objects:
            target = selected_objects[0]
            bpy.context.view_layer.objects.active = target
            
        # All other selected objects will be the operands
        operands = [obj for obj in selected_objects if obj != target]
        
        # Apply boolean modifiers
        for operand in operands:
            bool_mod = target.modifiers.new(name="Boolean", type='BOOLEAN')
            bool_mod.operation = operation
            bool_mod.object = operand
            
            try:
                # Apply the modifier
                bpy.ops.object.modifier_apply(modifier=bool_mod.name)
                # Hide the operand after applying boolean
                operand.hide_viewport = True
                logging.info(f"Applied {operation} boolean with {operand.name}")
            except Exception as e:
                logging.error(f"Boolean operation failed: {e}")
                
    def duplicate_object(self, fingertips):
        """Create a duplicate of the selected object at the new finger position"""
        try:
            # Get active object
            active_obj = bpy.context.active_object
            if not active_obj:
                logging.warning("No active object to duplicate")
                return None
            
            # Create a duplicate
            bpy.ops.object.duplicate_move()
            duplicate_obj = bpy.context.active_object
            
            # Move the duplicate based on thumb position
            thumb_pos = fingertips[0]
            thumb_3d = map_to_camera_relative_space(thumb_pos["x"], thumb_pos["y"], thumb_pos["z"])
            
            # Calculate offset based on original location and thumb position
            offset = thumb_3d - active_obj.location
            duplicate_obj.location = active_obj.location + offset
            
            logging.info(f"Duplicated {active_obj.name} to {duplicate_obj.name}")
            return duplicate_obj
        except Exception as e:
            logging.error(f"Object duplication failed: {e}")
            return None

    def create_new_object(self, fingertips):
        """Create a new cube object based on finger positions.
        
        When the user enters create mode, a cube is created between thumb and pinky.
        As the user moves their hand in create mode, the cube is dynamically updated.
        The cube is only joined to DeformingMesh when the user exits create mode.
        """
        if not fingertips or len(fingertips) < 5:
            return
            
        if not self.create_triggered:
            # Create a new cube between thumb and pinky positions
            new_cube = create_cube_object(fingertips)
            self.created_cube = new_cube
            
            if new_cube:
                # Mark as triggered so we don't create multiple cubes while in create mode
                self.create_triggered = True
                logging.info("Created new cube, ready for positioning")
        elif self.created_cube:
            # Update the cube's size and position based on thumb and pinky
            update_cube_object(self.created_cube, 
                             fingertips[0], 
                             fingertips[4])
            logging.debug("Updated cube position and size")

    def join_created_cube(self):
        """Join the created cube into the DeformingMesh object when exiting create mode."""
        if self.created_cube is None:
            return
            
        try:
            bpy.ops.object.select_all(action='DESELECT')
            deform_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
            if deform_obj and self.created_cube:
                deform_obj.select_set(True)
                self.created_cube.select_set(True)
                bpy.context.view_layer.objects.active = deform_obj
                bpy.ops.object.join()
                logging.info("Cube joined to DeformingMesh.")
                self.created_cube = None
                
                # Update original vertices reference after joining
                global original_vertices
                if deform_obj:
                    original_vertices = [v.co.copy() for v in deform_obj.data.vertices]
                    logging.info(f"Updated original_vertices reference with {len(original_vertices)} vertices")
        except Exception as e:
            logging.error(f"Failed to join cube: {e}")
            self.created_cube = None

    def cycle_remesh_type(self):
        self.current_remesh_index = (self.current_remesh_index + 1) % len(REMESH_TYPES)
        new_type = REMESH_TYPES[self.current_remesh_index]
        mesh_obj = bpy.data.objects.get("DeformingMesh")
        if mesh_obj:
            update_remesh_modifier(mesh_obj, new_type)
        logging.info(f"Switched remesh type to: {new_type}")
        return new_type
        
    def assign_material_to_selection(self, material_index=0):
        """Assign materials to vertices under influence of hand gestures"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj or not mesh_obj.data:
            logging.warning("No mesh object available for material assignment")
            return
            
        # Ensure object has materials
        if len(mesh_obj.data.materials) == 0:
            # Create default materials if none exist
            self.create_default_materials(mesh_obj)
            
        # Cap the material index to valid range
        material_index = min(material_index, len(mesh_obj.data.materials) - 1)
        if material_index < 0:
            logging.warning("Invalid material index")
            return
            
        # Switch to Edit mode for vertex selection
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
            
        # Use the currently influenced vertices for material assignment
        # This leverages the same vertex selection logic as in deformation
        mesh = mesh_obj.data
        bpy.ops.mesh.select_all(action='DESELECT')
        
        # Get current selection
        bm = bmesh.from_edit_mesh(mesh)
        bm.faces.ensure_lookup_table()
        
        # Select faces under influence (simplified example - would need to tie into deformation)
        for face in bm.faces:
            # Check if face is under hand influence - simplified example!
            # In a real implementation, use the same logic as your deformation system
            face.select = True
            
        # Assign selected faces to material
        if hasattr(bpy.context, 'object') and hasattr(bpy.context.object, 'active_material_index'):
            bpy.context.object.active_material_index = material_index
            bpy.ops.object.material_slot_assign()
            logging.info(f"Assigned material {material_index} to selected faces")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
    
    def create_default_materials(self, obj):
        """Create a set of default materials for the object"""
        # Create some default materials with different colors
        materials = [
            ("Material_Red", (1.0, 0.1, 0.1, 1.0)),
            ("Material_Green", (0.1, 0.8, 0.1, 1.0)),
            ("Material_Blue", (0.1, 0.1, 0.8, 1.0)),
            ("Material_Yellow", (0.9, 0.9, 0.1, 1.0)),
            ("Material_White", (0.9, 0.9, 0.9, 1.0))
        ]
        
        # Create and assign materials
        for mat_name, color in materials:
            # Check if material already exists
            if mat_name in bpy.data.materials:
                mat = bpy.data.materials[mat_name]
            else:
                # Create new material
                mat = bpy.data.materials.new(name=mat_name)
                mat.diffuse_color = color
                
            # Append material to object
            if obj.data.materials:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
                
        logging.info(f"Created {len(materials)} default materials for {obj.name}")
    
    def precise_scale(self, axis, value):
        """Apply precise numerical scaling based on voice commands"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for precise scaling")
            return
            
        # Ensure value is within reasonable range
        value = min(max(value, 0.01), 10.0)
        
        # Apply scaling based on axis
        if axis.upper() == "X":
            mesh_obj.scale.x = value
            logging.info(f"Set X scale to {value}")
        elif axis.upper() == "Y":
            mesh_obj.scale.y = value
            logging.info(f"Set Y scale to {value}")
        elif axis.upper() == "Z":
            mesh_obj.scale.z = value
            logging.info(f"Set Z scale to {value}")
        elif axis.upper() == "XYZ" or axis.upper() == "ALL":
            mesh_obj.scale = (value, value, value)
            logging.info(f"Set uniform scale to {value}")
        else:
            logging.warning(f"Unknown axis {axis} for precise scaling")
            
        # Update transformation
        recenter_mesh(mesh_obj)
        insert_deformation_keyframe(mesh_obj)
        
    def enable_snapping(self, snap_type="INCREMENT"):
        """Toggle different snapping modes with gestures"""
        valid_types = {"INCREMENT", "VERTEX", "EDGE", "FACE", "VOLUME", "EDGE_MIDPOINT", "EDGE_PERPENDICULAR"}
        
        if snap_type not in valid_types:
            snap_type = "INCREMENT"
            
        # Toggle snapping
        bpy.context.scene.tool_settings.use_snap = not bpy.context.scene.tool_settings.use_snap
        
        # If enabling, set the snap type
        if bpy.context.scene.tool_settings.use_snap:
            # Clear current snap elements
            for snap_elem in {'INCREMENT', 'VERTEX', 'EDGE', 'FACE', 'VOLUME', 'EDGE_MIDPOINT', 'EDGE_PERPENDICULAR'}:
                if hasattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_elem.lower()}"):
                    setattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_elem.lower()}", False)
            
            # Set the requested snap element
            if hasattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_type.lower()}"):
                setattr(bpy.context.scene.tool_settings, f"snap_elements_{snap_type.lower()}", True)
            else:
                # For older Blender versions
                bpy.context.scene.tool_settings.snap_element = snap_type
                
            logging.info(f"Snapping enabled with type: {snap_type}")
        else:
            logging.info("Snapping disabled")

    def extrude_selection(self, direction, distance=1.0):
        """Extrude selected faces in specified direction"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for extrusion")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in face selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        
        # Perform the extrusion
        try:
            # First extrude
            bpy.ops.mesh.extrude_region_move(
                TRANSFORM_OT_translate={
                    "value": (
                        direction.x * distance,
                        direction.y * distance, 
                        direction.z * distance
                    )
                }
            )
            logging.info(f"Extruded faces by distance {distance}")
        except Exception as e:
            logging.error(f"Extrusion failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
        
    def inset_faces(self, amount=0.1):
        """Inset selected faces"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for inset")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in face selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, False, True)
        
        # Perform the inset
        try:
            bpy.ops.mesh.inset(thickness=amount, depth=0)
            logging.info(f"Inset faces with thickness {amount}")
        except Exception as e:
            logging.error(f"Inset failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)

    def smooth_edge_flow(self, iterations=5):
        """Apply edge flow smoothing to selected edges"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for edge flow smoothing")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in edge selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        
        # Check if LoopTools is enabled
        if hasattr(bpy.ops, 'mesh') and hasattr(bpy.ops.mesh, 'looptools_relax'):
            try:
                bpy.ops.mesh.looptools_relax(
                    input='selected', 
                    interpolation='cubic',
                    iterations=iterations,
                    regular=True
                )
                logging.info(f"Applied edge flow smoothing with {iterations} iterations")
            except Exception as e:
                logging.error(f"Edge flow smoothing failed: {e}")
        else:
            # Fallback to Blender's native smooth
            try:
                bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=iterations)
                logging.info(f"Applied fallback smoothing with {iterations} iterations")
            except Exception as e:
                logging.error(f"Fallback smoothing failed: {e}")
                
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)
        
    def bridge_edge_loops(self):
        """Connect selected edge loops"""
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            logging.warning("No mesh object available for bridge loops")
            return
            
        # Ensure we're in edit mode
        bpy.context.view_layer.objects.active = mesh_obj
        current_mode = bpy.context.object.mode
        if current_mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        
        # Ensure we're in edge selection mode
        bpy.context.tool_settings.mesh_select_mode = (False, True, False)
        
        # Perform the bridge
        try:
            bpy.ops.mesh.bridge_edge_loops()
            logging.info("Bridge edge loops applied")
        except Exception as e:
            logging.error(f"Bridge edge loops failed: {e}")
            
        # Return to previous mode
        bpy.ops.object.mode_set(mode=current_mode)

    def read_live_data(self):
        if not os.path.exists(LIVE_DATA_FILE):
            logging.debug(f"Live data file not found at {LIVE_DATA_FILE}")
            return {}
        try:
            with open(LIVE_DATA_FILE, "r") as f:
                content = f.read().strip()
                if not content:
                    logging.debug("Live data file exists but is empty")
                    return {}
                return json.loads(content)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
        except Exception as e:
            logging.error(f"Error reading live data: {e}")
        return {}

    def deform_mesh(self, fingertips, anchors=None):
        """Deform the mesh based on finger positions without velocity information"""
        if not fingertips:
            return
        mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
        if not mesh_obj:
            return
        mesh = mesh_obj.data
        if not mesh:
            logging.error(f"Mesh data for {DEFORM_OBJ_NAME} is None")
            return
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        finger_points = []
        for tip in fingertips:
            # Always use camera-relative mapping for consistent experience
            pos = map_to_camera_relative_space(tip["x"], tip["y"], tip["z"])
            finger_points.append(pos)
        anchor_points = []
        if anchors:
            for anchor in anchors:
                # Always use camera-relative mapping for consistent experience
                pos = map_to_camera_relative_space(anchor["x"], anchor["y"], anchor["z"])
                anchor_points.append(pos)
        if ENABLE_DEBUG_ORBS:
            self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
        def smooth_falloff(distance, radius):
            if distance >= radius:
                return 0.0
            normalized = distance / radius
            return (1.0 - normalized**2)**2
        world_matrix = mesh_obj.matrix_world
        world_matrix_inv = world_matrix.inverted()
        vertex_displacements = {}
        for v in bm.verts:
            v_world = world_matrix @ v.co
            net_displacement = mathutils.Vector((0, 0, 0))
            for finger_pos in finger_points:
                to_finger = finger_pos - v_world
                dist = to_finger.length
                if dist < FINGER_INFLUENCE_RADIUS:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS)
                    direction = to_finger.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH
                    net_displacement += force
            for anchor_pos in anchor_points:
                to_anchor = anchor_pos - v_world
                dist = to_anchor.length
                if dist < FINGER_INFLUENCE_RADIUS * 1.2:
                    falloff = smooth_falloff(dist, FINGER_INFLUENCE_RADIUS * 1.2)
                    direction = to_anchor.normalized()
                    force = direction * falloff * FINGER_FORCE_STRENGTH * ANCHOR_FORCE_MULTIPLIER
                    net_displacement += force
            if net_displacement.length > 0.0001:
                if net_displacement.length > MAX_DISPLACEMENT_PER_FRAME:
                    net_displacement = net_displacement.normalized() * MAX_DISPLACEMENT_PER_FRAME
                vertex_displacements[v.index] = net_displacement
            else:
                vertex_displacements[v.index] = mathutils.Vector((0, 0, 0))
        smoothed_displacements = {}
        for v in bm.verts:
            if v.index not in vertex_displacements:
                continue
            original_displacement = vertex_displacements[v.index]
            neighbor_verts = [e.other_vert(v) for e in v.link_edges]
            if not neighbor_verts:
                smoothed_displacements[v.index] = original_displacement
                continue
            neighbor_avg = mathutils.Vector((0, 0, 0))
            for nv in neighbor_verts:
                if nv.index in vertex_displacements:
                    neighbor_avg += vertex_displacements[nv.index]
            if len(neighbor_verts) > 0:
                neighbor_avg /= len(neighbor_verts)
            smoothed_displacement = original_displacement.lerp(neighbor_avg, MASS_COHESION_FACTOR)
            smoothed_displacements[v.index] = smoothed_displacement
        for v in bm.verts:
            if v.index in smoothed_displacements:
                v_world = world_matrix @ v.co
                v_world += smoothed_displacements[v.index] * DEFORM_TIMESTEP
                v.co = world_matrix_inv @ v_world
        bm.to_mesh(mesh)
        mesh.update()
        
        try:
            current_volume = compute_mesh_volume(mesh_obj)
            volume_ratio = current_volume / original_volume
            logging.debug(f"Current volume: {current_volume:.3f}, Ratio: {volume_ratio:.3f}")
            
            if volume_ratio < VOLUME_LOWER_LIMIT or volume_ratio > VOLUME_UPPER_LIMIT:
                if volume_ratio < VOLUME_LOWER_LIMIT:
                    target_ratio = VOLUME_LOWER_LIMIT
                    logging.debug(f"Volume too small: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                else:
                    target_ratio = VOLUME_UPPER_LIMIT
                    logging.debug(f"Volume too large: {volume_ratio:.3f}, adjusting to {target_ratio:.3f}")
                scale_factor = (target_ratio / volume_ratio) ** (1/3)
                bm_corrected = bmesh.new()
                bm_corrected.from_mesh(mesh)
                total = mathutils.Vector((0, 0, 0))
                for v in bm_corrected.verts:
                    total += v.co
                centroid = total / len(bm_corrected.verts)
                for v in bm_corrected.verts:
                    v.co = centroid + (v.co - centroid) * scale_factor
                bm_corrected.to_mesh(mesh)
                mesh.update()
                bm_corrected.free()
                
                corrected_volume = compute_mesh_volume(mesh_obj)
                corrected_ratio = corrected_volume / original_volume
                logging.debug(f"Volume after correction: {corrected_volume:.3f}, Ratio: {corrected_ratio:.3f}")
        except Exception as e:
            logging.error(f"Error during volume calculations/correction: {e}")
        
        recenter_mesh(mesh_obj)
        bm.free()
        insert_deformation_keyframe(mesh_obj)

    def modal(self, context, event):
        if event.type == 'ESC' and event.value == 'PRESS':
            logging.info("Escape pressed. Cancelling operator.")
            return self.cancel(context)
        if event.type == 'D' and event.value == 'PRESS':
            self.mode = "deform" if self.mode != "deform" else "none"
            self.deform_active = (self.mode == "deform")
            logging.debug(f"Manual toggle: DEFORM = {self.mode == 'deform'}")
        if event.type == 'R' and event.value == 'PRESS':
            if event.shift:
                logging.debug("Manual multi-view render triggered with Shift+R")
                render_obj = self.create_render_copy()
                if render_obj:
                    bpy.context.view_layer.objects.active = render_obj
                    for modifier in render_obj.modifiers:
                        try:
                            bpy.ops.object.modifier_apply(modifier=modifier.name)
                        except Exception as e:
                            logging.error(f"Could not apply modifier {modifier.name}: {e}")
                    self.render_multiview()
            else:
                self.mode = "rotate" if self.mode != "rotate" else "none"
                logging.debug(f"Manual toggle: ROTATE = {self.mode == 'rotate'}")
        if event.type == 'S' and event.value == 'PRESS':
            if self.mode == "scale":
                # Apply scale when exiting scale mode
                self.apply_scale()
                self.mode = "none"
                # Reset the scale reference when exiting scale mode
                self.scale_start_thumb_z = None
                logging.debug("Exiting scale mode, applied current scale and reset reference")
                # Hide scale info text
                self.hide_scale_info()
            else:
                self.mode = "scale"
                # scale_start_thumb_z will be set in scale_mesh
            logging.debug(f"Manual toggle: SCALE = {self.mode == 'scale'}")
        if event.type == 'C' and event.value == 'PRESS':
            if self.mode == "create":
                # If we're exiting create mode, join the cube to DeformingMesh
                if self.created_cube:
                    self.join_created_cube()
                    logging.info("Joined cube to DeformingMesh when exiting create mode")
                self.create_triggered = False
                self.mode = "none"
            else:
                self.mode = "create"
            logging.debug(f"Manual toggle: CREATE = {self.mode == 'create'}")
        if event.type == 'A' and event.value == 'PRESS':
            self.mode = "anchor" if self.mode != "anchor" else "none"
            logging.debug(f"Manual toggle: ANCHOR = {self.mode == 'anchor'}")
        if event.type == 'M' and event.value == 'PRESS':
            self.cycle_remesh_type()
            logging.debug("Manual: Cycled remesh type")
        if event.type == 'V' and event.value == 'PRESS':
            self.use_velocity_forces = not self.use_velocity_forces
            logging.info(f"Velocity forces {'enabled' if self.use_velocity_forces else 'disabled'}")
        
        if event.type == 'TIMER':
            current_time = time.time()
            delta_time = current_time - self.last_rotation_update
            self.last_rotation_update = current_time
            
            # Check for import_command.json file
            import_command_path = os.path.join(os.path.dirname(LIVE_DATA_FILE), "import_command.json")
            if os.path.exists(import_command_path):
                try:
                    with open(import_command_path, 'r') as f:
                        import_command = json.load(f)
                    
                    # Process the import command
                    if import_command.get("command") == "import_mesh":
                        mesh_path = import_command.get("mesh_path")
                        remesh_type = import_command.get("remesh_type", "Blocks")
                        collection_settings = import_command.get("collection_settings", None)
                        
                        if mesh_path and os.path.exists(mesh_path):
                            logging.info(f"Processing import command for mesh: {mesh_path}")
                            
                            # Create or get the render collection if collection settings are provided
                            render_collection = None
                            if collection_settings:
                                collection_name = collection_settings.get("name", "VIBE_Renders")
                                instance_name = collection_settings.get("instance_name", f"Render_{len(bpy.data.collections.get(collection_name, {}).objects) if bpy.data.collections.get(collection_name) else 0}")
                                hide_viewport = collection_settings.get("hide_viewport", True)
                                hide_render = collection_settings.get("hide_render", True)
                                
                                # Create collection if it doesn't exist
                                if collection_name not in bpy.data.collections:
                                    render_collection = bpy.data.collections.new(collection_name)
                                    bpy.context.scene.collection.children.link(render_collection)
                                    logging.info(f"Created new collection: {collection_name}")
                                else:
                                    render_collection = bpy.data.collections[collection_name]
                                
                                # Apply collection settings
                                if render_collection:
                                    # Set the collection properties directly
                                    render_collection.hide_viewport = hide_viewport
                                    render_collection.hide_render = hide_render
                                    logging.info(f"Set collection properties: hide_viewport={hide_viewport}, hide_render={hide_render}")
                                    
                                    # Also set layer collection settings for each view layer
                                    for view_layer in bpy.context.scene.view_layers:
                                        layer_coll = view_layer.layer_collection
                                        found = False
                                        # Find the layer collection
                                        for child in layer_coll.children:
                                            if child.name == render_collection.name:
                                                child.hide_viewport = hide_viewport
                                                child.exclude = hide_render
                                                found = True
                                                logging.info(f"Set layer collection settings in view layer {view_layer.name}")
                                                break
                                        if not found:
                                            logging.warning(f"Could not find layer collection {render_collection.name} in view layer {view_layer.name}")
                            
                            # Delete existing deformingMesh if it exists
                            existing_mesh = bpy.data.objects.get(DEFORM_OBJ_NAME)
                            if existing_mesh:
                                # Save a copy to render collection if needed
                                if render_collection:
                                    # Get iteration from import command
                                    iteration = import_command.get("iteration", 0)
                                    iteration_name = f"iteration_{iteration:03d}"
                                    
                                    # First remove from current collections
                                    logging.info(f"Removing existing mesh from current collections")
                                    for col in existing_mesh.users_collection:
                                        col.objects.unlink(existing_mesh)
                                        logging.info(f"Unlinked from collection: {col.name}")
                                    
                                    # Create a copy with the iteration name
                                    render_obj = existing_mesh.copy()
                                    render_obj.data = existing_mesh.data.copy()
                                    render_obj.name = iteration_name
                                    logging.info(f"Created copy named: {iteration_name}")
                                    
                                    # Link to the render collection
                                    render_collection.objects.link(render_obj)
                                    logging.info(f"Linked {iteration_name} to collection {render_collection.name}")
                                    
                                    # Try to export to session folder
                                    session_dir = import_command.get("session_dir", "")
                                    if session_dir and os.path.isdir(session_dir):
                                        try:
                                            export_path = os.path.join(session_dir, f"{iteration_name}.glb")
                                            logging.info(f"Attempting to export to: {export_path}")
                                            
                                            # Select only the render object
                                            bpy.ops.object.select_all(action='DESELECT')
                                            render_obj.select_set(True)
                                            bpy.context.view_layer.objects.active = render_obj
                                            
                                            # Export as GLB
                                            bpy.ops.export_scene.gltf(
                                                filepath=export_path,
                                                use_selection=True,
                                                export_format='GLB'
                                            )
                                            logging.info(f"Successfully exported to: {export_path}")
                                        except Exception as e:
                                            logging.error(f"Error exporting GLB: {e}")
                                            import traceback
                                            logging.error(traceback.format_exc())
                                
                                # Now remove the original mesh
                                bpy.data.objects.remove(existing_mesh, do_unlink=True)
                                logging.info(f"Removed existing {DEFORM_OBJ_NAME}")
                            
                            # Import the new mesh
                            try:
                                # Import GLB file
                                logging.info(f"Importing new mesh from: {mesh_path}")
                                bpy.ops.import_scene.gltf(filepath=mesh_path)
                                imported_objects = [obj for obj in bpy.context.selected_objects]
                                logging.info(f"Imported {len(imported_objects)} objects")
                                
                                if imported_objects:
                                    # Set up the imported mesh as deformingMesh
                                    new_mesh = imported_objects[0]
                                    original_name = new_mesh.name
                                    new_mesh.name = DEFORM_OBJ_NAME
                                    logging.info(f"Renamed {original_name} to {DEFORM_OBJ_NAME}")
                                    
                                    # Ensure minimum dimensions of 4x4x4 meters
                                    try:
                                        ensure_minimum_dimensions(new_mesh, 4.0)
                                    except Exception as e:
                                        logging.error(f"Error ensuring minimum dimensions: {e}")
                                    
                                    # Apply the remesh modifier
                                    update_remesh_modifier(new_mesh, remesh_type)
                                    logging.info(f"Applied remesh modifier: {remesh_type}")
                                    
                                    # Make sure it's in the correct collection
                                    for col in new_mesh.users_collection:
                                        logging.info(f"Removing from collection: {col.name}")
                                        col.objects.unlink(new_mesh)
                                    bpy.context.scene.collection.objects.link(new_mesh)
                                    logging.info(f"Added to scene collection")
                                    
                                    # Center mesh
                                    try:
                                        recenter_mesh(new_mesh)
                                        logging.info(f"Recentered mesh")
                                    except Exception as e:
                                        logging.error(f"Failed to recenter newly imported mesh: {e}")
                                    
                                    # Update original_volume for the new mesh
                                    try:
                                        global original_volume
                                        calculated_volume = compute_mesh_volume(new_mesh)
                                        if calculated_volume > 0:
                                            original_volume = calculated_volume
                                            logging.info(f"Updated original mesh volume: {original_volume:.3f}")
                                        else:
                                            logging.warning(f"Calculated volume is invalid: {calculated_volume}, keeping previous value of {original_volume}")
                                    except Exception as e:
                                        logging.error(f"Error calculating new original volume: {e}")
                                    
                                    logging.info(f"Successfully set up {DEFORM_OBJ_NAME}")
                                else:
                                    logging.error(f"Failed to import objects from {mesh_path}")
                            except Exception as e:
                                logging.error(f"Error importing mesh: {e}")
                                import traceback
                                logging.error(traceback.format_exc())
                        else:
                            logging.error(f"Mesh path not found: {mesh_path}")
                    
                    # Remove the command file to avoid reprocessing
                    try:
                        os.remove(import_command_path)
                        logging.info(f"Removed processed import command file")
                    except Exception as e:
                        logging.error(f"Error removing import command file: {e}")
                
                except Exception as e:
                    logging.error(f"Error processing import command: {e}")
                    import traceback
                    logging.error(traceback.format_exc())
            
            data = self.read_live_data()
            if not data:
                return {'PASS_THROUGH'}
                
            json_deform_active = data.get("deform_active", None)
            if json_deform_active is not None:
                self.deform_active = json_deform_active

            command = data.get("command", "none")
            left_hand_data = data.get("left_hand")
            left = []
            if left_hand_data is not None and isinstance(left_hand_data, dict):
                left = left_hand_data.get("fingertips", [])
            right_hand_data = data.get("right_hand")
            right = []
            if right_hand_data is not None and isinstance(right_hand_data, dict):
                right = right_hand_data.get("fingertips", [])
            anchors_raw = data.get("anchors", [])
            rotation_value = data.get("rotation", 0.0)
            rotation_speed = data.get("rotation_speed", 0.0)
            scale_axis = data.get("scale_axis", "XYZ")
            remesh_type = data.get("remesh_type", REMESH_TYPES[0])
            
            if command != self.last_command:
                logging.debug(f"Command changed from '{self.last_command}' to '{command}'")
                # Apply scale and reset reference when changing modes via gesture/voice
                if self.last_command == "scale" and command != "scale":
                    self.apply_scale()
                    self.scale_start_thumb_z = None
                    self.hide_scale_info()
                    logging.debug("Exiting scale mode via command change, applied scale and reset reference")
                
                # Join cube to DeformingMesh when exiting create mode
                if self.last_command == "create" and command != "create":
                    if self.created_cube:
                        self.join_created_cube()
                        logging.info("Joined cube to DeformingMesh when exiting create mode")
                    self.create_triggered = False
                    logging.info("Exited create mode, reset for next cube creation")
                
                self.last_command = command
                self.mode = command
            
            # Hide scale info if we're not in scale mode
            if self.mode != "scale":
                self.hide_scale_info()
                
            if self.right_fingertips:
                self.prev_right_fingertips = self.right_fingertips.copy() if self.right_fingertips else None
            if self.left_fingertips:
                self.prev_left_fingertips = self.left_fingertips.copy() if self.left_fingertips else None
                
            self.left_fingertips = left
            self.right_fingertips = right
            
            if self.right_fingertips:
                self.smoothed_right_fingertips = self.smooth_points(self.right_fingertips, self.smoothed_right_fingertips)
            if self.left_fingertips:
                self.smoothed_left_fingertips = self.smooth_points(self.left_fingertips, self.smoothed_left_fingertips)
                
            if anchors_raw:
                self._anchors = anchors_raw
                self.smoothed_anchors = self.smooth_points(self._anchors, self.smoothed_anchors, SMOOTHING_ALPHA / 2)
            
            # ALWAYS update the finger orbs and anchor orbs positions every frame
            # This ensures continuous tracking regardless of mode
            if self.smoothed_right_fingertips:
                finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_right_fingertips]
                if ENABLE_DEBUG_ORBS:
                    self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
            
            if self.smoothed_anchors:
                anchor_points = [map_to_camera_relative_space(a["x"], a["y"], a["z"]) for a in self.smoothed_anchors]
                if ENABLE_DEBUG_ORBS:
                    self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
            
            # Only recenter mesh occasionally to prevent flickering
            RECENTER_INTERVAL = 10.0  # Only recenter every 10 seconds
            if current_time - self.last_recenter_time >= RECENTER_INTERVAL:
                mesh_obj = bpy.data.objects.get("DeformingMesh")
                if mesh_obj:
                    try:
                        recenter_mesh(mesh_obj)
                        self.last_recenter_time = current_time
                        logging.debug(f"Recentered mesh (next recenter in {RECENTER_INTERVAL} seconds)")
                    except Exception as e:
                        logging.error(f"Failed to recenter DeformingMesh in modal function: {e}")
            
            velocity_calc_interval = 0.05
            if current_time - self.last_velocity_update >= velocity_calc_interval:
                if self.smoothed_right_fingertips and self.prev_right_fingertips:
                    self.finger_velocities = self.calculate_finger_velocities(self.smoothed_right_fingertips,
                                                                              self.prev_right_fingertips,
                                                                              velocity_calc_interval)
                self.last_velocity_update = current_time
            
            if self.mode == "render":
                if command == "render":
                    logging.info("Render command received, creating mesh copy")
                    render_obj = self.create_render_copy()
                    if render_obj:
                        bpy.context.view_layer.objects.active = render_obj
                        for modifier in render_obj.modifiers:
                            try:
                                bpy.ops.object.modifier_apply(modifier=modifier.name)
                            except Exception as e:
                                logging.error(f"Could not apply modifier {modifier.name}: {e}")
                        # Use the new multi-view render function
                        self.render_multiview()
                self.mode = "none"
                    
            elif self.mode == "deform":
                if self.deform_active and self.smoothed_right_fingertips:
                    # Check if DeformingMesh exists and has valid data
                    mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
                    if not mesh_obj or not mesh_obj.data:
                        logging.error(f"Cannot deform: {DEFORM_OBJ_NAME} object does not exist or has no mesh data")
                        # If in deform mode but the mesh doesn't exist, switch back to 'none' mode
                        self.mode = "none"
                        self.deform_active = False
                    else:
                        if self.use_velocity_forces and self.finger_velocities:
                            self.deform_mesh_with_velocity(self.smoothed_right_fingertips,
                                                        self.finger_velocities,
                                                        self.smoothed_anchors)
                        else:
                            self.deform_mesh(self.smoothed_right_fingertips, self.smoothed_anchors)
                    
            elif self.mode == "rotate":
                env = bpy.data.objects.get("Env")
                if env is not None and self.smoothed_right_fingertips:
                    # Check if thumb and middle fingers are touching
                    thumb_tip = self.smoothed_right_fingertips[0]
                    middle_tip = self.smoothed_right_fingertips[2]
                    distance = math.sqrt(
                        (thumb_tip["x"] - middle_tip["x"])**2 +
                        (thumb_tip["y"] - middle_tip["y"])**2 +
                        (thumb_tip["z"] - middle_tip["z"])**2
                    )
                    # Only rotate if fingers are touching (distance < 0.05)
                    if distance < 0.05:
                        rotation_speed_deg = ROTATION_SPEED
                        angle_delta = math.radians(rotation_speed_deg * delta_time)
                        env.rotation_euler.z += angle_delta
                        
                        # Force update finger and anchor positions using camera-relative mapping
                        # This ensures they stay consistent relative to the camera view
                        camera = bpy.data.objects.get("Camera")
                        if camera is not None:
                            # Update all visualizations after rotation to keep them aligned with the camera
                            if self.smoothed_right_fingertips:
                                finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_right_fingertips]
                                if ENABLE_DEBUG_ORBS:
                                    self.update_fixed_debug_orbs(finger_points, self.finger_orbs, "fingerOrb", MAX_FINGER_ORBS)
                            
                            if self.smoothed_left_fingertips:
                                left_finger_points = [map_to_camera_relative_space(t["x"], t["y"], t["z"]) for t in self.smoothed_left_fingertips]
                                if ENABLE_DEBUG_ORBS:
                                    # Just update visualization, not actual processing
                                    self.update_fixed_debug_orbs(left_finger_points, [], "fingerOrb", 0)
                            
                            if self.smoothed_anchors:
                                anchor_points = [map_to_camera_relative_space(a["x"], a["y"], a["z"]) for a in self.smoothed_anchors]
                                if ENABLE_DEBUG_ORBS:
                                    self.update_fixed_debug_orbs(anchor_points, self.anchor_orbs, "anchorOrb", MAX_ANCHOR_ORBS)
                        
                        logging.debug("Rotating: fingers touching, positions updated with camera-relative mapping")
                    else:
                        logging.debug("Rotation stopped: fingers not touching")
                else:
                    logging.warning("Environment object 'Env' not found for rotation.")
            elif self.mode == "scale" and self.smoothed_right_fingertips:
                self.scale_mesh(self.smoothed_right_fingertips, scale_axis)
            elif self.mode == "create" and self.smoothed_right_fingertips:
                # When in create mode, create and position the cube
                # - Create a cube if one doesn't exist
                # - Update cube position continuously based on hand position
                self.create_new_object(self.smoothed_right_fingertips)
            elif self.mode == "sculpt" and self.smoothed_right_fingertips:
                # Determine brush type based on finger positions
                brush_type = self.determine_brush_type(self.smoothed_right_fingertips)
                # Apply the sculpt brush with the determined type
                self.apply_sculpt_brush(self.smoothed_right_fingertips, brush_type)
                
            elif self.mode == "boolean" and self.smoothed_left_fingertips and self.smoothed_right_fingertips:
                # Use both hands for object selection
                self.multi_select_objects(self.smoothed_left_fingertips, self.smoothed_right_fingertips)
                
                # Check if we have at least 2 objects selected for boolean operation
                # The gesture (hand configuration) would determine the boolean type
                if len(bpy.context.selected_objects) >= 2:
                    operation = "UNION"  # Default operation
                    # Determine operation based on hands configuration
                    # This is a simplified example - could be extended with more gestures
                    if (self.smoothed_left_fingertips[1]["y"] < 0.3 and 
                        self.smoothed_right_fingertips[1]["y"] < 0.3):
                        operation = "DIFFERENCE"
                    elif (self.smoothed_left_fingertips[1]["y"] > 0.7 and 
                          self.smoothed_right_fingertips[1]["y"] > 0.7):
                        operation = "INTERSECT"
                    self.apply_boolean_operation(operation)
                
            elif self.mode == "material" and self.smoothed_right_fingertips:
                # Determine material index based on hand height
                avg_y = sum(tip["y"] for tip in self.smoothed_right_fingertips) / len(self.smoothed_right_fingertips)
                # Map y position (0-1) to material indices (0-4)
                material_index = min(int(avg_y * 5), 4)
                self.assign_material_to_selection(material_index)
                
            elif self.mode == "dyntopo":
                # Toggle dynamic topology based on gesture
                self.toggle_dynamic_topology()
                self.mode = "sculpt"  # Automatically switch to sculpt mode after toggling
                
            # Check for additional voice commands from live data
            voice_command = data.get("voice_command", "")
            if voice_command.startswith("scale "):
                try:
                    # Parse commands like "scale x to 2.5"
                    parts = voice_command.split()
                    if len(parts) >= 4 and parts[2].lower() == "to":
                        axis = parts[1].upper()
                        value = float(parts[3])
                        self.precise_scale(axis, value)
                        logging.info(f"Applied precise scale to {axis}: {value}")
                except Exception as e:
                    logging.error(f"Error parsing scale command: {e}")
            elif voice_command == "enable snapping":
                self.enable_snapping()
            elif voice_command == "bridge edges":
                self.bridge_edge_loops()
            elif voice_command == "smooth edges":
                self.smooth_edge_flow()
                    
            self.prev_mode = self.mode
            
        # At the end of the modal loop, check if we're exiting create mode
        if self.prev_mode == "create" and self.mode != "create":
            # Join the cube when exiting create mode
            if self.created_cube:
                self.join_created_cube()
                logging.info("Joined cube to DeformingMesh when exiting create mode via prev_mode check")
            self.create_triggered = False
            
        return {'PASS_THROUGH'}

    def hide_scale_info(self):
        """Hide the scale info text object"""
        text_obj = bpy.data.objects.get("ScaleInfo")
        if text_obj:
            text_obj.hide_viewport = True

    def execute(self, context):
        self._timer = context.window_manager.event_timer_add(0.05, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.last_rotation_update = time.time()
        self.last_velocity_update = time.time()
        self.last_recenter_time = time.time()  # Initialize the recentering timer
        self.use_velocity_forces = True
        self.finger_velocities = None
        self.deform_active = False
        self.render_created_objects = []
        self.create_triggered = False
        self.created_cube = None
        self.prev_mode = self.mode
        self.scale_start_thumb_z = None
        mesh_obj = bpy.data.objects.get("DeformingMesh")
        if mesh_obj:
            try:
                recenter_mesh(mesh_obj)
            except Exception as e:
                logging.error(f"Failed to recenter mesh in execute: {e}")
        logging.info("Real-time mesh update operator started.")
        logging.info("Controls: ESC (cancel), D (deform), R (rotate), S (scale), C (create), A (anchor), M (cycle remesh), V (toggle velocity forces), Shift+R (render)")
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        logging.info("Real-time update operator cancelled. Cleaning up...")
        
        # Apply scale if in scale mode when cancelled
        if self.mode == "scale":
            self.apply_scale()
            logging.info("Applied scale before cancelling as we were in scale mode")
        
        # Join cube if in create mode when cancelled
        if self.mode == "create" and self.created_cube:
            self.join_created_cube()
            logging.info("Joined cube to DeformingMesh before cancelling as we were in create mode")
        
        # Hide scale info if visible
        self.hide_scale_info()
        cleanup_created_objects()
        return {'CANCELLED'}

    def render_multiview(self):
        """Render multiple views using the RenderCam camera"""
        # We need to bypass the error that's occurring in this function
        # Let's completely restructure the function to avoid the problematic operations
        
        # ===== PART 1: Setup Session Directory =====
        try:
            # First, find the DeformingMesh
            mesh_obj = bpy.data.objects.get(DEFORM_OBJ_NAME)
            if not mesh_obj:
                print("Cannot find DeformingMesh to create snapshot for rendering")
                return False
                
            print("Creating snapshot of current DeformingMesh state")
            
            # Create session directory with timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            base_output_dir = "C:\\CODING\\VIBE\\VIBE_Massing\\output\\generated\\Models"
            session_dir = os.path.join(base_output_dir, f"session_{timestamp}")
            os.makedirs(session_dir, exist_ok=True)
            print(f"Created session directory: {session_dir}")
        except Exception as e:
            print(f"Error in session directory setup: {str(e)}")
            return False
            
        # ===== PART 2: Collection Setup =====
        try:
            # Create or get the VIBE_Renders collection
            collection_name = "VIBE_Renders"
            render_collection = None
            
            if collection_name in bpy.data.collections:
                render_collection = bpy.data.collections[collection_name]
                print(f"Using existing collection: {collection_name}")
            else:
                render_collection = bpy.data.collections.new(collection_name)
                bpy.context.scene.collection.children.link(render_collection)
                print(f"Created new collection: {collection_name}")
            
            # Set collection to be hidden in viewport and excluded from renders
            render_collection.hide_viewport = True
            render_collection.hide_render = True
            print(f"Set collection properties")
            
            # Also set layer collection visibility
            for view_layer in bpy.context.scene.view_layers:
                layer_coll = view_layer.layer_collection
                for child in layer_coll.children:
                    if child.name == collection_name:
                        child.hide_viewport = True
                        child.exclude = True
                        print(f"Set layer collection settings in view layer")
        except Exception as e:
            print(f"Error in collection setup: {str(e)}")
            return False
            
        # ===== PART 3: Find Next Iteration Number =====
        try:
            # Find the next available iteration number
            iteration = 0
            while os.path.exists(os.path.join(session_dir, f"iteration_{iteration:03d}.glb")):
                iteration += 1
            
            iteration_name = f"iteration_{iteration:03d}"
            print(f"Using iteration name: {iteration_name}")
        except Exception as e:
            print(f"Error finding iteration number: {str(e)}")
            return False
            
        # ===== PART 4: Create Snapshot =====
        try:
            # Create a snapshot copy of the DeformingMesh
            bpy.ops.object.select_all(action='DESELECT')
            mesh_obj.select_set(True)
            bpy.context.view_layer.objects.active = mesh_obj
            
            # Duplicate the mesh (this creates a copy and selects it)
            bpy.ops.object.duplicate()
            
            # Get the duplicated object (it's now the active/selected object)
            snapshot_obj = bpy.context.active_object
            original_name = snapshot_obj.name
            snapshot_obj.name = iteration_name
            print(f"Created snapshot named: {iteration_name}")
            
            # Apply all modifiers to the snapshot
            for modifier in snapshot_obj.modifiers:
                try:
                    bpy.context.view_layer.objects.active = snapshot_obj
                    bpy.ops.object.modifier_apply(modifier=modifier.name)
                except Exception as modifier_error:
                    print(f"Could not apply modifier: {str(modifier_error)}")
        except Exception as e:
            print(f"Error creating snapshot: {str(e)}")
            return False
            
        # ===== PART 5: Collection Management =====
        try:
            # Make sure we have the correct object selected
            bpy.ops.object.select_all(action='DESELECT')
            snapshot_obj.select_set(True)
            bpy.context.view_layer.objects.active = snapshot_obj
            
            # CRITICAL: Remove the snapshot from ALL collections first
            print(f"Moving snapshot to collection: {collection_name}")
            all_collections = list(snapshot_obj.users_collection)
            for col in all_collections:
                col.objects.unlink(snapshot_obj)
            
            # Now link ONLY to the render collection
            render_collection.objects.link(snapshot_obj)
            
            # Verify the object is only in the render collection
            if len(snapshot_obj.users_collection) != 1 or snapshot_obj.users_collection[0].name != collection_name:
                print(f"Warning: snapshot may not be exclusively in {collection_name}")
            else:
                print(f"Snapshot successfully placed in {collection_name}")
        except Exception as e:
            print(f"Error managing collections: {str(e)}")
            # Don't return False here, try to continue with export
            
        # ===== PART 6: Export GLB =====
        try:
            # Export the snapshot to the session directory
            export_path = os.path.join(session_dir, f"{iteration_name}.glb")
            
            # Make sure the object is properly selected again
            bpy.ops.object.select_all(action='DESELECT')
            snapshot_obj.select_set(True)
            bpy.context.view_layer.objects.active = snapshot_obj
            
            # Export as GLB
            bpy.ops.export_scene.gltf(
                filepath=export_path,
                use_selection=True,
                export_format='GLB'
            )
            print(f"Exported to: {export_path}")
            
            # Verify the export file exists
            if os.path.exists(export_path):
                file_size = os.path.getsize(export_path)
                print(f"Verified file exists ({file_size} bytes)")
            else:
                print(f"Warning: Export file not found")
        except Exception as e:
            print(f"Error exporting GLB: {str(e)}")
            # Continue with renders even if export fails
            
        # ===== PART 7: Multi-View Renders =====
        try:
            # Create output directory
            os.makedirs(RENDER_OUTPUT_DIR, exist_ok=True)
            
            # Get the render camera
            render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
            if not render_cam:
                print(f"Render camera not found: {RENDER_CAMERA_NAME}")
                return False
                
            # Store current camera and frame
            current_camera = bpy.context.scene.camera
            current_frame = bpy.context.scene.frame_current
            
            # Set render camera
            bpy.context.scene.camera = render_cam
            
            # Render each frame
            for frame, filename in RENDER_FRAMES.items():
                try:
                    # Set frame
                    bpy.context.scene.frame_current = frame
                    
                    # Set output path - ASCII only
                    safe_filename = "".join(c for c in filename if ord(c) < 128)
                    output_path = os.path.join(RENDER_OUTPUT_DIR, safe_filename)
                    bpy.context.scene.render.filepath = output_path
                    
                    # Render
                    print(f"Rendering frame {frame}")
                    bpy.ops.render.render(write_still=True)
                except Exception as frame_error:
                    print(f"Error rendering frame {frame}: {str(frame_error)}")
            
            print("Multi-view render completed")
            return True
        except Exception as e:
            print(f"Error in multi-view render: {str(e)}")
            return False
        finally:
            try:
                # Restore original camera and frame
                bpy.context.scene.camera = current_camera
                bpy.context.scene.frame_current = current_frame
            except:
                pass  # Silently continue if restoration fails

def ensure_minimum_dimensions(obj, min_dimension=4.0):
    """
    Ensures that the object has at least one dimension (X, Y, or Z) that is at least min_dimension meters.
    
    Args:
        obj (bpy.types.Object): The Blender object to resize
        min_dimension (float): The minimum dimension in meters (default: 4.0)
        
    Returns:
        bool: True if scaling was applied, False otherwise
    """
    if not obj:
        logging.error("No object provided to ensure_minimum_dimensions")
        return False
        
    # Get the object's dimensions
    dimensions = obj.dimensions
    logging.info(f"Original dimensions: {dimensions.x:.2f}m x {dimensions.y:.2f}m x {dimensions.z:.2f}m")
    
    # Find the largest dimension
    max_dim = max(dimensions.x, dimensions.y, dimensions.z)
    
    # If the largest dimension is less than the minimum dimension, scale the object
    if max_dim < min_dimension:
        # Calculate the scale factor needed
        scale_factor = min_dimension / max_dim
        
        # Apply the scale factor to the object
        obj.scale = [s * scale_factor for s in obj.scale]
        
        # Update the object to reflect the new scale
        bpy.context.view_layer.update()
        
        # Apply the scale to the mesh (so it's "baked in")
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        
        # Log the new dimensions
        new_dimensions = obj.dimensions
        logging.info(f"Scaled to minimum dimensions: {new_dimensions.x:.2f}m x {new_dimensions.y:.2f}m x {new_dimensions.z:.2f}m")
        logging.info(f"Applied scale factor: {scale_factor:.2f}")
        return True
    else:
        logging.info(f"No scaling needed, largest dimension {max_dim:.2f}m already meets minimum {min_dimension:.2f}m")
        return False

class ImageUserProperties(bpy.types.PropertyGroup):
    # Instead of trying to use ImageUser directly, we'll create a simple property
    # that will allow the template_image to work
    use_A: bpy.props.BoolProperty(default=True)
    use_B: bpy.props.BoolProperty(default=True)
    use_C: bpy.props.BoolProperty(default=True)

def register_massing():
    bpy.utils.register_class(REALTIME_OT_update_mesh)
    # OPTION_OT_select already registered by base script, avoid duplicate
    bpy.utils.register_class(ImageUserProperties)
    
    # Register the property group
    bpy.types.Scene.vibe_image_users = bpy.props.PointerProperty(type=ImageUserProperties)
    
    register_image_panel()
    logging.info("Registered VIBE Massing addon with image panel")

def unregister_massing():
    cleanup_created_objects()
    
    # Unregister the property group
    del bpy.types.Scene.vibe_image_users
    
    bpy.utils.unregister_class(ImageUserProperties)
    unregister_image_panel()
    bpy.utils.unregister_class(REALTIME_OT_update_mesh)
    logging.info("Unregistered VIBE Massing addon")

if __name__ == "__main__":
    # Register base addon (which now also registers massing components)
    register()
    bpy.ops.wm.realtime_update_mesh()

# Duplicate __main__ block disabled after consolidation
if False:
    try:
        unregister_massing()
    except:
        pass
    register_massing()
    check_render_requests()