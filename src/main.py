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

# Render configuration
RENDER_OUTPUT_DIR = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\blenderRender"
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

# Generated mesh location
GENERATED_MESH_PATH = r"C:\CODING\VIBE\VIBE_Forming\output\generated\Models\current_mesh.glb"

# ComfyUI server configuration
COMFYUI_SERVER = "127.0.0.1:8188"
COMFYUI_OUTPUT_DIR = r"C:\ComfyUI_windows_portable_nvidia\ComfyUI_windows_portable\ComfyUI\output"

# Text prompt configuration
TEXT_OPTIONS_DIR = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\textOptions"
PROMPT_FILE = "prompt.txt"
INPUT_TEXT_FILE = r"C:\CODING\VIBE\VIBE_Forming\input\input.txt"
OPTIONS_API_SCRIPT = r"C:\CODING\VIBE\VIBE_Forming\src\comfyworkflows\options_API.py"

# Communication files for integration with UI
RENDER_REQUEST_FILE = r"C:\CODING\VIBE\VIBE_Forming\render_request.txt"
RENDER_COMPLETE_FILE = r"C:\CODING\VIBE\VIBE_Forming\render_complete.txt"
IMPORT_REQUEST_FILE = r"C:\CODING\VIBE\VIBE_Forming\import_request.txt"
IMPORT_COMPLETE_FILE = r"C:\CODING\VIBE\VIBE_Forming\import_complete.txt"

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
        layout.operator("object.generate_iteration", text="Generate New Iteration", icon='CAMERA_DATA')
        layout.operator("option.terminate_script", text="Terminate Script", icon='X')

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
            self.report({'ERROR'}, "Please select a mesh object before generating a new iteration")
            return {'CANCELLED'}
            
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
        if not active_obj or active_obj.type != 'MESH':
            logging.warning("No active mesh object selected. Please select an object before importing.")
            return False
            
        # Store the reference to the previously active object
        previous_obj = active_obj
        
        # Get the max dimension of the previous object
        previous_max_dim = max(previous_obj.dimensions.x, previous_obj.dimensions.y, previous_obj.dimensions.z)
        logging.info(f"Previous object max dimension: {previous_max_dim}")
        
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
        
        # Hide the previous object
        previous_obj.hide_viewport = True
        previous_obj.hide_render = True
        logging.info(f"Hidden previous object: {previous_obj.name}")
        
        # Set the main mesh as active
        bpy.context.view_layer.objects.active = main_mesh
        main_mesh.select_set(True)
        
        # Set the object's origin to its geometry center
        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
        
        # Center the object at the world origin
        main_mesh.location = (0, 0, 0)
        
        # Calculate and apply scaling to match the previous object's max dimension
        current_max_dim = max(main_mesh.dimensions.x, main_mesh.dimensions.y, main_mesh.dimensions.z)
        logging.info(f"Current mesh max dimension: {current_max_dim}")
        
        if current_max_dim > 0:
            scale_factor = previous_max_dim / current_max_dim
            logging.info(f"Calculated scale factor: {scale_factor}")
            
            # Apply scaling to main mesh and its children
            main_mesh.scale = (scale_factor, scale_factor, scale_factor)
            
            # Apply the scale
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            logging.info(f"Applied scaling factor {scale_factor} to match previous object dimension")
        else:
            logging.warning("Imported mesh has zero dimensions, couldn't scale properly")
        
        logging.info(f"Successfully imported and processed mesh: {main_mesh.name}")
        return True
    except Exception as e:
        logging.error(f"Error importing generated mesh: {str(e)}")
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
    alt_image_dir = r"C:\CODING\VIBE\VIBE_Forming\input\options"  # Alternative path format
    
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
        "C:/CODING/VIBE/VIBE_Forming/input/options",
        "C:/CODING/VIBE/VIBE_Forming/input/COMFYINPUTS/blenderRender",
        "C:/CODING/VIBE/VIBE_Forming/input/COMFYINPUTS/textOptions",
        "C:/CODING/VIBE/VIBE_Forming/output",
        "C:/CODING/VIBE/VIBE_Forming/output/generated/Models"
    ]
    
    # Also try backslash versions as alternative
    alt_dirs = [
        r"C:\CODING\VIBE\VIBE_Forming\input\options",
        r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\blenderRender",
        r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\textOptions",
        r"C:\CODING\VIBE\VIBE_Forming\output",
        r"C:\CODING\VIBE\VIBE_Forming\output\generated\Models"
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
        "C:/CODING/VIBE/VIBE_Forming/input/options",
        r"C:\CODING\VIBE\VIBE_Forming\input\options"
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

# Timer function to check if images have been updated
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
            base_dir = r"C:\CODING\VIBE\VIBE_Forming"
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
    """Check if there's an import request from the UI and process it"""
    if os.path.exists(IMPORT_REQUEST_FILE):
        logging.info(f"Found import request file: {IMPORT_REQUEST_FILE}")
        try:
            # Read request details
            with open(IMPORT_REQUEST_FILE, 'r') as f:
                request_details = f.read()
                
            logging.info(f"Import request details: {request_details}")
            
            # Delete the request file
            os.remove(IMPORT_REQUEST_FILE)
            
            # Process the import
            success = import_generated_mesh()
            
            # Write completion status
            with open(IMPORT_COMPLETE_FILE, 'w') as f:
                if success:
                    f.write("SUCCESS")
                    logging.info("Import completed successfully")
                else:
                    f.write("ERROR: Import failed")
                    logging.info("Import failed")
                    
            return True
        except Exception as e:
            logging.error(f"Error processing import request: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # Write error status
            try:
                with open(IMPORT_COMPLETE_FILE, 'w') as f:
                    f.write(f"ERROR: {str(e)}")
            except:
                pass
                
            return False
    
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
    bpy.types.Scene.prompt_properties = PointerProperty(type=PromptProperties)
    bpy.types.Scene.custom_request_properties = PointerProperty(type=CustomRequestProperties)
    
    # Register operators and UI
    bpy.utils.register_class(IMAGE_OT_refresh)  # Register the new refresh operator
    bpy.utils.register_class(REQUEST_OT_submit)  # Register the new submit operator
    bpy.utils.register_class(IMAGE_PT_display_panel)
    bpy.utils.register_class(OPTION_OT_select)
    bpy.utils.register_class(OPTION_OT_terminate_script)
    bpy.utils.register_class(OBJECT_OT_generate_iteration)
    
    # Create render camera
    ensure_render_camera()
    
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
        
    logging.info("Successfully registered VIBE panel")

# Unregistration function
def unregister():
    try:
        # Unregister property groups
        del bpy.types.Scene.prompt_properties
        del bpy.types.Scene.custom_request_properties
        
        # Unregister operators and UI
        bpy.utils.unregister_class(OBJECT_OT_generate_iteration)
        bpy.utils.unregister_class(OPTION_OT_terminate_script)
        bpy.utils.unregister_class(OPTION_OT_select)
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(REQUEST_OT_submit)
        bpy.utils.unregister_class(IMAGE_OT_refresh)
        bpy.utils.unregister_class(PromptProperties)
        bpy.utils.unregister_class(CustomRequestProperties)
        
        logging.info("Successfully unregistered VIBE panel")
    except Exception as e:
        logging.error(f"Failed to unregister panel: {e}")

# Run register when script is run directly in Blender's text editor
if __name__ == "__main__":
    try:
        # Try to unregister first (in case it's already registered)
        unregister()
    except:
        pass
    register()
    
    # Check for render requests from UI
    check_render_requests() 