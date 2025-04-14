# VIBE Forming Tool

A Blender add-on for the VIBE project that provides image display and new mesh generation through ComfyUI.

## Features

- Display and select from A/B/C design options
- Submit custom prompts for generating design alternatives
- Select and customize text prompts for generation
- Generate new 3D iterations based on rendered views of current models
- Automatically create and configure rendering camera
- Save selection results to output directory

## Directory Structure

The add-on uses the following directory structure:

```
VIBE_Forming/
├── input/
│   ├── options/            # Contains A.png, B.png, C.png design options for Blender display
│   ├── input.txt           # Input file for custom prompts
│   ├── COMFYINPUTS/
│   │   ├── blenderRender/  # Output directory for rendered views
│   │   ├── ImageOPTIONS/   # ComfyUI output for generated images
│   │   └── textOptions/    # For prompt text files (A_0001.txt, B_0001.txt, C_0001.txt)
├── output/
│   └── generated/
│       └── Models/         # Where generated mesh files are saved
└── src/
    ├── main.py             # The Blender add-on script (contains all functionality)
    └── comfyworkflows/     # ComfyUI workflow files and API scripts
        ├── VIBEMultiView.json  # Workflow for generating 3D models
        ├── VIBEOptions.json    # Workflow for generating 2D design options
        ├── multiview_API.py    # API script for running multi-view workflow
        └── options_API.py      # API script for generating design options
```

## Installation

1. Open Blender
2. Go to Edit > Preferences > Add-ons
3. Click "Install" and select the `main.py` file
4. Enable the add-on

## Usage

### Starting the Add-on

Run the script directly in Blender's Text Editor or install it as an add-on.

### Submitting Custom Requests

1. In the VIBE panel, locate the "Custom Request" section
2. Enter your prompt in the text field
3. Click "Submit Request" to generate new design options
4. Wait for the images to be generated and displayed in the panel

### Selecting Design Options

1. View the design options (A, B, C) in the VIBE panel
2. Click "Select A/B/C" to choose an option
3. Your selection will be saved to `output/selected_option.txt`
4. The corresponding text prompt will be applied for future iterations

### Selecting Text Prompts

1. Use the dropdown menu to select between Prompt A, B, or C
2. Toggle "Show Prompt Content" to view the text of the selected prompt
3. The selected prompt will be used for the next mesh generation

Text prompts are stored as:
- A_0001.txt: Abstract, futuristic sculpture
- B_0001.txt: Organic, biomechanical structure
- C_0001.txt: Crystalline, geometric composition

You can edit these files directly in the `input/COMFYINPUTS/textOptions/` directory to customize the prompts.

### Generating New Iterations

1. Make sure you have a 3D model in your scene
2. Select your desired text prompt using the dropdown
3. Ensure ComfyUI is running on localhost:8188
4. Click the "Generate New Iteration" button in the VIBE panel
5. The script will:
   - Render views from multiple angles (front, right, back, left)
   - Send these renders to ComfyUI for processing via direct HTTP requests
   - Import the resulting generated mesh back into Blender

This creates a complete pipeline:
1. Render → 2. Process in ComfyUI → 3. Import new mesh

### Refreshing Images

Click the "Refresh Images" button to reload all images from disk if you've generated new options externally.

### Terminating the Script

Click the "Terminate Script" button to unregister the add-on and stop the script.

## Requirements

- Blender 2.93 or newer
- ComfyUI installed and configured with Hunyuan3D model
- ComfyUI must be running on localhost:8188
- Required ComfyUI nodes:
  - Hy3DModelLoader
  - Hy3DGenerateMeshMultiView
  - Hy3DExportMesh

## Troubleshooting

### Image Display Issues

If images don't appear in the Blender panel:
- Images are generated in `input/COMFYINPUTS/ImageOPTIONS` and then copied to `input/options` for Blender to display
- Check that both directories exist and have the proper permissions
- Click the "Refresh Images" button to manually reload images from disk
- Use the "Submit Request" button to generate new options

### ComfyUI Connection

If the connection to ComfyUI fails:
- Ensure ComfyUI is running on localhost:8188
- Check the server address in the script (COMFYUI_SERVER constant)
- Check the Blender console for detailed error messages

### File Paths

The add-on uses absolute paths for file references. If you need to move the project:
1. Update the path constants in `main.py`
2. Update paths in `options_API.py` and `multiview_API.py`
3. Update file paths in ComfyUI workflow JSON files

## Development

### Main Components

- `main.py`: Blender add-on with UI, rendering, and mesh import
- `options_API.py`: Generates design alternatives via ComfyUI
- `multiview_API.py`: Processes rendered views to generate 3D models
- ComfyUI workflow JSON files: Define the processing pipelines

### Recent Updates

- Fixed image directory mismatch between ComfyUI output and Blender
- Added automatic image copying from `input/COMFYINPUTS/ImageOPTIONS` to `input/options`
- Added ability to submit custom requests directly from Blender
- Added image refresh functionality
- Updated LoadImage node to use absolute paths 