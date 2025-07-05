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
from bpy.app.handlers import persistent
from pathlib import Path

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
LIVE_DATA_FILE = "C:/CODING/VIBE/VIBE_Forming/output/live_hand_data.json"  # Updated to match the actual file location

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

# Add these constants at the top of the file, after the imports
ENABLE_DEBUG_ORBS = True
MAX_FINGER_ORBS = 5
MAX_ANCHOR_ORBS = 2
SMOOTHING_ALPHA = 0.3
VELOCITY_SMOOTHING = 0.3
VELOCITY_MAX_SPEED = 2.0
VELOCITY_MIN_SPEED = 0.1
FINGER_INFLUENCE_RADIUS = 2.0
FINGER_FORCE_STRENGTH = 0.5
ANCHOR_FORCE_MULTIPLIER = 1.5
MASS_COHESION_FACTOR = 0.5
DEFORM_TIMESTEP = 0.016
MAX_DISPLACEMENT_PER_FRAME = 0.1
ROTATION_SPEED = 45.0

# Global variables
original_volume = 1.0  # Default value in case calculation fails
view_layer_processed_objects = {}  # Track objects we've already tried to fix
VIEW_LAYER_PROCESS_TIMEOUT = 5.0  # Only try to fix an object's view layer every 5 seconds

# Property Groups
class CustomRequestProperties(PropertyGroup):
    custom_prompt: StringProperty(
        name="Custom Prompt",
        description="Enter your custom request for generating 3D models",
        default="",
        maxlen=500
    )

class PromptProperties(PropertyGroup):
    prompt_items = [
        ("A", "Prompt A", "Use text prompt A"),
        ("B", "Prompt B", "Use text prompt B"),
        ("C", "Prompt C", "Use text prompt C")
    ]
    
    active_prompt: EnumProperty(
        name="Text Prompt",
        description="Select the text prompt to use for generation",
        items=prompt_items,
        default="A"
    )
    
    show_prompt_text: BoolProperty(
        name="Show Prompt Text",
        description="Display the current prompt text",
        default=False
    )

class RemeshProperties(PropertyGroup):
    enable_remesh: BoolProperty(
        name="Enable Remesh",
        description="Enable staged remesh processing on mesh import",
        default=False
    )
    
    current_stage: IntProperty(
        name="Remesh Stage",
        description="Current remesh processing stage",
        default=1,
        min=1,
        max=3
    )
    
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

class ImageUserProperties(PropertyGroup):
    use_A: BoolProperty(default=True)
    use_B: BoolProperty(default=True)
    use_C: BoolProperty(default=True)

# Registration function
def register():
    try:
        # Register property groups first, before any other operations
        if not hasattr(bpy.types, 'CustomRequestProperties'):
            bpy.utils.register_class(CustomRequestProperties)
        if not hasattr(bpy.types, 'PromptProperties'):
            bpy.utils.register_class(PromptProperties)
        if not hasattr(bpy.types, 'RemeshProperties'):
            bpy.utils.register_class(RemeshProperties)
        if not hasattr(bpy.types, 'ImageUserProperties'):
            bpy.utils.register_class(ImageUserProperties)
        
        # Add properties to scene
        if not hasattr(bpy.types.Scene, 'custom_request'):
            bpy.types.Scene.custom_request = PointerProperty(type=CustomRequestProperties)
        if not hasattr(bpy.types.Scene, 'prompt_props'):
            bpy.types.Scene.prompt_props = PointerProperty(type=PromptProperties)
        if not hasattr(bpy.types.Scene, 'remesh_props'):
            bpy.types.Scene.remesh_props = PointerProperty(type=RemeshProperties)
        if not hasattr(bpy.types.Scene, 'image_user_props'):
            bpy.types.Scene.image_user_props = PointerProperty(type=ImageUserProperties)
        
        # Register operators
        bpy.utils.register_class(IMAGE_OT_refresh)
        bpy.utils.register_class(OPTION_OT_select)
        bpy.utils.register_class(OPTION_OT_terminate_script)
        bpy.utils.register_class(OBJECT_OT_generate_iteration)
        bpy.utils.register_class(OBJECT_OT_toggle_remesh)
        bpy.utils.register_class(REQUEST_OT_submit)
        bpy.utils.register_class(IMAGE_PT_reload_all)
        bpy.utils.register_class(REALTIME_OT_update_mesh)
        
        # Register panels
        bpy.utils.register_class(IMAGE_PT_display_panel)
        bpy.utils.register_class(REMESH_PT_settings_panel)
        bpy.utils.register_class(IMAGE_MASSING_PT_display_panel)
        
        # Register image panel
        register_image_panel()
        
        # Register massing
        register_massing()
        
        # Add timer for checking requests
        bpy.app.timers.register(check_requests_timer)
        
        logging.info("Successfully registered all components")
    except Exception as e:
        logging.error(f"Error during registration: {str(e)}")
        raise

def unregister():
    try:
        bpy.app.timers.unregister(check_requests_timer)
        unregister_massing()
        unregister_image_panel()
        bpy.utils.unregister_class(IMAGE_MASSING_PT_display_panel)
        bpy.utils.unregister_class(REMESH_PT_settings_panel)
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(REALTIME_OT_update_mesh)
        bpy.utils.unregister_class(IMAGE_PT_reload_all)
        bpy.utils.unregister_class(REQUEST_OT_submit)
        bpy.utils.unregister_class(OBJECT_OT_toggle_remesh)
        bpy.utils.unregister_class(OBJECT_OT_generate_iteration)
        bpy.utils.unregister_class(OPTION_OT_terminate_script)
        bpy.utils.unregister_class(OPTION_OT_select)
        bpy.utils.unregister_class(IMAGE_OT_refresh)
        del bpy.types.Scene.image_user_props
        del bpy.types.Scene.remesh_props
        del bpy.types.Scene.prompt_props
        del bpy.types.Scene.custom_request
        bpy.utils.unregister_class(ImageUserProperties)
        bpy.utils.unregister_class(RemeshProperties)
        bpy.utils.unregister_class(PromptProperties)
        bpy.utils.unregister_class(CustomRequestProperties)
        logging.info("Successfully unregistered all components")
    except Exception as e:
        logging.error(f"Error during unregistration: {str(e)}")

def safely_create_debug_orb(self, template_name):
    """Safely create a debug orb object"""
    try:
        # Check if template exists
        template = bpy.data.objects.get(template_name)
        if not template:
            # Create template if it doesn't exist
            if template_name == "fingerOrb":
                template = create_orb_template(radius=0.2, segments=8)
            elif template_name == "anchorOrb":
                template = create_anchor_template(radius=0.4, segments=12)
            else:
                logging.error(f"Unknown template name: {template_name}")
                return None
        
        # Create new orb
        orb = template.copy()
        orb.data = template.data.copy()
        orb.name = f"{template_name}_{len(self.finger_orbs)}"
        
        # Create material if it doesn't exist
        mat_name = f"{template_name}Material"
        if mat_name not in bpy.data.materials:
            mat = bpy.data.materials.new(name=mat_name)
            mat.diffuse_color = (0.0, 0.0, 1.0, 0.7)  # Default blue color
        else:
            mat = bpy.data.materials[mat_name]
        
        # Assign material
        if not orb.material_slots:
            orb.data.materials.append(mat)
        else:
            orb.material_slots[0].material = mat
        
        # Link to scene
        bpy.context.collection.objects.link(orb)
        return orb
    except Exception as e:
        logging.error(f"Error creating debug orb: {e}")
        return None

def update_fixed_debug_orbs(self, mapped_points, orb_list, template_name, max_count, color=None):
    """Update the positions of debug orbs"""
    if not ENABLE_DEBUG_ORBS:
        return
        
    # Create orbs if needed
    while len(orb_list) < len(mapped_points):
        orb = self.safely_create_debug_orb(template_name)
        if orb:
            orb_list.append(orb)
    
    # Update positions and colors
    for i, (point, orb) in enumerate(zip(mapped_points, orb_list)):
        if orb and orb.name in bpy.data.objects:
            orb.location = point
            if color and orb.material_slots and orb.material_slots[0].material:
                orb.material_slots[0].material.diffuse_color = color
        
    # Hide excess orbs
    for orb in orb_list[len(mapped_points):]:
        if orb and orb.name in bpy.data.objects:
            orb.hide_viewport = True

def create_orb_template(radius=0.2, segments=8):
    """Create a template sphere for finger orbs"""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        segments=segments,
        ring_count=segments
    )
    orb = bpy.context.active_object
    orb.name = "fingerOrb"
    
    # Create material
    mat = bpy.data.materials.new(name="fingerOrbMaterial")
    mat.diffuse_color = (0.0, 0.0, 1.0, 0.7)  # Blue color
    orb.data.materials.append(mat)
    
    # Hide the template
    orb.hide_viewport = True
    return orb

def create_anchor_template(radius=0.4, segments=12):
    """Create a template sphere for anchor orbs"""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        segments=segments,
        ring_count=segments
    )
    orb = bpy.context.active_object
    orb.name = "anchorOrb"
    
    # Create material
    mat = bpy.data.materials.new(name="anchorOrbMaterial")
    mat.diffuse_color = (1.0, 0.0, 0.0, 0.7)  # Red color
    orb.data.materials.append(mat)
    
    # Hide the template
    orb.hide_viewport = True
    return orb

def create_tracking_orb():
    """Create a single orb for tracking fingertips"""
    # Create icosphere
    bpy.ops.mesh.primitive_ico_sphere_add(
        radius=0.05,
        subdivisions=3,
        location=(0, 0, 0)
    )
    orb = bpy.context.active_object
    orb.name = "Orb"
    
    # Create emission material
    mat = bpy.data.materials.new(name="OrbMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    
    # Clear default nodes
    nodes.clear()
    
    # Create emission shader
    emission = nodes.new('ShaderNodeEmission')
    emission.inputs[0].default_value = (0, 1, 1, 1)  # Cyan color
    emission.inputs[1].default_value = 2.0  # Emission strength
    
    # Create material output
    material_output = nodes.new('ShaderNodeOutputMaterial')
    
    # Link nodes
    mat.node_tree.links.new(emission.outputs[0], material_output.inputs[0])
    
    # Assign material to orb
    orb.data.materials.append(mat)
    
    return orb

def update_tracking_orb(orb, hand_data):
    """Update orb position based on hand data"""
    if not orb or not hand_data:
        return
        
    # Get right hand fingertips
    right_hand = hand_data.get("right_hand", {})
    fingertips = right_hand.get("fingertips", [])
    
    if fingertips:
        # Use the first fingertip (index finger) for tracking
        tip = fingertips[0]
        # Map the normalized coordinates to 3D space
        pos = map_to_camera_relative_space(tip["x"], tip["y"], tip["z"])
        orb.location = pos
        logging.debug(f"Updated orb position to {pos}")

def map_to_camera_relative_space(x_norm: float, y_norm: float, z_val: float) -> mathutils.Vector:
    """Maps normalized coordinates to 3D space relative to camera view"""
    # Get basic mapping first (standard coordinate conversion)
    point = mathutils.Vector((-z_val * 20.0, -(x_norm - 0.5) * 20.0, (0.5 - y_norm) * 20.0))
    
    # Look for the Camera object (not RenderCam)
    camera = bpy.data.objects.get("Camera")
    if camera is not None:
        # Get the camera's world matrix
        cam_matrix = camera.matrix_world
        
        # Create a coordinate system based on the camera's orientation
        cam_forward = -cam_matrix.to_3x3().col[2].normalized()  # -Z axis
        cam_right = cam_matrix.to_3x3().col[0].normalized()     # X axis
        cam_up = cam_matrix.to_3x3().col[1].normalized()        # Y axis
        
        # Apply 45-degree rotation around the camera's up axis
        angle_rad = math.radians(45)
        cos_angle = math.cos(angle_rad)
        sin_angle = math.sin(angle_rad)
        
        # Rotate the right and forward vectors
        cam_right_rotated = cam_right * cos_angle + cam_forward * sin_angle
        cam_forward_rotated = -cam_right * sin_angle + cam_forward * cos_angle
        
        # Create point in camera-relative coordinates
        cam_relative_point = (
            cam_right_rotated * point.x +
            cam_up * point.z +
            cam_forward_rotated * point.y
        )
        
        return cam_relative_point
    
    # Fallback to standard mapping if no camera found
    return point

class REALTIME_OT_update_mesh(bpy.types.Operator):
    bl_idname = "wm.realtime_update_mesh"
    bl_label = "Real-time Mesh Update Operator"

    _timer = None
    tracking_orb = None

    def execute(self, context):
        # Create tracking orb if it doesn't exist
        if not self.tracking_orb:
            self.tracking_orb = create_tracking_orb()
            logging.info("Created tracking orb")
        
        # Add timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.016, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'ESC' and event.value == 'PRESS':
            logging.info("Escape pressed. Cancelling operator.")
            return self.cancel(context)
        
        if event.type == 'TIMER':
            try:
                data = self.read_live_data()
                if not data:
                    return {'PASS_THROUGH'}
                
                # Process hand data
                left_hand_data = data.get("left_hand")
                left = []
                if left_hand_data is not None and isinstance(left_hand_data, dict):
                    left = left_hand_data.get("fingertips", [])
                
                right_hand_data = data.get("right_hand")
                right = []
                if right_hand_data is not None and isinstance(right_hand_data, dict):
                    right = right_hand_data.get("fingertips", [])
                
                # Update finger positions
                if self.right_fingertips:
                    self.prev_right_fingertips = self.right_fingertips.copy() if self.right_fingertips else None
                if self.left_fingertips:
                    self.prev_left_fingertips = self.left_fingertips.copy() if self.left_fingertips else None
                
                self.left_fingertips = left
                self.right_fingertips = right
                
                # Smooth the finger positions
                if self.right_fingertips:
                    self.smoothed_right_fingertips = self.smooth_points(self.right_fingertips, self.smoothed_right_fingertips)
                if self.left_fingertips:
                    self.smoothed_left_fingertips = self.smooth_points(self.left_fingertips, self.smoothed_left_fingertips)
                
                # Update tracking orb position
                if self.tracking_orb and self.smoothed_right_fingertips:
                    update_tracking_orb(self.tracking_orb, data)
                    logging.debug("Updated tracking orb position")
            except Exception as e:
                logging.error(f"Error in modal: {e}")
                import traceback
                logging.error(traceback.format_exc())
            
        return {'PASS_THROUGH'}

    def cancel(self, context):
        # Remove timer
        if self._timer:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
        
        # Remove orb
        if self.tracking_orb:
            bpy.data.objects.remove(self.tracking_orb, do_unlink=True)
            self.tracking_orb = None
            logging.info("Removed tracking orb")

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

class IMAGE_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'

    def draw(self, context):
        layout = self.layout
        
        # Add tracking control section
        box = layout.box()
        box.label(text="Hand Tracking")
        row = box.row()
        row.operator("wm.realtime_update_mesh", text="Start Tracking", icon='HAND')
        
        # Rest of your panel UI
        # ... existing code ...

class IMAGE_OT_refresh(bpy.types.Operator):
    bl_idname = "image.refresh"
    bl_label = "Refresh Images"
    bl_description = "Reload all images from disk"

    def execute(self, context):
        # Dummy implementation; replace with actual refresh logic if needed
        self.report({'INFO'}, "Images refreshed (dummy operator)")
        return {'FINISHED'}

class OPTION_OT_select(bpy.types.Operator):
    bl_idname = "option.select"
    bl_label = "Select Option"
    bl_description = "Select this design option"

    option: bpy.props.StringProperty()

    def execute(self, context):
        self.report({'INFO'}, f"Option {self.option} selected (dummy operator)")
        return {'FINISHED'}

class OPTION_OT_terminate_script(bpy.types.Operator):
    bl_idname = "option.terminate_script"
    bl_label = "Terminate Script"
    bl_description = "Unregister the addon and stop the script"

    def execute(self, context):
        self.report({'INFO'}, "Script terminated (dummy operator)")
        return {'FINISHED'}

class OBJECT_OT_generate_iteration(bpy.types.Operator):
    bl_idname = "object.generate_iteration"
    bl_label = "Generate New Iteration"
    bl_description = "Render views, process through ComfyUI, and import the resulting mesh"

    def execute(self, context):
        self.report({'INFO'}, "Generated new iteration (dummy operator)")
        return {'FINISHED'}

class OBJECT_OT_toggle_remesh(bpy.types.Operator):
    bl_idname = "object.toggle_remesh"
    bl_label = "Toggle Remesh"
    bl_description = "Toggle the staged remesh functionality"

    def execute(self, context):
        self.report({'INFO'}, "Toggled remesh (dummy operator)")
        return {'FINISHED'}

class REQUEST_OT_submit(bpy.types.Operator):
    bl_idname = "request.submit"
    bl_label = "Submit Request"
    bl_description = "Submit custom request to generate new options"

    def execute(self, context):
        self.report({'INFO'}, "Request submitted (dummy operator)")
        return {'FINISHED'}

class IMAGE_PT_reload_all(bpy.types.Operator):
    bl_idname = "image.reload_all"
    bl_label = "Reload All Images"
    bl_description = "Force reload all images from disk"

    def execute(self, context):
        self.report({'INFO'}, "Images reloaded (dummy operator)")
        return {'FINISHED'}

class REMESH_PT_settings_panel(bpy.types.Panel):
    bl_label = "Remesh Settings"
    bl_idname = "REMESH_PT_settings_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        layout.label(text="Remesh settings (dummy panel)")

class IMAGE_MASSING_PT_display_panel(bpy.types.Panel):
    bl_label = "Generated Images"
    bl_idname = "IMAGE_MASSING_PT_display_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'VIBE Massing'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Generated images (dummy panel)")

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
        bpy.utils.register_class(IMAGE_PT_display_panel)
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
        bpy.utils.unregister_class(IMAGE_PT_display_panel)
        bpy.utils.unregister_class(IMAGE_PT_reload_all)
        logging.info("Successfully unregistered image panel")
    except Exception as e:
        logging.error(f"Failed to unregister image panel: {e}")

# ... rest of the file ...

bl_info = {
    "name": "VIBE Forming",
    "blender": (2, 80, 0),
    "category": "3D View",
    "author": "VIBE Team",
    "version": (1, 0, 0),
    "description": "Hand tracking and mesh generation tools for VIBE",
}

if __name__ == "__main__":
    register()