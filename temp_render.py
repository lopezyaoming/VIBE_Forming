
import bpy
import sys
import os
import math

# Append path to the src directory
sys.path.append(r"C:\CODING\VIBE\VIBE_Forming\src")

# Output directory for renders
RENDER_OUTPUT_DIR = r"C:\CODING\VIBE\VIBE_Forming\input\COMFYINPUTS\blenderRender"
RENDER_CAMERA_NAME = "RenderCam"
RENDER_FRAMES = {
    0: "0.png",
    1: "front.png",
    2: "right.png",
    3: "back.png",
    4: "left.png"
}

def ensure_render_camera():
    """Create and configure the RenderCam if it doesn't exist"""
    render_cam = bpy.data.objects.get(RENDER_CAMERA_NAME)
    
    if not render_cam:
        print(f"Creating render camera: {RENDER_CAMERA_NAME}")
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
        
        print("Render camera configured with rotation animation")
    else:
        print(f"Using existing render camera: {RENDER_CAMERA_NAME}")
    
    return render_cam

def render_multiview():
    """
    Render multiple views using the RenderCam camera:
    - front view (frame 1)
    - right view (frame 2)
    - back view (frame 3)
    - left view (frame 4)
    """
    try:
        print("Starting manual multi-view render...")
        
        # Create output directory
        os.makedirs(RENDER_OUTPUT_DIR, exist_ok=True)
        print(f"Render output directory: {RENDER_OUTPUT_DIR}")
        
        # Get the render camera
        render_cam = ensure_render_camera()
        if not render_cam:
            print(f"Failed to create or get render camera: {RENDER_CAMERA_NAME}")
            return False
            
        # Store current camera and frame
        current_camera = bpy.context.scene.camera
        current_frame = bpy.context.scene.frame_current
        
        # Configure render settings
        bpy.context.scene.render.resolution_x = 1024
        bpy.context.scene.render.resolution_y = 1024
        bpy.context.scene.render.film_transparent = True
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        
        # Set render camera as active camera
        print(f"Setting {render_cam.name} as active camera")
        bpy.context.scene.camera = render_cam
        
        # Render each frame
        for frame, filename in RENDER_FRAMES.items():
            try:
                # Set frame
                bpy.context.scene.frame_current = frame
                
                # Set output path
                output_path = os.path.join(RENDER_OUTPUT_DIR, filename)
                bpy.context.scene.render.filepath = output_path
                
                # Render
                print(f"Rendering frame {frame} to {output_path}")
                bpy.ops.render.render(write_still=True)
                
                if os.path.exists(output_path):
                    print(f"Successfully rendered {filename}")
                else:
                    print(f"Render file not found after rendering: {output_path}")
                    
            except Exception as frame_error:
                print(f"Error rendering frame {frame}: {frame_error}")
        
        # Restore original camera and frame
        bpy.context.scene.camera = current_camera
        bpy.context.scene.frame_current = current_frame
        
        print("Multi-view render completed successfully")
        return True
    except Exception as e:
        print(f"Error in multi-view render: {e}")
        # Restore original camera and frame if possible
        try:
            if 'current_camera' in locals():
                bpy.context.scene.camera = current_camera
            if 'current_frame' in locals():
                bpy.context.scene.frame_current = current_frame
        except:
            pass
        return False

# Actually run the render function
try:
    render_result = render_multiview()
    print(f"Render result: {'Success' if render_result else 'Failed'}")
except Exception as e:
    print(f"Unhandled exception in render script: {str(e)}")
