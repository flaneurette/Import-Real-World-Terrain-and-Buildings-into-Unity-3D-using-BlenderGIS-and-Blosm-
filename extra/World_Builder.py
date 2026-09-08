bl_info = {
    "name": "World Builder",
    "blender": (2, 83, 0),
    "category": "Object",
    "author": "Flaneurette",
    "description": "World Builder. Create 3D maps from real-world data, and render them accordingly.",
    "version": (1, 3, 0),
    "support": "COMMUNITY",
}

import bpy
import bmesh
import random
import os
import shutil
import math
from mathutils import Vector, Matrix
import time
import json
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, CollectionProperty, PointerProperty
import ctypes
import sys
from pathlib import Path
import gc
from datetime import datetime

# Global metadata storage
GLOB_BUILDINGS_META_DATA = []
GLOB_EXPORT_FOLDER = None
GLOB_TEXTURE_FOLDER = None
GLOB_START_TIME = None

# Default additional arguments
console_wall_thickness = 0.15
console_tex_width = 2.0
console_tex_height = 2.0
console_roof_threshold = 0.85
console_floor_height = 3.0
console_door_prob = 0.8
console_door_width = 2.0
console_door_height = 3.5
console_window_prob = 0.8
console_window_width = 1.0
console_window_height = 1.5

coloring_failed = False

# Define a property group for building metadata
class BuildingMetadata(bpy.types.PropertyGroup):
    building_id: StringProperty(name="Building ID")
    width: FloatProperty(name="Width")
    depth: FloatProperty(name="Depth")
    height: FloatProperty(name="Height")
    num_floors: IntProperty(name="Number of Floors")
    has_door: BoolProperty(name="Has Door")
    door_width: FloatProperty(name="Door Width")
    door_height: FloatProperty(name="Door Height")
    num_windows: IntProperty(name="Number of Windows")
    window_width: FloatProperty(name="Window Width")
    window_height: FloatProperty(name="Window Height")
    location_x: FloatProperty(name="Location X")
    location_y: FloatProperty(name="Location Y")
    location_z: FloatProperty(name="Location Z")
    
class WorldBuilderSettings(bpy.types.PropertyGroup):
    wall_thickness: bpy.props.FloatProperty(name="Wall Thickness", default=0.15)
    tex_width: bpy.props.FloatProperty(name="Texture Width", default=2.0)
    tex_height: bpy.props.FloatProperty(name="Texture Height", default=2.0)
    roof_threshold: bpy.props.FloatProperty(name="Roof Threshold", default=0.85)
    floor_height: bpy.props.FloatProperty(name="Floor Height", default=3.0)
    door_prob: bpy.props.FloatProperty(name="Door Probability", default=0.8)
    door_width: bpy.props.FloatProperty(name="Door Width", default=2.0)
    door_height: bpy.props.FloatProperty(name="Door Height", default=3.5)
    window_prob: bpy.props.FloatProperty(name="Window Probability", default=0.8)
    window_width: bpy.props.FloatProperty(name="Window Width", default=1.0)
    window_height: bpy.props.FloatProperty(name="Window Height", default=1.5)
    texture_folder: bpy.props.StringProperty(name="Texture Folder", default="//textures")
    export_folder: bpy.props.StringProperty(name="Export Folder", default="//export")
    solidify: bpy.props.BoolProperty(name="Solidify objects", default=True)

# Check if we can color console output.
if os.name == 'nt':
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        coloring_failed = True
        
# ----------------------------
# Helper functions
# ----------------------------
class DualStream: 
    
    def __init__(self, stream1, stream2, log_progress=False):
        self.stream1 = stream1
        self.stream2 = stream2
        self.log_progress = log_progress
        self._buffer = ""

    def write(self, message, base_time=None):

        if message.startswith('\r'):
            if not self.log_progress:
                return
            message = message.lstrip('\r')

        self._buffer += message

        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            if not line.strip():
                continue
            if not self.log_progress and "Progress:" in line:
                continue

            # Use base_time if provided, otherwise current time
            if base_time is None:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            else:
                timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(base_time))

            self.stream1.write(f"{timestamp} | {line}\n")
            self.stream1.flush()
            self.stream2.write(f"{timestamp} | {line}\n")

    def flush(self):
        self.stream1.flush()
        self.stream2.flush()

def run_stage(name, func):
	print_to_stream(f"Console starting process: {name}...\n", stream=None, base_time=time.time())
	func()
    
def print_to_stream(message, stream=None, base_time=None):
    
    global GLOB_EXPORT_FOLDER
    
    if not GLOB_EXPORT_FOLDER:
        if "bpy" not in globals():
            print("Cannot log results! Export folder is unknown!")
        return {'FINISHED'}

    os.makedirs(GLOB_EXPORT_FOLDER, exist_ok=True)
    log_file_path = os.path.join(GLOB_EXPORT_FOLDER, "console_log.txt")

    if stream is None:
        with open(log_file_path, 'a') as log_file:
            dual_stream = DualStream(sys.stdout, log_file, log_progress=False)
            dual_stream.write(f"= {message}\n", base_time=base_time)
            dual_stream.flush()
    else:
        stream.write(f"= {message}\n", base_time=base_time)
        stream.flush()

    return {'FINISHED'}

def messagebox_showerror(title, message):
    """Blender-native replacement for tkinter's messagebox.showerror.
    Shows a popup in the 3D Viewport and logs the error to the console/log file."""
    def draw(self, context):
        self.layout.label(text=str(message), icon='ERROR')
    try:
        bpy.context.window_manager.popup_menu(draw, title=str(title), icon='ERROR')
    except Exception:
        pass
    print_to_stream(f"{title}: {message}\n", stream=None, base_time=time.time())

def c(text, color):
    
    if os.name == 'nt' and coloring_failed:
        return text
 
    colors = {
        "cyan": "\033[96m",
        "yellow": "\033[93m",
        "green": "\033[92m",
        "red": "\033[91m",
        "magenta": "\033[95m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"

def auto_cast(value):
    if isinstance(value, str):
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        try:
            return float(value)
        except ValueError:
            return value
    return value

def load_cli_args():
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    params = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            params[key] = auto_cast(value)
    return params

def apply_cli_args_to_scene(params):
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    for key, value in params.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    
def ensure_global_export_folder():
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    if "export_folder" in globals() and globals()["export_folder"]:
        GLOB_EXPORT_FOLDER = globals()["export_folder"]
    if GLOB_EXPORT_FOLDER is None:
        print_to_stream(
            "Failed to acquire a global export folder. Script will cease now. "
            "Please provide a export folder using --export_folder argument.\n",
            stream=None, base_time=time.time()
        )
        sys.exit(1)
    if "texture_folder" in globals() and globals()["texture_folder"]:
        GLOB_TEXTURE_FOLDER = globals()["texture_folder"]
    if GLOB_TEXTURE_FOLDER is None:
        print_to_stream(
            "Failed to acquire a global texture folder. Script will cease now. "
            "Please provide a texture folder using --texture_folder argument.\n",
            stream=None, base_time=time.time()
        )
        sys.exit(1)
# ----------------------------
# Console generation functions
# ----------------------------  
def console_generate_buildings():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.run_pbr_export()
    print_to_stream(f"Processing console buildings generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_generate_openings():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.windows_and_doors()
    print_to_stream(f"Processing console openings (windows, doors, vents) generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_generate_vegetation():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.greenery()
    print_to_stream(f"Processing console vegetation generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_place_trees():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.place_trees()
    print_to_stream(f"Processing console tree placement took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}
    
def console_generate_water():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.waterways()
    print_to_stream(f"Processing console water generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_generate_railways():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.railways()
    print_to_stream(f"Processing console railways generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_generate_roads():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.roads()
    print_to_stream(f"Processing console roads generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_generate_terrain():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.terrain()
    print_to_stream(f"Processing console terrain generation took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def console_export_data():
    ensure_global_export_folder()
    global GLOB_EXPORT_FOLDER
    global GLOB_TEXTURE_FOLDER
    start_time = time.time()
    scn = bpy.context.scene
    settings = scn.pbr_export_settings
    bpy.ops.object.export_data()
    print_to_stream(f"Processing console export took: {time.time() - start_time:.2f} seconds.\n", stream=None, base_time=time.time())
    return {'FINISHED'}

def print_help_message():
    print(f"""
{c('World Builder Headless Usage:', 'cyan')}
-----------------------------
Usage command: blender -b --factory-startup <blend_file> -P <script> -- <script_args>
-----------------------------
Real world example: 
-----------------------------
blender -b --factory-startup "C:\\Users\\Gebruiker\\Desktop\\Game\\Blender\\Test4WORKING.blend"
-P "C:\\Users\\Gebruiker\\Desktop\\Game\\BlenderScripts\\World_Builder.py" --
export_folder="C:\\Users\\Gebruiker\\Desktop\\World Builder\\Export"
texture_folder="C:\\Users\\Gebruiker\\Desktop\\World Builder\\Textures"
--all=True
-----------------------------
{c('Arguments:', 'green')}
-----------------------------
{c('--export_folder=PATH', 'yellow')}      : (Required) Folder where export files are saved, e.g. "C:\\Users\\Username\\Desktop\\World Builder\\Export"
{c('--texture_folder=PATH', 'yellow')}      : (Required) (sub) folder(s) where all texture files are found, e.g. "C:\\Users\\Username\\Desktop\\World Builder\\Textures"
{c('Processing Options:', 'green')}
--all=True, --any=True     : Runs all available methods/functions in sequence, without needing to call them individually.
--process_buildings=True   : Texturizes buildings
--process_openings=True    : Generates random windows, doors and vents on each building (and also cuts out mesh openings.)
--process_roads=True       : Texturizes roads
--process_vegetation=True  : Texturizes vegetation
--process_trees=True       : Scatters placeholder trees across forest/park areas
--process_waterways=True   : Texturizes waterways such as rivers, lakes, etc.
--process_railways=True    : Texturizes railways
-----------------------------
{c('Overrides:', 'magenta')}
-----------------------------
NOTE: All float units should be in real world meters! most have default values, and rarely needs change.
--solidify=Bool            : Solidifies walls, if True. Default: True.
--wall_thickness=Float     : Thickness of the building walls when script applies SOLIDIFY boolean modifier. Default: 0.15 (15 centimeters in world units)
--tex_width=Float          : Texture width. Default: 2.0 (2048 x 2048 pixels)
--tex_height=Float         : Texture height. Default: 2.0 (2048 x 2048 pixels)
--roof_threshold=Float     : Threshold to automatically detect roofs. Default: 0.85
--floor_height=Float       : Height of individual floors in a building, used to determine window locations. Default: 3.0
--door_prob=Float          : Probability of a door being placed on a processed building. Default: 0.8
--door_width=Float         : Minimal width of generated doors. Default: 2.0
--door_height=Float        : Minimal height of generated doors. Default: 3.5
--window_prob=Float        : Probability of rows of windows being placed on a processed building. Default: 0.8
--window_width=Float       : Minimal width of generated windows. Default: 1.0
--window_height=Float      : Minimal height of generated windows. Default: 1.5
-----------------------------
--help, -h                 : Show this help message
-----------------------------
Tips: You can combine multiple processing options in one command.  
For example, to only process buildings, openings, and roads together:  
--process_buildings=True --process_openings=True --process_roads=True  

Use --all=True to run everything in sequence without specifying each option.
""")
    
# ===== Helper Functions =====

def blender_to_unity_coords(pos):
    return [pos[0], pos[2], -pos[1]]
    
def blender_to_unity_rotation(rot):
    return [
        math.degrees(-rot[0]),
        math.degrees(-rot[2]),
        math.degrees(-rot[1])
    ]
        
def copy_texture_for_unity(image_path, export_folder):
    if not os.path.exists(image_path):
        return None
    filename = os.path.basename(image_path)
    dest_path = os.path.join(export_folder, "Textures", filename)
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(image_path, dest_path)
        return dest_path
    except Exception as e:
        print_to_stream(f"Failed to copy {filename}: {e}", stream = None, base_time = time.time())
        return None

def get_or_create_pbr_material(base_name, texture_folder, export_folder):

    texture_folder = os.path.normpath(os.path.abspath(texture_folder))
    
    mat_name = f"PBR_{base_name}"
    mat = bpy.data.materials.get(mat_name)
    if mat:
        return mat
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (400, 0)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    # First pass: Load all textures
    textures = {}
    
    valid_image_extensions = ('.png', '.jpg', '.jpeg') 
    # Filter files to include only valid image files
    files = [f for f in os.listdir(texture_folder) if f.lower().endswith(valid_image_extensions)]
            
    if os.path.exists(texture_folder):
        
        for file in files:
            
            name_lower = file.lower()
            if not name_lower.startswith(base_name.lower()):
                continue
            path = os.path.join(texture_folder, file)
            if not os.path.isfile(path):
                continue
            # Identify texture type - handle multiple naming conventions
            if '_base_color' in name_lower or '_basecolor' in name_lower or '_albedo' in name_lower or '_diffuse' in name_lower:
                textures['albedo'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_normal' in name_lower:
                textures['normal'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_roughness' in name_lower:
                textures['roughness'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_metallic' in name_lower:
                textures['metallic'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_ambient_occlusion' in name_lower or '_ao' in name_lower or '_occlusion' in name_lower:
                textures['ao'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_height' in name_lower:
                textures['height'] = path
                copy_texture_for_unity(path, export_folder)
            elif '_maskmap' in name_lower or '_mask' in name_lower:
                textures['maskmap'] = path
                copy_texture_for_unity(path, export_folder)
    
    # Second pass: Create nodes and connections in proper order
    image_nodes = {}
    
    # 1. Albedo/Base Color
    if 'albedo' in textures:
        tex = nodes.new(type='ShaderNodeTexImage')
        tex.image = bpy.data.images.load(textures['albedo'])
        tex.location = (-600, 200)
        image_nodes['albedo'] = tex
        tex.image.pack()
        
        # Handle standalone AO if present (not in maskmap)
        if 'ao' in textures and 'maskmap' not in textures:
            ao_tex = nodes.new(type='ShaderNodeTexImage')
            ao_tex.image = bpy.data.images.load(textures['ao'])
            ao_tex.image.colorspace_settings.name = 'Non-Color'
            ao_tex.location = (-600, -100)
            ao_tex.image.pack()
            
            mix = nodes.new(type='ShaderNodeMixRGB')
            mix.blend_type = 'MULTIPLY'
            mix.inputs['Fac'].default_value = 1.0
            mix.location = (-300, 200)
            
            links.new(tex.outputs['Color'], mix.inputs[1])
            links.new(ao_tex.outputs['Color'], mix.inputs[2])
            links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
            
            image_nodes['ao'] = ao_tex
        else:
            # No standalone AO, direct connection (AO might be in maskmap)
            links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
        
        # Connect alpha if present
        if tex.image.channels == 4:
            links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
    
    # 2. Handle MaskMap (contains Metallic, AO, and Roughness in different channels)
    if 'maskmap' in textures:
        maskmap_tex = nodes.new(type='ShaderNodeTexImage')
        maskmap_tex.image = bpy.data.images.load(textures['maskmap'])
        maskmap_tex.image.colorspace_settings.name = 'Non-Color'
        maskmap_tex.location = (-900, -400)
        image_nodes['maskmap'] = maskmap_tex
        maskmap_tex.image.pack()
        # Separate RGB to extract individual channels
        separate = nodes.new(type='ShaderNodeSeparateRGB')
        separate.location = (-600, -400)
        links.new(maskmap_tex.outputs['Color'], separate.inputs['Image'])
        
        # Red channel = Metallic
        links.new(separate.outputs['R'], bsdf.inputs['Metallic'])
        
        # Green channel = AO (mix with albedo if we have albedo)
        if 'albedo' in textures:
            ao_mix = nodes.new(type='ShaderNodeMixRGB')
            ao_mix.blend_type = 'MULTIPLY'
            ao_mix.inputs['Fac'].default_value = 1.0
            ao_mix.location = (-300, 200)
            links.new(image_nodes['albedo'].outputs['Color'], ao_mix.inputs[1])
            links.new(separate.outputs['G'], ao_mix.inputs[2])
            links.new(ao_mix.outputs['Color'], bsdf.inputs['Base Color'])
        
        # Alpha channel = Smoothness, need to invert for Roughness
        invert = nodes.new(type='ShaderNodeInvert')
        invert.location = (-300, -400)
        links.new(maskmap_tex.outputs['Alpha'], invert.inputs['Color'])
        links.new(invert.outputs['Color'], bsdf.inputs['Roughness'])
    
    # 3. Normal and Height (with proper chaining)
    normal_input = bsdf.inputs['Normal']
    
    if 'height' in textures:
        height_tex = nodes.new(type='ShaderNodeTexImage')
        height_tex.image = bpy.data.images.load(textures['height'])
        height_tex.image.colorspace_settings.name = 'Non-Color'
        height_tex.location = (-600, -600)
        height_tex.image.pack()
        bump = nodes.new(type='ShaderNodeBump')
        bump.location = (-300, -600)
        bump.inputs['Strength'].default_value = 0.3
        
        links.new(height_tex.outputs['Color'], bump.inputs['Height'])
        normal_input = bump.inputs['Normal']  # Next normal connects here
        
        image_nodes['height'] = height_tex
        image_nodes['bump'] = bump
    
    if 'normal' in textures:
        normal_tex = nodes.new(type='ShaderNodeTexImage')
        normal_tex.image = bpy.data.images.load(textures['normal'])
        normal_tex.image.colorspace_settings.name = 'Non-Color'
        normal_tex.location = (-600, -800)
        normal_tex.image.pack()
        normal_map = nodes.new(type='ShaderNodeNormalMap')
        normal_map.location = (-300, -800)
        
        links.new(normal_tex.outputs['Color'], normal_map.inputs['Color'])
        links.new(normal_map.outputs['Normal'], normal_input)
        
        # If we have height, connect its output to BSDF
        if 'height' in textures:
            links.new(image_nodes['bump'].outputs['Normal'], bsdf.inputs['Normal'])
        else:
            links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
        
        image_nodes['normal'] = normal_tex
    elif 'height' in textures:
        # Only height, no normal
        links.new(image_nodes['bump'].outputs['Normal'], bsdf.inputs['Normal'])
    
    # 4. Roughness (standalone - only if no maskmap)
    if 'roughness' in textures and 'maskmap' not in textures:
        tex = nodes.new(type='ShaderNodeTexImage')
        tex.image = bpy.data.images.load(textures['roughness'])
        tex.image.colorspace_settings.name = 'Non-Color'
        tex.location = (-600, -1000)
        links.new(tex.outputs['Color'], bsdf.inputs['Roughness'])
        image_nodes['roughness'] = tex
        tex.image.pack()
    # 5. Metallic (standalone - only if no maskmap)
    if 'metallic' in textures and 'maskmap' not in textures:
        tex = nodes.new(type='ShaderNodeTexImage')
        tex.image = bpy.data.images.load(textures['metallic'])
        tex.image.colorspace_settings.name = 'Non-Color'
        tex.location = (-600, -1200)
        tex.image.pack()
        links.new(tex.outputs['Color'], bsdf.inputs['Metallic'])
        image_nodes['metallic'] = tex
    
    return mat

def get_or_create_material_auto(base_name, texture_folder, export_folder, random_select=True):

    # Check if we should scan subfolders
    subfolders = []
    if os.path.exists(texture_folder):
        for item in os.listdir(texture_folder):
            item_path = os.path.join(texture_folder, item)
            if os.path.isdir(item_path):
                subfolders.append(item_path)
    
    # If we have subfolders and random_select is True, pick one randomly
    if subfolders and random_select:
        chosen_subfolder = random.choice(subfolders)
        # Now scan within this subfolder
        search_folder = chosen_subfolder
    else:
        # Use the main folder directly
        search_folder = texture_folder
    
    files = [f for f in os.listdir(search_folder) if os.path.isfile(os.path.join(search_folder, f))]
                
    # Find all unique texture sets that match the base pattern
    if random_select:
        # Extract all unique set identifiers (e.g., "T02", "T03", "T04")
        texture_sets = set()
        
        for f in files:
            f_lower = f.lower()
            base_lower = base_name.lower()
             
            # Check if file matches base name
            if not f_lower.startswith(base_lower):
                continue
            
            # Check if it's a PBR texture type
            if not any(x in f_lower for x in ["_base_color", "_basecolor", "_albedo", "_diffuse", 
                                               "_normal", "_roughness", "_metallic", "_ao", 
                                               "_ambient_occlusion", "_maskmap", "_height"]):
                continue
            
            # Extract the set identifier (everything between base_name and texture type)
            after_base = f[len(base_name):]  # "_T02_Base_Color"
            
            # Find the texture type position
            for tex_type in ["_base_color", "_basecolor", "_albedo", "_diffuse", "_normal", 
                           "_roughness", "_metallic", "_ao", "_ambient_occlusion", "_maskmap", "_height"]:
                if tex_type in f_lower:
                    # Get everything before the texture type
                    type_pos = f_lower.find(tex_type)
                    set_id = f[:type_pos]  # "Outdoor_Wall_T02"
                    
                    # Extract just the variant part (e.g., "T02")
                    variant = set_id[len(base_name):].strip('_')  # "T02"
                    if variant:
                        texture_sets.add(variant)
                    break
        
        if texture_sets:
            # Randomly pick one set
            chosen_set = random.choice(list(texture_sets))
            full_base_name = f"{base_name}_{chosen_set}"
            folder_name = os.path.basename(search_folder)
            return get_or_create_pbr_material(full_base_name, search_folder, export_folder)
    
    # Non-random mode: use the exact base_name provided
    pbr_files = [f for f in files if base_name.lower() in f.lower() and 
                 any(x in f.lower() for x in ["_base_color", "_basecolor", "_albedo", "_diffuse", 
                                               "_normal", "_roughness", "_metallic", "_ao", 
                                               "_ambient_occlusion", "_maskmap", "_height"])]
    
    if pbr_files:
        return get_or_create_pbr_material(base_name, search_folder, export_folder)

    # Fallback: Single PNG mode
    candidates = [f for f in files if base_name.lower() in f.lower() and 
                  f.lower().endswith(('.png', '.jpg', '.jpeg', '.avif'))]
    if not candidates:
        return None

    if random_select:
        chosen_file = random.choice(candidates)
    else:
        chosen_file = candidates[0]

    mat_name = f"{base_name}_{os.path.splitext(chosen_file)[0]}"
    mat = bpy.data.materials.get(mat_name)
    if mat:
        return mat

    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    mat.blend_method = 'OPAQUE'
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type='ShaderNodeOutputMaterial')
    output.location = (300, 0)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    path = os.path.join(search_folder, chosen_file)
    tex = nodes.new(type='ShaderNodeTexImage')
    tex.image = bpy.data.images.load(path)
    tex.location = (-300, 0)
    links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

    if tex.image.channels == 4:
        links.new(tex.outputs['Alpha'], bsdf.inputs['Alpha'])
        mat.blend_method = 'HASHED'

    return mat

def face_local_axes(mesh, poly):
    verts = [mesh.vertices[i].co.copy() for i in poly.vertices]
    if len(verts) < 2: return None,None,None
    edge = verts[1] - verts[0]
    edge.z = 0.0
    u = edge.normalized() if edge.length_squared>0 else Vector((1,0,0))
    return u, Vector((0,0,1)), poly.center.copy()

def project_vertex_along_u(vert_co, origin, u):
    rel = vert_co - origin
    return rel.dot(u), vert_co.z

def ensure_material_black(name):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (0,0,0,1)
    bsdf.inputs['Roughness'].default_value = 0.9
    nodes.new('ShaderNodeBsdfPrincipled')
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    try: mat.diffuse_color = (0,0,0,1)
    except: pass
    return mat
    
def generate_face_uvs(mesh, face, uv_layer, tex_width, tex_height):
    # Ensure UV layer has data
    if len(uv_layer.data) == 0:
        return  # Skip if no UV data
    
    normal = face.normal
    if abs(normal.z) > 0.7:
        u_axis = Vector((1, 0, 0))
        v_axis = Vector((0, 1, 0))
    elif abs(normal.x) > abs(normal.y):
        u_axis = Vector((0, 1, 0))
        v_axis = Vector((0, 0, 1))
    else:
        u_axis = Vector((1, 0, 0))
        v_axis = Vector((0, 0, 1))
    
    for loop_index in face.loop_indices:
        # Safety check
        if loop_index >= len(uv_layer.data):
            continue
            
        loop = mesh.loops[loop_index]
        vert = mesh.vertices[loop.vertex_index]
        u = vert.co.dot(u_axis) / tex_width
        v = vert.co.dot(v_axis) / tex_height
        uv_layer.data[loop_index].uv = (u, v)

def prepare_mesh_fast(obj):
    try:
        mesh = obj.data
        if mesh.has_custom_normals:
            mesh.free_normals_split()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()
        mesh.normal_update()
        mesh.calc_normals_split()
        mesh.update()
        return True
    except Exception as e:
        return False

def get_all_children(obj):
    all_children = []
    for child in obj.children:
        all_children.append(child)
        all_children.extend(get_all_children(child))
    return all_children
    
def get_all_objects_in_collection(coll):
    all_objs = list(coll.objects)  # objects directly in this collection
    for child_coll in coll.children:  # child collections
        all_objs.extend(get_all_objects_in_collection(child_coll))
    return all_objs

# ===== Tree placement (placeholder trees, real mesh instances) =====

def get_or_create_flat_material(name, color, roughness=0.9):
    """Simple flat Principled BSDF material, cached by name so re-runs reuse it."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    return mat

def _bmesh_create_cone(bm, cap_ends, cap_tris, segments, r1, r2, depth):
    """Blender <~3.0 bmesh.ops.create_cone takes diameter1/diameter2; newer
    versions take radius1/radius2. Try the modern kwargs first, fall back."""
    try:
        return bmesh.ops.create_cone(
            bm, cap_ends=cap_ends, cap_tris=cap_tris, segments=segments,
            radius1=r1, radius2=r2, depth=depth
        )
    except TypeError:
        return bmesh.ops.create_cone(
            bm, cap_ends=cap_ends, cap_tris=cap_tris, segments=segments,
            diameter1=r1 * 2, diameter2=r2 * 2, depth=depth
        )

def _bmesh_create_icosphere(bm, subdivisions, r):
    """Same story as _bmesh_create_cone: 'radius' on newer Blender, 'diameter' on older."""
    try:
        return bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=r)
    except TypeError:
        return bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, diameter=r * 2)

def get_or_create_tree_mesh(variant="cone", trunk_radius=0.15, trunk_height=1.8,
                             canopy_radius=1.4, canopy_height=3.0, canopy_segments=7):
    """Builds a small low-poly placeholder tree (trunk + canopy) once and caches
    it in bpy.data.meshes so every placed tree instance shares the same mesh data."""
    mesh_name = f"WB_TreeMesh_{variant}"
    if mesh_name in bpy.data.meshes:
        return bpy.data.meshes[mesh_name]

    bm = bmesh.new()

    trunk = _bmesh_create_cone(
        bm, cap_ends=True, cap_tris=False, segments=6,
        r1=trunk_radius, r2=trunk_radius * 0.75, depth=trunk_height
    )
    bmesh.ops.translate(bm, verts=trunk['verts'], vec=(0, 0, trunk_height / 2))

    if variant == "round":
        canopy = _bmesh_create_icosphere(bm, subdivisions=1, r=canopy_radius)
        canopy_center_z = trunk_height + canopy_radius * 0.7
    else:
        canopy = _bmesh_create_cone(
            bm, cap_ends=True, cap_tris=False, segments=canopy_segments,
            r1=canopy_radius, r2=0.0, depth=canopy_height
        )
        canopy_center_z = trunk_height + canopy_height / 2

    bmesh.ops.translate(bm, verts=canopy['verts'], vec=(0, 0, canopy_center_z))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    bark_mat = get_or_create_flat_material("WB_TreeBark", (0.14, 0.09, 0.05, 1.0))
    leaf_mat = get_or_create_flat_material("WB_TreeLeaves", (0.07, 0.22, 0.08, 1.0))
    mesh.materials.append(bark_mat)
    mesh.materials.append(leaf_mat)
    trunk_top_z = trunk_height * 0.9
    for poly in mesh.polygons:
        avg_z = sum(mesh.vertices[v].co.z for v in poly.vertices) / len(poly.vertices)
        poly.material_index = 0 if avg_z < trunk_top_z else 1

    return mesh

def sample_points_on_mesh(obj, density, rng):
    """Non-destructively triangulates a copy of obj's mesh (original is left
    untouched) and area-weight samples world-space points across its faces."""
    points = []
    matrix = obj.matrix_world
    normal_matrix = matrix.to_3x3()

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])

    for tri in bm.faces:
        verts = tri.verts
        if len(verts) != 3:
            continue
        v0 = matrix @ verts[0].co
        v1 = matrix @ verts[1].co
        v2 = matrix @ verts[2].co
        area = (v1 - v0).cross(v2 - v0).length / 2.0
        expected = area * density
        count = int(expected)
        if rng.random() < (expected - count):
            count += 1
        if count <= 0:
            continue
        normal = (normal_matrix @ tri.normal).normalized()
        for _ in range(count):
            r1 = rng.random()
            r2 = rng.random()
            sqrt_r1 = math.sqrt(r1)
            a = 1 - sqrt_r1
            b = sqrt_r1 * (1 - r2)
            c = sqrt_r1 * r2
            point = v0 * a + v1 * b + v2 * c
            points.append((point, normal))

    bm.free()
    return points

def filter_points_by_spacing(points, min_spacing):
    """Thins out points that fall closer together than min_spacing using a
    simple spatial hash grid, so trees don't clump unnaturally."""
    if min_spacing <= 0 or not points:
        return points
    cell = min_spacing
    grid = {}
    kept = []
    for point, normal in points:
        key = (int(point.x // cell), int(point.y // cell))
        too_close = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for other in grid.get((key[0] + dx, key[1] + dy), []):
                    if (other - point).length < min_spacing:
                        too_close = True
                        break
                if too_close:
                    break
            if too_close:
                break
        if not too_close:
            grid.setdefault(key, []).append(point)
            kept.append((point, normal))
    return kept

def build_terrain_raycaster(terrain_obj):
    """Builds a reusable BVH tree (in the terrain's local space) ONCE per scatter
    run, so per-tree raycasts don't each pay the cost of re-fetching the
    depsgraph and re-evaluating the terrain object. Returns
    (bvh, matrix_world, matrix_world_inverted) or None if terrain_obj is None."""
    if terrain_obj is None:
        return None
    try:
        from mathutils.bvhtree import BVHTree
        depsgraph = bpy.context.evaluated_depsgraph_get()
        bvh = BVHTree.FromObject(terrain_obj, depsgraph)
        matrix = terrain_obj.matrix_world.copy()
        return (bvh, matrix, matrix.inverted())
    except Exception as e:
        print_to_stream(f"Could not build terrain raycaster, trees will use the forest mesh's own height: {e}", stream=None, base_time=time.time())
        return None

def get_ground_z(raycaster, x, y, fallback_z):
    """Uses a prebuilt terrain raycaster (see build_terrain_raycaster) to find
    the true ground height at (x, y). Falls back to fallback_z if there's no
    raycaster or the ray misses (e.g. off the terrain edge)."""
    if raycaster is None:
        return fallback_z
    bvh, matrix, matrix_inv = raycaster
    ray_origin_local = matrix_inv @ Vector((x, y, 100000.0))
    ray_dir_local = (matrix_inv.to_3x3() @ Vector((0, 0, -1))).normalized()
    location, normal, index, distance = bvh.ray_cast(ray_origin_local, ray_dir_local)
    if location is not None:
        return (matrix @ location).z
    return fallback_z

def get_terrain_base_z(terrain_obj):
    """Returns the lowest world-space Z of terrain_obj's bounding box, used to
    normalize real-world SRTM elevation (often tens/hundreds of meters above
    sea level) down to a local ground level of ~0."""
    if terrain_obj is None:
        return 0.0
    try:
        bbox_world = [terrain_obj.matrix_world @ Vector(corner) for corner in terrain_obj.bound_box]
        return min(v.z for v in bbox_world)
    except Exception as e:
        print_to_stream(f"Could not compute terrain base elevation: {e}", stream=None, base_time=time.time())
        return 0.0

def get_tree_mesh_sources(names_csv):
    """Parses a comma-separated string of existing MESH object names already
    in the scene and returns their mesh data blocks, to be used as tree
    instances instead of the procedural placeholder geometry. The source
    objects themselves are hidden from render/viewport (not deleted) once
    picked up, since every placed tree references their mesh data directly."""
    sources = []
    names = []
    for raw_name in (names_csv or "").split(","):
        name = raw_name.strip()
        if not name:
            continue
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != 'MESH':
            print_to_stream(f"Tree source object '{name}' not found or not a mesh - skipping.", stream=None, base_time=time.time())
            continue
        sources.append(obj.data)
        names.append(name)
        obj.hide_render = True
        obj.hide_set(True)
    return sources, names

def scatter_trees_in_collection(area_name_substr, density, min_scale, max_scale,
                                 min_spacing, seed, tree_variants=("cone", "round"),
                                 terrain_obj_name="", tree_source_objects="",
                                 auto_normalize_z=True, z_offset=0.0):
    """Finds the first top-level collection whose name contains area_name_substr
    (e.g. 'forest', 'vegetation'), then scatters tree objects across every MESH
    object found inside it, weighted by face area. If tree_source_objects names
    real tree mesh(es) already in the scene, those are instanced instead of the
    procedural placeholders. If terrain_obj_name matches an object in the scene,
    tree height is taken from a raycast onto that terrain instead of trusting
    the forest mesh's own (possibly modifier-driven) Z. If auto_normalize_z is
    True, the terrain's own lowest point is subtracted so trees land relative
    to local ground level (~0) instead of real-world SRTM elevation; z_offset
    is then added on top for any further manual nudging."""
    rng = random.Random(seed)

    coll = select_top_level_collection_by_name(area_name_substr)
    if not coll:
        print_to_stream(f"No collection matching '{area_name_substr}' found - skipping tree placement.", stream=None, base_time=time.time())
        return 0

    all_children = get_all_objects_in_collection(coll)

    # Same curve->mesh safety net used before texturing, so curve-based
    # OSM areas don't silently get skipped here either.
    curve_objs = [obj for obj in all_children if obj.type == 'CURVE']
    if curve_objs:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in curve_objs:
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
        try:
            bpy.ops.object.convert(target='MESH')
        except Exception as e:
            print_to_stream(f"Curve to mesh conversion failed before tree placement: {e}", stream=None, base_time=time.time())
        all_children = get_all_objects_in_collection(coll)

    meshes = [obj for obj in all_children if obj.type == 'MESH']
    if not meshes:
        print_to_stream(f"No MESH area found under '{area_name_substr}' - nothing to scatter trees on.", stream=None, base_time=time.time())
        return 0

    custom_meshes, custom_names = get_tree_mesh_sources(tree_source_objects)
    if custom_meshes:
        tree_meshes = custom_meshes
        tree_variants = custom_names
        print_to_stream(f"Using {len(custom_meshes)} custom tree source object(s): {', '.join(custom_names)}", stream=None, base_time=time.time())
    else:
        tree_meshes = [get_or_create_tree_mesh(v) for v in tree_variants]

    terrain_obj = bpy.data.objects.get(terrain_obj_name) if terrain_obj_name else None
    if terrain_obj_name and terrain_obj is None:
        print_to_stream(f"Terrain object '{terrain_obj_name}' not found - trees will use the forest mesh's own height.", stream=None, base_time=time.time())

    terrain_base_z = get_terrain_base_z(terrain_obj) if (terrain_obj and auto_normalize_z) else 0.0
    if terrain_obj and auto_normalize_z:
        print_to_stream(f"Normalizing tree height: subtracting terrain base elevation {terrain_base_z:.2f}", stream=None, base_time=time.time())

    raycaster = build_terrain_raycaster(terrain_obj)

    trees_collection_name = "WB_Trees"
    if trees_collection_name in bpy.data.collections:
        trees_collection = bpy.data.collections[trees_collection_name]
    else:
        trees_collection = bpy.data.collections.new(trees_collection_name)
        bpy.context.scene.collection.children.link(trees_collection)

    placed = 0
    z_min, z_max = None, None
    sample_time = 0.0
    place_time = 0.0
    raw_point_total = 0
    for obj in meshes:
        t0 = time.time()
        raw_points = sample_points_on_mesh(obj, density, rng)
        points = filter_points_by_spacing(raw_points, min_spacing)
        sample_time += time.time() - t0
        raw_point_total += len(raw_points)

        t0 = time.time()
        for point, normal in points:
            variant_idx = rng.randrange(len(tree_variants))
            tree_data = tree_meshes[variant_idx]
            tree_obj = bpy.data.objects.new(f"Tree_{tree_variants[variant_idx]}_{placed:05d}", tree_data)

            raw_z = get_ground_z(raycaster, point.x, point.y, point.z)
            z = raw_z - terrain_base_z + z_offset
            tree_obj.location = (point.x, point.y, z)
            z_min = z if z_min is None else min(z_min, z)
            z_max = z if z_max is None else max(z_max, z)

            tree_obj.rotation_euler[2] = rng.uniform(0, math.pi * 2)
            scale = rng.uniform(min_scale, max_scale)
            tree_obj.scale = (scale, scale, scale * rng.uniform(0.9, 1.1))
            tree_obj["WB_TreeVariant"] = tree_variants[variant_idx]
            trees_collection.objects.link(tree_obj)
            placed += 1
        place_time += time.time() - t0

    if placed:
        print_to_stream(f"Tree Z range placed: {z_min:.2f} to {z_max:.2f}", stream=None, base_time=time.time())
    print_to_stream(f"Sampled {raw_point_total} candidate points ({sample_time:.2f}s) before spacing filter, placed {placed} objects ({place_time:.2f}s, incl. raycasting).", stream=None, base_time=time.time())
    if raw_point_total > 20000:
        print_to_stream(f"Note: {raw_point_total} candidate points is a lot for a single area - if this feels slow, try lowering Tree Density or raising Min Tree Spacing.", stream=None, base_time=time.time())
    print_to_stream(f"Placed {placed} trees across {len(meshes)} area(s) matching '{area_name_substr}'.\n", stream=None, base_time=time.time())
    return placed

def create_cube_verts_faces(width, depth, height):
    # Half sizes
    hw = width / 2
    hd = depth / 2
    hh = height / 2

    # Vertices of a cube centered at origin
    verts = [
        Vector((-hw, -hd, -hh)),
        Vector(( hw, -hd, -hh)),
        Vector(( hw,  hd, -hh)),
        Vector((-hw,  hd, -hh)),
        Vector((-hw, -hd,  hh)),
        Vector(( hw, -hd,  hh)),
        Vector(( hw,  hd,  hh)),
        Vector((-hw,  hd,  hh)),
    ]

    # Faces as list of vertex indices
    faces = [
        (0, 1, 2, 3),  # bottom
        (4, 5, 6, 7),  # top
        (0, 1, 5, 4),  # front
        (1, 2, 6, 5),  # right
        (2, 3, 7, 6),  # back
        (3, 0, 4, 7),  # left
    ]

    return verts, faces

def finalize_mesh_with_normals(bm, mesh):
    """Finalize bmesh and calculate normals properly"""
    bm.normal_update()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    mesh.calc_normals_split()
    
def round_coord(value, decimals=2):
    return round(value, decimals)

def round_vec(vec, decimals=2):
    return [round_coord(v, decimals) for v in vec]

def cut_opening_from_walls(building_obj, door_obj, wall_depth=0.15):

    if building_obj.type != 'MESH' or door_obj.type != 'MESH':
        return

    # --- STEP 1: Temporarily extrude the door along its local Y-axis ---
    # Duplicate door vertices in bmesh
    bm = bmesh.new()
    bm.from_mesh(door_obj.data)

    # Calculate door local "depth" direction (assuming Y points forward)
    # If your doors are aligned differently, change the axis
    for v in bm.verts:
        v.co.y -= wall_depth / 2  # move back

    # Update the mesh with the modified bmesh data
    bm.normal_update()
    bm.to_mesh(door_obj.data)
    door_obj.data.update()

    # Ensure normals are recalculated after geometry changes
    door_obj.data.calc_normals_split()
    
    # Free the bmesh after use
    bm.free()
    
    # --- STEP 2: Add Boolean modifier ---
    mod = building_obj.modifiers.new(name=f"DoorBoolean_{door_obj.name}", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = door_obj
    building_obj.data.update()
    

def batch_create_doors(building_obj, settings, doors_collection):
    """
    Fast creation of doors for a building using a single mesh per building.
    Returns the created door mesh object.
    """
    doors_collection_name = f"Doors"
    doors_collection = bpy.data.collections[doors_collection_name]
    door_depth = 0.025
    
    # Check if object has mesh data
    if building_obj.type != 'MESH' or not building_obj.data:
        return None
    
    mesh = building_obj.data
    
    # Safety check - ensure mesh has vertices
    if len(mesh.vertices) == 0:
        return None  # Silently skip empty meshes

    mesh_name = f"Doors_{building_obj.name}"
    door_mesh = bpy.data.meshes.new(mesh_name)
    door_obj = bpy.data.objects.new(mesh_name, door_mesh)

    # Link to scene collection
    doors_collection.objects.link(door_obj)
    door_obj.parent = building_obj

    bm = bmesh.new()
    door_global_id = 0
    
    # Find the ground level
    ground_z = min(v.co.z for v in mesh.vertices)
    DOOR_FIXED_Z = 0.0

    # GROUP WALLS: Cluster polygons into logical wall sections
    wall_groups = []
    used_polys = set()
    
    for poly in mesh.polygons:
        if poly.index in used_polys:
            continue
            
        if abs(poly.normal.z) > settings.roof_threshold:
            continue  # skip roofs
        
        # Check if wall touches ground
        min_z = min(mesh.vertices[vi].co.z for vi in poly.vertices)
        if min_z > ground_z + 0.1:
            continue
        
        # Start a new wall group with this polygon
        wall_group = [poly.index]
        used_polys.add(poly.index)
        
        # Find similar adjacent polygons (similar normal direction)
        for other_poly in mesh.polygons:
            if other_poly.index in used_polys:
                continue
            
            if abs(other_poly.normal.z) > settings.roof_threshold:
                continue
            
            # Check if normals are similar (angle < 30 degrees)
            angle = poly.normal.angle(other_poly.normal)
            if angle < 0.52:  # ~30 degrees in radians
                # Check if they share an edge (are adjacent)
                shared_verts = set(poly.vertices) & set(other_poly.vertices)
                if len(shared_verts) >= 2:  # Share an edge
                    wall_group.append(other_poly.index)
                    used_polys.add(other_poly.index)
        
        wall_groups.append(wall_group)
    
    # PLACE ONE DOOR PER WALL GROUP
    doors_placed = 0
    for wall_group in wall_groups:
        if doors_placed >= 3:  # Limit to 3 doors per building
            break
            
        # Decide if we place a door on this wall
        if random.random() > settings.door_prob:
           continue
        
        # Use the first polygon in the group as representative
        poly = mesh.polygons[wall_group[0]]
        
        # Calculate the average normal and center of the entire wall group
        avg_normal = Vector((0, 0, 0))
        all_verts = []
        for poly_idx in wall_group:
            group_poly = mesh.polygons[poly_idx]
            avg_normal += group_poly.normal
            for vi in group_poly.vertices:
                all_verts.append(mesh.vertices[vi].co)
        
        avg_normal.normalize()
        
        # Compute the center point of all vertices in the wall group
        wall_center = sum(all_verts, Vector((0, 0, 0))) / len(all_verts)
        
        # Create local coordinate system based on average normal
        normal_local = avg_normal
        
        # Create u vector (horizontal along wall)
        if abs(normal_local.z) < 0.99:
            u_local = normal_local.cross(Vector((0, 0, 1)))
            u_local.normalize()
        else:
            u_local = Vector((1, 0, 0))
        
        # v_local points up along the wall
        v_local = normal_local.cross(u_local)
        v_local.normalize()
        
        # Project all wall vertices onto the local 2D coordinate system
        all_xs = []
        all_ys = []
        all_zs = []
        
        for vert_co in all_verts:
            x = (vert_co - wall_center).dot(u_local)
            y = (vert_co - wall_center).dot(normal_local)
            z = vert_co.z
            all_xs.append(x)
            all_ys.append(y)
            all_zs.append(z)
        
        min_x, max_x = min(all_xs), max(all_xs)
        avg_y = sum(all_ys) / len(all_ys)  # Average depth to wall surface
        min_z, max_z = min(all_zs), max(all_zs)
        
        wall_width = max_x - min_x
        wall_height = max_z - min_z
        
        if wall_width <= 0.01 or wall_height <= 0.01:
            continue

        # Fixed door dimensions
        door_w = settings.door_width
        door_h = settings.door_height
        door_depth = 0.025 # 2.5 centimeters depth
        # Make sure door fits
        if door_w > wall_width or door_h > wall_height:
            continue
            
        # Place door randomly along the wall width
        door_local_x = random.uniform(min_x + door_w/2, max_x - door_w/2)

        # Create door vertices (in local space)
        half_depth = door_depth / 2
        verts = [
            Vector((-door_w/2, -half_depth, 0)),
            Vector((door_w/2, -half_depth, 0)),
            Vector((door_w/2, half_depth, 0)),
            Vector((-door_w/2, half_depth, 0)),
            Vector((-door_w/2, -half_depth, door_h)),
            Vector((door_w/2, -half_depth, door_h)),
            Vector((door_w/2, half_depth, door_h)),
            Vector((-door_w/2, half_depth, door_h)),
        ]

        # Calculate door position on the wall
        # Start from wall center, move along u_local by door_local_x
        door_position = Vector((wall_center.x, wall_center.y, DOOR_FIXED_Z))
        door_position += u_local * door_local_x
        # Move to wall surface (use average y position)
        door_position += normal_local * avg_y
        door_position -= normal_local * door_depth  # correct subtraction
        # Add small offset to prevent z-fighting
        door_position += normal_local * 0.01

        # Create rotation matrix
        z_local = Vector((0, 0, 1))
        rot_mat = Matrix((
            u_local,
            normal_local,
            z_local
        )).transposed()

        # Transform door vertices to world space
        transformed_verts_local = [rot_mat @ v + door_position for v in verts]
        vert_idxs = [bm.verts.new(v) for v in transformed_verts_local]
        
        # Create faces
        
        bm.faces.new([vert_idxs[i] for i in [0, 1, 2, 3]])
        bm.faces.new([vert_idxs[i] for i in [4, 5, 6, 7]])
        bm.faces.new([vert_idxs[i] for i in [0, 1, 5, 4]])
        bm.faces.new([vert_idxs[i] for i in [1, 2, 6, 5]])
        bm.faces.new([vert_idxs[i] for i in [2, 3, 7, 6]])
        bm.faces.new([vert_idxs[i] for i in [3, 0, 4, 7]])

        # Store metadata
        door_global_id += 1
        door_obj[f"Door_{door_global_id}_Width"] = round(door_w, 3)
        door_obj[f"Door_{door_global_id}_Height"] = round(door_h, 3)
        door_obj[f"Door_{door_global_id}_WallGroup"] = str(wall_group)
        door_obj[f"Door_{door_global_id}_LocalX"] = round(door_local_x, 3)
        door_obj[f"Door_{door_global_id}_LocalZ"] = DOOR_FIXED_Z
        
        doors_placed += 1

    # Finalize mesh
    finalize_mesh_with_normals(bm, door_mesh)

    # Assign material
    
    door_mat = bpy.data.materials.get("Preview_Door_Mat")
    if not door_mat:
        door_mat = bpy.data.materials.new("Preview_Door_Mat")
        door_mat.use_nodes = True
        nodes = door_mat.node_tree.nodes
        nodes.clear()
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 0.5)
        output = nodes.new('ShaderNodeOutputMaterial')
        door_mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if len(door_obj.data.materials) == 0:
        door_obj.data.materials.append(door_mat)
    else:
        door_obj.data.materials[0] = door_mat
  
    cut_opening_from_walls(building_obj, door_obj, door_depth)
    
    return door_obj

def batch_create_windows(building_obj, settings, windows_collection):
    """
    Fast creation of windows for a building using a single mesh per building.
    Returns the created window mesh object.
    """
    # Window placement settings
    WINDOW_MARGIN = 0.5  # Space from edges and between windows
    FLOOR_BOTTOM_MARGIN = 3.5  # Distance from floor
    FLOOR_TOP_MARGIN = 3.0  # Distance from ceiling (larger to avoid sloped roofs)
    WALL_OFFSET = 0.01
    DOOR_OFFSET = 3 # This allows windows to be placed above doors.
    ROOF_OFFSET = 2.5 # Higher avoids window tiling on roofs.
    window_depth = 0.015
    
    windows_collection_name = f"Windows"
    windows_collection = bpy.data.collections[windows_collection_name]
            
    if building_obj.type != 'MESH' or not building_obj.data:
        return None
    
    mesh = building_obj.data
    if len(mesh.vertices) == 0:
        return None

    mesh_name = f"Windows_{building_obj.name}"
    window_mesh = bpy.data.meshes.new(mesh_name)
    window_obj = bpy.data.objects.new(mesh_name, window_mesh)
    windows_collection.objects.link(window_obj)
    
    window_obj.parent = building_obj
    window_obj.matrix_parent_inverse = building_obj.matrix_world.inverted()

    bm = bmesh.new()

    # Find building dimensions IN LOCAL SPACE
    ground_z = (min(v.co.z for v in mesh.vertices) + DOOR_OFFSET)
    top_z = (max(v.co.z for v in mesh.vertices) - ROOF_OFFSET)
    building_height = top_z - ground_z
    
    # GROUP WALLS
    wall_groups = []
    used_polys = set()
    
    for poly in mesh.polygons:
        if poly.index in used_polys:
            continue
        if abs(poly.normal.z) > settings.roof_threshold:
            continue
        
        # Start new group
        group_polys = [poly.index]
        group_normal = poly.normal.copy()
        used_polys.add(poly.index)
        
        # Find similar adjacent polygons
        for other_poly in mesh.polygons:
            if other_poly.index in used_polys:
                continue
            if abs(other_poly.normal.z) > settings.roof_threshold:
                continue
            
            if group_normal.dot(other_poly.normal) > 0.95:
                group_polys.append(other_poly.index)
                used_polys.add(other_poly.index)
        
        wall_groups.append(group_polys)
    
    # Process each wall group
    for wall_poly_indices in wall_groups:
        if random.random() > settings.window_prob:
            continue
        
        # Process each face in the wall group individually
        for poly_idx in wall_poly_indices:
            poly = mesh.polygons[poly_idx]
            
            # Get vertices of this specific face
            face_verts_local = [mesh.vertices[v_idx].co for v_idx in poly.vertices]
            face_verts_world = [building_obj.matrix_world @ v for v in face_verts_local]
            
            # Calculate this face's dimensions
            face_z_values = [v.z for v in face_verts_world]
            face_min_z = min(face_z_values)
            face_max_z = max(face_z_values)
            face_height = face_max_z - face_min_z
            
            # Skip if face is too small
            if face_height < settings.window_height + FLOOR_BOTTOM_MARGIN + FLOOR_TOP_MARGIN:
                continue
            
            # Find horizontal edges of this face
            horizontal_edges = []
            for i in range(len(poly.vertices)):
                v1_idx = poly.vertices[i]
                v2_idx = poly.vertices[(i + 1) % len(poly.vertices)]
                
                v1_local = mesh.vertices[v1_idx].co
                v2_local = mesh.vertices[v2_idx].co
                
                # Check if edge is horizontal (similar Z values)
                if abs(v1_local.z - v2_local.z) < 0.1:
                    v1_world = building_obj.matrix_world @ v1_local
                    v2_world = building_obj.matrix_world @ v2_local
                    horizontal_edges.append((v1_world, v2_world))
            
            if len(horizontal_edges) == 0:
                continue
            
            # Get wall normal IN WORLD SPACE
            wall_normal = building_obj.matrix_world.to_3x3() @ poly.normal
            wall_normal.normalize()
            
            # Find the longest horizontal edge to determine wall direction
            max_edge_length = 0
            wall_direction = Vector((1, 0, 0))
            longest_edge_start = None
            longest_edge_end = None
            
            for v1, v2 in horizontal_edges:
                edge_vec = v2 - v1
                edge_length = edge_vec.length
                if edge_length > max_edge_length:
                    max_edge_length = edge_length
                    wall_direction = edge_vec.normalized()
                    longest_edge_start = v1
                    longest_edge_end = v2
            
            if max_edge_length < settings.window_width:
                continue  # Face too small for windows
            
            # Calculate wall center from the longest edge
            wall_center = (longest_edge_start + longest_edge_end) / 2
            wall_length = max_edge_length
            
            # Calculate how much usable height we have for windows (excluding margins)
            usable_height = face_height - FLOOR_BOTTOM_MARGIN - FLOOR_TOP_MARGIN
            
            # Determine number of floors that would fit in this face
            num_floors_for_face = max(1, int(usable_height / settings.floor_height))
            
            # Now calculate the actual floor height that divides this face evenly
            actual_floor_height = usable_height / num_floors_for_face
            
            # Skip this face if the floor height would be too small for a window
            if actual_floor_height < settings.window_height + 0.5:
                continue
            
            # Calculate how many windows fit horizontally
            available_width = wall_length - (2 * WINDOW_MARGIN)
            num_windows_horizontal = max(1, int(available_width / (settings.window_width + WINDOW_MARGIN)))
            
            # Adjust spacing to distribute evenly
            if num_windows_horizontal > 1:
                total_window_width = num_windows_horizontal * settings.window_width
                total_spacing = available_width - total_window_width
                window_spacing = total_spacing / (num_windows_horizontal + 1)
            else:
                window_spacing = WINDOW_MARGIN
            
            # CREATE WINDOWS FOR EACH FLOOR
            for floor_idx in range(num_floors_for_face):
                # Calculate Z position for this floor using the actual floor height for this face
                floor_base_z = face_min_z + FLOOR_BOTTOM_MARGIN + (floor_idx * actual_floor_height)
                
                # Center window vertically within the floor space
                window_z = floor_base_z + (actual_floor_height - settings.window_height) / 2
                
                # Skip first floor center (where door might be)
                skip_center = (floor_idx == 0)
                
                # Create windows horizontally across the wall
                for win_idx in range(num_windows_horizontal):
                    # Calculate horizontal position along wall direction
                    t = (win_idx + 0.5) / num_windows_horizontal
                    offset_from_start = (t * wall_length) - (wall_length / 2)
                    
                    # Skip center window on ground floor (door area)
                    if skip_center:
                        center_idx = num_windows_horizontal // 2
                        if win_idx == center_idx:
                            continue
                    
                    # Position window along the actual wall edge
                    window_center = wall_center + (wall_direction * offset_from_start)
                    window_center.z = window_z + settings.window_height / 2
                    
                    # Push window out from wall slightly
                    window_center += wall_normal * WALL_OFFSET
                    
                    # Create window quad aligned to wall direction
                    half_width = settings.window_width / 2
                    half_height = settings.window_height / 2
                    
                    # Build vertices using wall_direction
                    v1 = bm.verts.new(window_center + (wall_direction * -half_width) + Vector((0, 0, -half_height)))
                    v2 = bm.verts.new(window_center + (wall_direction * half_width) + Vector((0, 0, -half_height)))
                    v3 = bm.verts.new(window_center + (wall_direction * half_width) + Vector((0, 0, half_height)))
                    v4 = bm.verts.new(window_center + (wall_direction * -half_width) + Vector((0, 0, half_height)))
                    
                    face = bm.faces.new([v1, v2, v3, v4])
                    face.normal_update()
                    
                    # Orient face to match wall
                    if face.normal.dot(wall_normal) < 0:
                        face.normal_flip()
    
    # Finalize mesh
    finalize_mesh_with_normals(bm, window_mesh)
    
    # Apply material
    window_mat_name = "WindowMaterial"
    if window_mat_name not in bpy.data.materials:
        window_mat = bpy.data.materials.new(name=window_mat_name)
        window_mat.use_nodes = True
        nodes = window_mat.node_tree.nodes
        nodes.clear()
        node_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
        node_bsdf.inputs['Base Color'].default_value = (0.3, 0.6, 0.9, 1.0)
        node_bsdf.inputs['Emission'].default_value = (0.3, 0.6, 0.9, 1.0)
        try:
            node_bsdf.inputs['Emission Strength'].default_value = 0.5
        except KeyError:
            pass
        node_output = nodes.new(type='ShaderNodeOutputMaterial')
        window_mat.node_tree.links.new(node_bsdf.outputs['BSDF'], node_output.inputs['Surface'])
    else:
        window_mat = bpy.data.materials[window_mat_name]
    
    if len(window_obj.data.materials) == 0:
        window_obj.data.materials.append(window_mat)
    
    cut_opening_from_walls(building_obj, window_obj, window_depth)
    
    return window_obj

class WINDOWS_AND_DOORS(bpy.types.Operator):
    bl_idname = "object.windows_and_doors"
    bl_label = "Decal windows & doors"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):

        scn = context.scene.pbr_export_settings
        
        # Clear old metadata
        # scn.buildings_metadata.clear()
        global GLOB_BUILDINGS_META_DATA
        GLOB_BUILDINGS_META_DATA.clear()
        
        global GLOB_EXPORT_FOLDER
        global GLOB_TEXTURE_FOLDER
        
        if scn.export_folder:
            GLOB_EXPORT_FOLDER  = bpy.path.abspath(scn.export_folder)
        if scn.texture_folder:
            GLOB_TEXTURE_FOLDER = bpy.path.abspath(scn.texture_folder)
            
        start_time = time.time()
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: windows & doors generation", stream = None, base_time = time.time())
        print_to_stream("="*60 + "\n", stream = None, base_time = time.time())
        
        settings = type("Settings", (), {})()
        settings.export_folder = scn.export_folder
        settings.texture_folder = scn.texture_folder
        
        door_max_width = 5.0
        door_settings = type("DoorSettings", (), {})()
        door_settings.door_prob = scn.door_prob
        door_settings.door_width = scn.door_width
        door_settings.door_max_width = door_max_width
        door_settings.door_height = scn.door_height
        door_settings.door_min_height = 1.0
        door_settings.door_max_height = 10.0
        door_settings.roof_threshold = scn.roof_threshold
        
        window_settings = type("WindowSettings", (), {})()
        window_settings.door_prob = scn.door_prob
        window_settings.door_width = scn.door_width
        window_settings.door_max_width = door_max_width
        window_settings.door_height = scn.door_height
        window_settings.door_min_height = 1.0
        window_settings.door_max_height = 10.0
        window_settings.window_prob = scn.window_prob
        window_settings.window_width = scn.window_width
        window_settings.window_height = scn.window_height
        window_settings.roof_threshold = scn.roof_threshold
        window_settings.floor_height = scn.floor_height
        
        # Create or get collections
        doors_collection_name = "Doors"
        if doors_collection_name in bpy.data.collections:
            doors_collection = bpy.data.collections[doors_collection_name]
        else:
            doors_collection = bpy.data.collections.new(doors_collection_name)
            bpy.context.scene.collection.children.link(doors_collection)
            
        windows_collection_name = "Windows"
        if windows_collection_name in bpy.data.collections:
            windows_collection = bpy.data.collections[windows_collection_name]
        else:
            windows_collection = bpy.data.collections.new(windows_collection_name)
            bpy.context.scene.collection.children.link(windows_collection)
 
        collections = select_top_level_collection_by_name("buildings")
        
        if collections:
            selected = collections
        else:
            print_to_stream("No matching collection found, cannot access first element!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "A buildings scene collection does not exist!")
            return {'CANCELLED'}
            
        if not selected:
            self.report({'ERROR'}, "Select parent buildings object")
            return {'CANCELLED'}
            
        parent = selected
        # FIX all_children = get_all_children(parent)
        all_children = get_all_objects_in_collection(parent)
        meshes = [obj for obj in all_children if obj.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, "No mesh children found")
            return {'CANCELLED'}
        
        print_to_stream(f"Processing {len(meshes)} buildings... please be patient, this might take a while.", stream = None, base_time = time.time())
        start_time = time.time()
        processed_count = 0
        i = 0
        totals = len(meshes)
        start_time = time.time()
        for i, obj in enumerate(meshes, start=1):
            # Create doors and windows
            door_obj = batch_create_doors(obj, door_settings, doors_collection)
            window_obj = batch_create_windows(obj, window_settings, windows_collection)
            console_progress(i, totals, start_time=start_time)
            GLOB_BUILDINGS_META_DATA.append((obj, window_obj, door_obj))
            
            if obj.type != 'MESH':
                continue
            
            # ULTRA-FAST METHOD: Use cached object properties
            world_location = obj.matrix_world.translation
            
            # obj.dimensions gives bounding box dimensions WITH scale applied
            dims = obj.dimensions
            width = dims.x
            depth = dims.y
            height = dims.z
            
            # Only do expensive calculation if dimensions are invalid
            if width < 0.001 or depth < 0.001 or height < 0.001:
                print_to_stream(f"  {obj.name}: Using fallback calculation (dimensions too small)", stream = None, base_time = time.time())
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = obj.evaluated_get(depsgraph)
                if eval_obj.data:
                    matrix = eval_obj.matrix_world
                    bbox_corners = [matrix @ Vector(corner) for corner in eval_obj.bound_box]
                    
                    min_x = min(v.x for v in bbox_corners)
                    max_x = max(v.x for v in bbox_corners)
                    min_y = min(v.y for v in bbox_corners)
                    max_y = max(v.y for v in bbox_corners)
                    min_z = min(v.z for v in bbox_corners)
                    max_z = max(v.z for v in bbox_corners)
                    
                    width = max_x - min_x
                    depth = max_y - min_y
                    height = max_z - min_z
                    world_location = matrix.translation
    
            processed_count += 1
            
            # Progress update every 1000 buildings
            if processed_count % 1000 == 0:
                elapsed = time.time() - start_time
                rate = processed_count / elapsed
                remaining = (len(meshes) - processed_count) / rate

        elapsed = time.time() - start_time
        print_to_stream(f"=== Summary ===\n", stream = None, base_time = time.time())
        print_to_stream(f"Total buildings processed: {processed_count}", stream = None, base_time = time.time())
        print_to_stream(f"Total time: {elapsed:.1f} seconds ({processed_count/elapsed:.1f} buildings/sec)", stream = None, base_time = time.time())
        
        # Export once at the end
        export_city_metadata(GLOB_BUILDINGS_META_DATA, settings)

        self.report({'INFO'}, f"Processed {processed_count} buildings in {elapsed:.1f}s")
        
        cleanup_blender_memory()

        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.", stream = None, base_time = time.time())
        print_to_stream("="* 60+ "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 
        
        return {'FINISHED'}

def is_folder_empty(path):
    return os.path.exists(path) and os.path.isdir(path) and not os.listdir(path)

def select_top_level_collection_by_name(part_name):
    """
    Selects only the first collection containing 'part_name',
    selects only its objects (ignoring children), and returns the collection.
    """
    # Deselect everything first
    bpy.ops.object.select_all(action='DESELECT')
    i = 0
    for coll in bpy.data.collections:
        if part_name.lower() in coll.name.lower() and coll.objects:
            # Select only objects in this collection (ignore children)
            for obj in coll.objects:
                if i < 1:
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active = obj  # last object becomes active
                    print_to_stream(f"Selected parent collection: {coll.name}", stream = None, base_time = time.time())
                    i = 1
                    return coll
                    
def extract_openings_data(building_obj, window_obj, door_obj):
    """Extract window and door data from objects"""
    building_data = {
        "name": building_obj.name,
        "windows": [],
        "doors": []
    }

    # Store windows
    if window_obj and window_obj.data:
        mesh = window_obj.data
        for poly in mesh.polygons:
            center = sum((window_obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
            building_data["windows"].append({
                "face_index": poly.index,
                "center": round_vec([center.x, center.y, center.z], 2),
                "normal": round_vec([poly.normal.x, poly.normal.y, poly.normal.z], 3) 
            })
    
    # Store doors
    if door_obj and door_obj.data:
        mesh = door_obj.data
        for poly in mesh.polygons:
            center = sum((door_obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
            building_data["doors"].append({
                "face_index": poly.index,
                "center": round_vec([center.x, center.y, center.z], 2),
                "normal": round_vec([poly.normal.x, poly.normal.y, poly.normal.z], 3) 
            })
    
    return building_data

def extract_window_data(window_obj):
    """Optimized window data extraction"""
    if not window_obj or not window_obj.data:
        return []
    
    windows = []
    mesh = window_obj.data
    matrix = window_obj.matrix_world
    
    # Pre-calculate all centers at once
    for poly in mesh.polygons:
        center = matrix @ poly.center
        windows.append({
            "face_index": poly.index,
            "center": [blender_to_unity_coords([round(center.x, 2), round(center.y, 2), round(center.z, 2)])],
            "normal": [blender_to_unity_coords([round(poly.normal.x, 3), round(poly.normal.y, 3), round(poly.normal.z, 3)])]
        })
    
    return windows

def extract_door_data(door_obj):
    """Optimized door data extraction"""
    if not door_obj or not door_obj.data:
        return []
    
    doors = []
    mesh = door_obj.data
    matrix = door_obj.matrix_world
    
    # Pre-calculate all centers at once
    for poly in mesh.polygons:
        center = matrix @ poly.center
        doors.append({
            "face_index": poly.index,
            "center": [blender_to_unity_coords([round(center.x, 2), round(center.y, 2), round(center.z, 2)])],
            "normal": [blender_to_unity_coords([round(poly.normal.x, 3), round(poly.normal.y, 3), round(poly.normal.z, 3)])]
        })
    
    return doors
    
def collect_existing_metadata_from_scene():
    """Fallback: Scan scene for existing door/window objects"""
    metadata = []
    start_time = time.time()
    # Find Windows and Doors collections
    windows_coll = bpy.data.collections.get("Windows")
    doors_coll = bpy.data.collections.get("Doors")
    
    if not windows_coll and not doors_coll:
        print_to_stream("No Windows/Doors collections found in scene!")
        return []
    
    # Group by building
    buildings = {}
    
    if windows_coll:
        for obj in windows_coll.objects:
            building_name = obj.name.replace("_windows", "")
            if building_name not in buildings:
                buildings[building_name] = {"name": building_name, "windows": [], "doors": []}
            
            mesh = obj.data
            for poly in mesh.polygons:
                center = sum((obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
                buildings[building_name]["windows"].append({
                    "face_index": poly.index,
                    "center": round_vec(blender_to_unity_coords([center.x, center.y, center.z]), 3),
                    "normal": round_vec(blender_to_unity_coords([poly.normal.x, poly.normal.y, poly.normal.z]), 3)
                })
    
    if doors_coll:
        for obj in doors_coll.objects:
            building_name = obj.name.replace("_doors", "")
            if building_name not in buildings:
                buildings[building_name] = {"name": building_name, "windows": [], "doors": []}
            
            mesh = obj.data
            for poly in mesh.polygons:
                center = sum((obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
                buildings[building_name]["doors"].append({
                    "face_index": poly.index,
                    "center": round_vec(blender_to_unity_coords([center.x, center.y, center.z]), 3),
                    "normal": round_vec(blender_to_unity_coords([poly.normal.x, poly.normal.y, poly.normal.z]), 3)
                })
    
    print_to_stream(f"Collected {len(buildings)} buildings from scene\n", stream = None, base_time = time.time())
    print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 
    return list(buildings.values())

def export_city_metadata(buildings_data, settings):
    """Export all buildings, windows, and doors to one JSON file"""
    
    global GLOB_EXPORT_FOLDER 
    global GLOB_TEXTURE_FOLDER 
    if settings.export_folder:
        GLOB_EXPORT_FOLDER  = bpy.path.abspath(settings.export_folder)
    if settings.texture_folder:
        GLOB_TEXTURE_FOLDER = bpy.path.abspath(settings.texture_folder)
            
    export_folder = bpy.path.abspath(settings.export_folder)
    start_time = time.time()
    # Detect data format
    if buildings_data and isinstance(buildings_data[0], dict):
        print_to_stream("Using pre-formatted metadata from scene", stream = None, base_time = time.time())
        formatted_buildings = buildings_data
    elif buildings_data and isinstance(buildings_data[0], tuple):
        print_to_stream("Processing raw object tuples", stream = None, base_time = time.time())
        formatted_buildings = []
        
        for building_obj, window_obj, door_obj in buildings_data:
            building_data = {
                "name": building_obj.name,
                "windows": [],
                "doors": []
            }
            
            # Store windows
            if window_obj and window_obj.data:
                mesh = window_obj.data
                for poly in mesh.polygons:
                    center = sum((window_obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
                    building_data["windows"].append({
                        "face_index": poly.index,
                        "center": round_vec(blender_to_unity_coords([center.x, center.y, center.z]), 3),
                        "normal": round_vec(blender_to_unity_coords([poly.normal.x, poly.normal.y, poly.normal.z]), 3)
                    })
            
            # Store doors
            if door_obj and door_obj.data:
                mesh = door_obj.data
                for poly in mesh.polygons:
                    center = sum((door_obj.matrix_world @ mesh.vertices[v].co for v in poly.vertices), Vector()) / len(poly.vertices)
                    building_data["doors"].append({
                        "face_index": poly.index,
                        "center": round_vec(blender_to_unity_coords([center.x, center.y, center.z]), 3),
                        "normal": round_vec(blender_to_unity_coords([poly.normal.x, poly.normal.y, poly.normal.z]), 3)
                    })
            
            formatted_buildings.append(building_data)
    else:
        print_to_stream("WARNING: Unknown metadata format!", stream = None, base_time = time.time())
        formatted_buildings = []
    
    # Export
    metadata = {
        "city": "Generated City",
        "export_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_buildings": len(formatted_buildings),
        "buildings": formatted_buildings
    }
    
    building_json_path = os.path.join(export_folder, "Metadata.json")
    os.makedirs(export_folder, exist_ok=True)
    
    with open(building_json_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f)
    
    print_to_stream(f"Exported {len(formatted_buildings)} buildings to Metadata.json\n", stream = None, base_time = time.time())
    print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 

def export_material_texture_list(export_folder):
    """Create a simple text file listing which textures belong to which material"""
    mapping_file = os.path.join(export_folder, "material_textures.txt")
    
    with open(mapping_file, 'w') as f:
        f.write("# Material -> Texture mappings\n")
        f.write("# Format: MaterialName | TextureType | FileName\n\n")
        
        for mat in bpy.data.materials:
            if not mat.use_nodes or not mat.name.startswith("PBR_"):
                continue
            
            f.write(f"\n[{mat.name}]\n")
            
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image:
                    img_name = node.image.name
                    name_lower = img_name.lower()
                    
                    tex_type = "Unknown"
                    if 'albedo' in name_lower or 'base_color' in name_lower or 'basecolor' in name_lower:
                        tex_type = "Albedo"
                    elif 'normal' in name_lower:
                        tex_type = "Normal"
                    elif 'metallic' in name_lower:
                        tex_type = "Metallic"
                    elif 'roughness' in name_lower:
                        tex_type = "Roughness"
                    elif 'ao' in name_lower or 'occlusion' in name_lower:
                        tex_type = "AO"
                    elif 'height' in name_lower:
                        tex_type = "Height"
                    elif 'maskmap' in name_lower or 'mask' in name_lower:
                        tex_type = "MaskMap"
                    
                    f.write(f"{tex_type} = {img_name}\n")
    
    print_to_stream(f"Material mapping exported to: {mapping_file}", stream = None, base_time = time.time())

def solidify_vertical_walls(obj, thickness=0.1, vertical_threshold=0.9):
    
    if obj.type != 'MESH':
        return
        
    vg = obj.vertex_groups.new(name="WallsOnly")
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)

    for face in bm.faces:
        normal = face.normal.normalized()
        if abs(normal.z) < (1 - vertical_threshold):
            for vert in face.verts:
                vg.add([vert.index], 1.0, 'ADD')

    bm.free()

    solidify = obj.modifiers.new(name="Solidify_Walls", type='SOLIDIFY')
    solidify.thickness = thickness
    solidify.vertex_group = vg.name
    solidify.use_even_offset = True
    return {'FINISHED'}

def cleanup_blender_memory():
    
    """
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    for mat in list(bpy.data.materials):
        if mat.users == 0:
            bpy.data.materials.remove(mat)

    for img in list(bpy.data.images):
        if img.users == 0 and not img.packed_file:
            bpy.data.images.remove(img)

    for tex in list(bpy.data.textures):
        if tex.users == 0:
            bpy.data.textures.remove(tex)

    for curve in list(bpy.data.curves):
        if curve.users == 0:
            bpy.data.curves.remove(curve)

    # Optional: refresh the viewport cleanly
    try:
        bpy.context.view_layer.update()
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except:
        pass  # this can fail if no window context (like background mode)

    # Force Python GC and Blender depsgraph updates
    # gc.collect()
    """
    
    print_to_stream("Blender memory cleaned up.")

def create_textures(texture_path,texture_name,obj_tex,export_folder,tex_width,tex_height):
    
    if os.path.exists(texture_path) and os.path.isdir(texture_path): 
       
       start_time = time.time()
       if is_folder_empty(texture_path):
           print_to_stream(texture_path + "\ folder is empty! please add textures first!", stream = None, base_time = time.time())
           messagebox_showerror("Error", texture_path + "\ folder is empty! please add textures first!")
           return {'CANCELLED'}
        
       collections = select_top_level_collection_by_name(texture_name)
        
       if collections:
           selected = collections
       else:
           print_to_stream("No matching collection found, cannot access first element!", stream = None, base_time = time.time())
           messagebox_showerror("Error", "A " + texture_name + " scene collection does not exist!")
           return {'CANCELLED'}
       if not selected:
           print_to_stream("Select " + texture_name + " parent!", stream = None, base_time = time.time())
           messagebox_showerror("Error", "Select " + texture_name + " parent!")
           return {'CANCELLED'}
       parent = selected
       all_children = get_all_objects_in_collection(parent)

       # Auto-convert any CURVE objects (common for OSM road/path imports) into MESH
       # so they aren't silently skipped by the MESH-only filter below.
       curve_objs = [obj for obj in all_children if obj.type == 'CURVE']
       if curve_objs:
           print_to_stream(f"Converting {len(curve_objs)} curve object(s) to mesh in {texture_name}...", stream = None, base_time = time.time())
           bpy.ops.object.select_all(action='DESELECT')
           for obj in curve_objs:
               obj.select_set(True)
               bpy.context.view_layer.objects.active = obj
           try:
               bpy.ops.object.convert(target='MESH')
           except Exception as e:
               print_to_stream(f"Curve to mesh conversion failed: {e}", stream = None, base_time = time.time())
           all_children = get_all_objects_in_collection(parent)  # re-fetch after conversion

       meshes = [obj for obj in all_children if obj.type == 'MESH']
       if not meshes:
           print_to_stream("No MESH children found!, textures might not have been applied everywhere!", stream = None, base_time = time.time())
       # Apply textures per mesh
       i = 0
       totals = len(meshes)
       start_time = time.time()
       print_to_stream("Creating materials/textures... please wait.", stream = None, base_time = time.time())
       for i, obj in enumerate(meshes, start=1):
           obj_mat = get_or_create_material_auto(obj_tex, texture_path, export_folder, random_select=True)
           console_progress(i, totals, start_time=start_time)
           mesh = obj.data
           if len(mesh.polygons) == 0:
               print_to_stream(f"Skipping {obj.name} - no polygons", stream = None, base_time = time.time())
               continue
           if not mesh.uv_layers:
               uv_layer = mesh.uv_layers.new(name="UVMap")
           else:
               uv_layer = mesh.uv_layers.active
           if not uv_layer:
               uv_layer = mesh.uv_layers[0]
               
           mesh.materials.clear()
           mesh.materials.append(obj_mat)
           
           try:
               mesh.normal_update()
               mesh.calc_normals_split()
           except: 
               pass
           
           for poly in mesh.polygons:
               generate_face_uvs(mesh, poly, uv_layer, tex_width, tex_height)
           mesh.update()
        
           obj["StochasticSeed"] = random.random()
        
           if obj.data.materials:
               obj["MaterialName"] = obj.data.materials[0].name if obj.data.materials[0] else "Unknown"
           else:
               obj["MaterialName"] = "Unknown"
               
       print_to_stream("Applied " + str(len(meshes)) + " textures to @ " + texture_name + "!\n", stream = None, base_time = time.time())
       print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 
       cleanup_blender_memory()
       return {'FINISHED'}
        
    else:
        print_to_stream("/" + texture_name + "/ texture folder does not exist!", stream = None, base_time = time.time())
        messagebox_showerror("Error", "/" + texture_name + "/ texture folder does not exist!")
        return {'CANCELLED'} 

    return {'FINISHED'}

def clean_evaluated_mesh(obj, depsgraph):
    try:
        eval_obj = obj.evaluated_get(depsgraph)
        temp_mesh = eval_obj.to_mesh()
        
        if not temp_mesh or len(temp_mesh.polygons) == 0:
            eval_obj.to_mesh_clear()
            return

        # Create a real copy of the mesh (so we can assign it safely)
        clean_mesh = bpy.data.meshes.new(name=f"{obj.name}_clean")
        clean_mesh.from_mesh(temp_mesh)

        eval_obj.to_mesh_clear()

        # Assign temporary mesh
        obj.data = clean_mesh

        # Enter edit mode for cleanup operations
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.0001)
        bpy.ops.mesh.delete_loose()
        bpy.ops.mesh.normals_make_consistent()
        bpy.ops.object.mode_set(mode='OBJECT')

        # Optional: remove temporary mesh if you want to save memory
        # (Keep it if you're exporting right after)
        # bpy.data.meshes.remove(clean_mesh)

    except Exception as e:
        return {'FINISHED'}

def console_progress(current, total, bar_length=40, start_time=None):
    percent = float(current) / total
    filled_length = int(percent * bar_length)
    hashes = '#' * filled_length
    spaces = ' ' * (bar_length - filled_length)
    print(f"\rProgress: [{hashes}{spaces}] {int(percent*100)}%", end='', flush=True)

    if current == total:
        print()  # move to next line when finished
        if start_time is not None:
            elapsed = time.time() - start_time
            print_to_stream(f"Processing took: {elapsed:.2f} seconds.\n", stream = None, base_time = time.time())

class EXPORT_DATA(bpy.types.Operator):
    bl_idname = "object.export_data"
    bl_label = "Export data"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        
        scn = context.scene.pbr_export_settings
        texture_folder = bpy.path.abspath(scn.texture_folder)
        export_folder = bpy.path.abspath(scn.export_folder)
        tex_width = scn.tex_width
        tex_height = scn.tex_height
        roof_threshold = scn.roof_threshold

        global GLOB_BUILDINGS_META_DATA

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
        
        start_time = time.time()

        water_collection = bpy.data.collections.get("_WaterBooleans")
        # delete the water copies, if they exists.
        if water_collection:
            for obj in list(water_collection.objects): 
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections.remove(water_collection)
                
        objects_to_select = [obj for obj in bpy.context.scene.objects if obj.type in {'MESH', 'EMPTY'}]
        for obj in objects_to_select:
            obj.select_set(True)
        
        texture_path_roofs = os.path.join(texture_folder, "roofs")
        texture_path_buildings = os.path.join(texture_folder, "buildings")
        
        if os.path.exists(texture_path_roofs) and os.path.isdir(texture_path_roofs):
            roof_folder = texture_path_roofs
        else:
            print_to_stream("/roofs/ texture folder does not exist!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "/roofs/ texture folder does not exist!")
            return {'CANCELLED'}
            
        if os.path.exists(texture_path_buildings) and os.path.isdir(texture_path_buildings):
            texture_folder = texture_path_buildings
        else:
            print_to_stream("/buildings/ texture folder does not exist!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "/buildings/ texture folder does not exist!")
            return {'CANCELLED'}
        
        if os.name == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)

        export_settings = type("ExportSettings", (), {})()
        export_settings.export_folder = scn.export_folder
        export_settings.texture_folder = scn.texture_folder
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: preparing everything for export, please wait.", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        # Reload all images with absolute paths
        print_to_stream("Reloading textures...", stream = None, base_time = time.time())
        for img in bpy.data.images:
            if img.source == 'FILE' and img.filepath:
                try:
                    abs_path = bpy.path.abspath(img.filepath)
                    if os.path.exists(abs_path):
                        img.filepath = abs_path
                        img.reload()
                        img.pack()
                    else:
                        print_to_stream(f"Missing: {img.name} at {abs_path}", stream = None, base_time = time.time())
                except Exception as e:
                    print_to_stream(f"Failed to reload: {img.name} - {e}", stream = None, base_time = time.time())
        
        # Ensure all materials have proper nodes
        print_to_stream("Fixing materials for export...", stream = None, base_time = time.time())
        fixed_count = 0
        for mat in bpy.data.materials:
            if not mat.use_nodes:
                print_to_stream(f"Material '{mat.name}' has no nodes - enabling...", stream = None, base_time = time.time())
                mat.use_nodes = True
                fixed_count += 1
            
            # Ensure BSDF exists
            if mat.use_nodes:
                nodes = mat.node_tree.nodes
                if not nodes.get("Principled BSDF"):
                    print_to_stream(f"Adding BSDF to {mat.name}", stream = None, base_time = time.time())
                    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
                    output = nodes.get("Material Output")
                    if not output:
                        output = nodes.new('ShaderNodeOutputMaterial')
                        output.location = (300, 0)
                    bsdf.location = (0, 0)
                    mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])
        
        print_to_stream(f"Fixed {fixed_count} materials without nodes", stream = None, base_time = time.time())
        
        # Pack images
        print_to_stream("Packing images...", stream = None, base_time = time.time())
        bpy.ops.file.pack_all()

        # Get all objects
        all_objects = [obj for obj in bpy.data.objects if obj.type in {'EMPTY', 'MESH'}]
    
        if not all_objects:
            self.report({'ERROR'}, "No objects found in scene")
            return {'CANCELLED'}
    
        if len(GLOB_BUILDINGS_META_DATA) == 0:
            GLOB_BUILDINGS_META_DATA = collect_existing_metadata_from_scene()
            
        # Export metadata
        export_city_metadata(GLOB_BUILDINGS_META_DATA, export_settings)
    
        print_to_stream(f"Preparing meshes for export. Please wait... this takes a while.", stream = None, base_time = time.time())
        # Ensure OBJECT mode
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
    
        # Select all
        bpy.ops.object.select_all(action='DESELECT')
        view_layer = bpy.context.view_layer

        for obj in all_objects:
            if obj.name in view_layer.objects:
                obj.select_set(True)
                for c in obj.children:
                    if c.get("PreviewMarker") and c.name in view_layer.objects:
                       c.select_set(True)
    
        # Filter meshes properly
        objects_to_export = [obj for obj in all_objects if obj.type == 'MESH' and prepare_mesh_fast(obj)]
    
        # Prepare export
        export_path = os.path.join(export_folder, "Models", "buildings.fbx")
        os.makedirs(os.path.dirname(export_path), exist_ok=True)

        # Mesh cleanup for Unity.
        print_to_stream(f"Mesh cleanup started. Please wait...", stream = None, base_time = time.time())
        depsgraph = bpy.context.evaluated_depsgraph_get()
        
        totals = len(objects_to_export)
        start_time = time.time()
        for i, obj in enumerate(objects_to_export, start=1):
            
            if obj.type == 'MESH':
                clean_evaluated_mesh(obj, depsgraph)
                console_progress(i, totals, start_time=start_time)

        print_to_stream("Mesh cleanup finished. Please wait for the next step to finish: exporting the FBX...", stream = None, base_time = time.time())
        
        bpy.ops.object.select_all(action='DESELECT')
        view_layer = bpy.context.view_layer

        for obj in objects_to_export:
            if obj.name in view_layer.objects:
                obj.select_set(True)
                for c in obj.children:
                    if c.get("PreviewMarker") and c.name in view_layer.objects:
                       c.select_set(True)
        
        print_to_stream(f"Exporting {len(objects_to_export)} objects to FBX...", stream = None, base_time = time.time())
        
        # Now export!
        bpy.ops.export_scene.fbx(
            filepath=export_path,
            global_scale=1.0,
            use_selection=True,
            object_types={'EMPTY', 'MESH'},
            use_mesh_modifiers=True,
            use_mesh_edges=False,
            # use_tspace=False,
            use_custom_props=True,
            add_leaf_bones=False,
            bake_space_transform=False,
            path_mode='COPY',
            embed_textures=True,
            axis_forward='-Z',
            axis_up='Y',
            apply_unit_scale=True,
            # apply_modifiers=True,
            mesh_smooth_type='FACE',
            apply_scale_options='FBX_SCALE_ALL',
            bake_anim=False
        )

        print_to_stream("FBX export complete, continuing... please wait.", stream = None, base_time = time.time())

        # Export material mapping for Unity
        export_material_texture_list(export_folder)

        # Manually copy textures as backup
        print_to_stream("\nCopying textures to export folder...", stream = None, base_time = time.time())
        textures_copied = 0
        texture_export_path = os.path.join(export_folder, "Textures")
        os.makedirs(texture_export_path, exist_ok=True)
        
        for folder in [texture_folder, roof_folder]:
            if os.path.exists(folder):
                for file in os.listdir(folder):
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.tga')):
                        src = os.path.join(folder, file)
                        dst = os.path.join(texture_export_path, file)
                        try:
                            shutil.copy2(src, dst)
                            textures_copied += 1
                        except Exception as e:
                            print_to_stream(f"Failed to copy {file}: {e}", stream = None, base_time = time.time())
        
        print_to_stream(f"Copied {textures_copied} texture files", stream = None, base_time = time.time())

        # Export stochastic seeds
        seed_file_path = os.path.join(export_folder, "stochastic_seeds.txt")
        with open(seed_file_path, 'w') as f:
            f.write("# Stochastic Seeds for Unity\n")
            f.write("# Format: ObjectName | Seed | MaterialName\n\n")
            for obj in objects_to_export:
                seed = obj.get("StochasticSeed", 0.5)
                mat_name = obj.get("MaterialName", "Unknown")
                f.write(f"{obj.name} | {seed:.6f} | {mat_name}\n")
        
        # Unity instructions
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream("UNITY IMPORT INSTRUCTIONS:\n", stream = None, base_time = time.time())
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream("1. Copy '/World Builder/Export/' folder to Unity Assets\n", stream = None, base_time = time.time())
        print_to_stream("2. Import the /World Builder/Shaders/StochasticTiling_URP.shader into Unity Shaders folder\n", stream = None, base_time = time.time())
        print_to_stream("2.1 Then import /World Builder/Scripts/ApplyStochasticShader.cs script into the scripts folder\n", stream = None, base_time = time.time())
        print_to_stream("3. Select FBX -> Inspector -> Materials:\n", stream = None, base_time = time.time())
        print_to_stream("   - 'Extract Materials'\n", stream = None, base_time = time.time())
        print_to_stream("   - 'Use External Materials (Legacy)'\n", stream = None, base_time = time.time())
        print_to_stream("4. Model tab:\n", stream = None, base_time = time.time())
        print_to_stream("   - Normals: 'Calculate'\n", stream = None, base_time = time.time())
        print_to_stream("   - Tangents: 'Calculate Mikktspace'\n", stream = None, base_time = time.time())
        print_to_stream("5. Drag FBX into Hierarchy. Then drag and drop ApplyStochasticShader.cs script to inspector\n", stream = None, base_time = time.time())
        print_to_stream("5.1. Then drag shader file into shader slot\n", stream = None, base_time = time.time())
        print_to_stream("6. Right click on script name: Run 'Apply Stochastic Materials' from context menu\n", stream = None, base_time = time.time())
        print_to_stream("   - The door/window preview objects have custom props: Type, ParentBuilding, DoorID/WindowID, Width, Height\n", stream = None, base_time = time.time())
        print_to_stream("   - Unity can read these from the imported model (ModelImporter) or via serialized metadata\n", stream = None, base_time = time.time())
        print_to_stream("   - Use the preview meshes as colliders / spawn interior prefabs at those positions, then remove previews if not needed.\n", stream = None, base_time = time.time())
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream(f"Export complete!\n", stream = None, base_time = time.time())
        print_to_stream(f"{len(objects_to_export)} buildings exported\n", stream = None, base_time = time.time())
        print_to_stream(f"{textures_copied} textures copied\n", stream = None, base_time = time.time())
        print_to_stream(f"Files saved to: {export_folder}\n", stream = None, base_time = time.time())
        print_to_stream("="*60)
        print_to_stream(f"FINISHED, EVERYTHING IS COMPLETE! (You can close your work now, please note: if you save the .blend file, then upon reload, it uses scene collection as data!)\n", stream = None, base_time = time.time())
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream("Log file saved to: " + export_folder + "console_log.txt\n", stream = None, base_time = time.time())
     
        cleanup_blender_memory()

        global GLOB_START_TIME
        
        if GLOB_START_TIME is None:
            print_to_stream("="*60, stream = None, base_time = time.time())
            print_to_stream("Global timer was not started! cannot calculate the time it took, exiting to finish.... script is now done and finalized.\n", stream = None, base_time=time.time())
            print_to_stream("="*60, stream = None, base_time = time.time())
            return {'FINISHED'}

        elapsed = time.time() - GLOB_START_TIME
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream(f"Total elapsed time (from starting to finishing your work): {minutes} min {seconds} sec\n", stream = None, base_time=time.time())
        print_to_stream("="*60, stream = None, base_time = time.time())
        print_to_stream(f"Export processing took: {time.time() - start_time:.2f} seconds") 
        
        return {'FINISHED'}
                    
# ===== Main Operator =====
class OBJECT_OT_run_pbr_export(bpy.types.Operator):
    bl_idname = "object.run_pbr_export"
    bl_label = "Run wall and roof texture generation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.object.mode_set(mode='OBJECT')
        scn = context.scene.pbr_export_settings
        texture_folder = bpy.path.abspath(scn.texture_folder)
        export_folder = bpy.path.abspath(scn.export_folder)
        thickness = scn.wall_thickness
        tex_width = scn.tex_width
        tex_height = scn.tex_height
        roof_threshold = scn.roof_threshold
        wall_tex = ""
        roof_tex = ""

        texture_path_roofs = os.path.join(texture_folder, "roofs")
        texture_path_buildings = os.path.join(texture_folder, "buildings")

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
            
        global GLOB_START_TIME
        GLOB_START_TIME = time.time()
        start_time = time.time()
        
        if os.name == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
            
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("STARTING WORLD BUILDER.\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: material initialization\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
            
        if os.path.exists(texture_path_roofs) and os.path.isdir(texture_path_roofs):
            roof_folder = texture_path_roofs
        else:
            print_to_stream("/roofs/ texture folder does not exist!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "/roofs/ texture folder does not exist!")
            return {'CANCELLED'}
            
        if os.path.exists(texture_path_buildings) and os.path.isdir(texture_path_buildings):
            texture_folder = texture_path_buildings
        else:
            print_to_stream("/buildings/ texture folder does not exist!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "/buildings/ texture folder does not exist!")
            return {'CANCELLED'}

        if is_folder_empty(texture_folder):
            print_to_stream(texture_folder + "/ folder is empty! please add textures first!", stream = None, base_time = time.time())
            messagebox_showerror("Error", texture_folder + "/ folder is empty! please add textures first!")
            return {'CANCELLED'}
 
        if is_folder_empty(roof_folder):
            print_to_stream(roof_folder + "/ folder is empty! please add textures first!", stream = None, base_time = time.time())
            messagebox_showerror("Error", roof_folder + "/ folder is empty! please add textures first!")
            return {'CANCELLED'}

        collections = select_top_level_collection_by_name("buildings")
        if collections:
            selected = collections
        else:
            print_to_stream("No matching collection found, cannot access first element!", stream = None, base_time = time.time())
            messagebox_showerror("Error", "A buildings scene collection does not exist!")
            return {'CANCELLED'}
            
        if not selected:
            self.report({'ERROR'}, "Select parent buildings object")
            return {'CANCELLED'}
            
        parent = selected
        # all_children = get_all_children(parent) 
        all_children = get_all_objects_in_collection(parent)
        meshes = [obj for obj in all_children if obj.type == 'MESH']
        if not meshes:
            self.report({'ERROR'}, "No mesh children found")
            return {'CANCELLED'}
        i = 0
        totals = len(meshes)
        start_time = time.time()

        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: material/texture generation\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        
        # Apply materials per mesh (random wall + roof)
        for i, obj in enumerate(meshes, start=1):
            wall_mat = get_or_create_material_auto(wall_tex, texture_folder, export_folder, random_select=True)
            roof_mat = get_or_create_material_auto(roof_tex, roof_folder, export_folder, random_select=True)
            console_progress(i, totals, start_time=start_time)
            mesh = obj.data
            
            # Ensure mesh has valid data
            if len(mesh.polygons) == 0:
                print_to_stream(f"Skipping {obj.name} - no polygons")
                continue
            
            # Create UV layer properly
            if not mesh.uv_layers:
                uv_layer = mesh.uv_layers.new(name="UVMap")
            else:
                uv_layer = mesh.uv_layers.active
            
            # Verify UV layer is active
            if not uv_layer:
                uv_layer = mesh.uv_layers[0]
                
            mesh.materials.clear()
            mesh.materials.append(wall_mat)
            mesh.materials.append(roof_mat)
           
            if scn.solidify:
                solidify_vertical_walls(obj, thickness, 0.9)

            for poly in mesh.polygons:
                is_roof = abs(poly.normal.z) > roof_threshold
                poly.material_index = 1 if is_roof else 0
                generate_face_uvs(mesh, poly, uv_layer, tex_width, tex_height)

            mesh.update()
            obj["StochasticSeed"] = random.random()
            
            if obj.data.materials:
                obj["MaterialName"] = obj.data.materials[0].name if obj.data.materials[0] else "Unknown"
            else:
                obj["MaterialName"] = "Unknown"
        
        self.report({'INFO'}, f"Applied materials to {len(meshes)} buildings")
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 
        
        cleanup_blender_memory()
        return {'FINISHED'}

class WATERWAYS(bpy.types.Operator):
    
    bl_idname = "object.waterways"
    bl_label = "Texturize waterways"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        
        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
        start_time = time.time()
        scn = context.scene.pbr_export_settings
        settings = type("Settings", (), {})()
        settings.water_folder = scn.texture_folder
        export_folder = bpy.path.abspath(scn.export_folder)
        texture_folder = bpy.path.abspath(scn.texture_folder)
        texture_path_water = os.path.join(settings.water_folder, "water")
        tex_width = scn.tex_width
        tex_height = scn.tex_height
        water_tex = ""
        
        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
        
        if texture_path_water:
            print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
            print_to_stream("Starting subroutine: waterways texturing\n", stream = None, base_time = time.time())
            print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
            create_textures(texture_path_water,"water",water_tex,export_folder,tex_width,tex_height)
        
            print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
            print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
            print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.\n", stream = None, base_time = time.time())
            print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
            print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds") 
        
        else:
            print_to_stream("WARNING: Skipping texturing waterways, as no texture folder has been found.\n", stream = None, base_time = time.time())

        # Carve water.
        bpy.ops.object.water_carver()
        
        return {'FINISHED'}
  
class GREENERY(bpy.types.Operator):
    
    bl_idname = "object.greenery"
    bl_label = "Texturize greenery"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        
        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
            
        start_time = time.time()
        scn = context.scene.pbr_export_settings
        settings = type("Settings", (), {})()
        settings.vegetation_folder = scn.texture_folder
        settings.forest_folder = scn.texture_folder
        export_folder = bpy.path.abspath(scn.export_folder)
        texture_folder = bpy.path.abspath(scn.texture_folder)
        texture_path_vegetation = os.path.join(settings.vegetation_folder, "vegetation")
        texture_path_forest = os.path.join(settings.forest_folder, "forest")
        tex_width = scn.tex_width
        tex_height = scn.tex_height
        vegetation_tex = ""
        forest_tex = ""

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
            
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: greenery generation\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        create_textures(texture_path_vegetation,"vegetation",vegetation_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_forest,"forest",forest_tex,export_folder,tex_width,tex_height)
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds")  
        
        return {'FINISHED'}

class TREES(bpy.types.Operator):

    bl_idname = "object.place_trees"
    bl_label = "Place trees"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)

        start_time = time.time()
        scn = context.scene.pbr_export_settings

        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: tree placement\n", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())

        total_placed = 0
        total_placed += scatter_trees_in_collection(
            "forest",
            scn.tree_density,
            scn.tree_min_scale,
            scn.tree_max_scale,
            scn.tree_min_spacing,
            scn.tree_seed,
            terrain_obj_name=scn.tree_terrain_obj_name,
            tree_source_objects=scn.tree_source_objects,
            auto_normalize_z=scn.tree_auto_normalize_z,
            z_offset=scn.tree_z_offset
        )

        if scn.tree_also_vegetation:
            total_placed += scatter_trees_in_collection(
                "vegetation",
                scn.tree_density * 0.3,
                scn.tree_min_scale,
                scn.tree_max_scale,
                scn.tree_min_spacing,
                scn.tree_seed + 1,
                terrain_obj_name=scn.tree_terrain_obj_name,
                tree_source_objects=scn.tree_source_objects,
                auto_normalize_z=scn.tree_auto_normalize_z,
                z_offset=scn.tree_z_offset
            )

        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Subroutine completed. Placed {total_placed} trees total.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds")

        cleanup_blender_memory()

        return {'FINISHED'}

class ROADS(bpy.types.Operator):
    
    bl_idname = "object.roads"
    bl_label = "Texturize roads"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        
        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
        
        start_time = time.time()
        
        scn = context.scene.pbr_export_settings
        settings = type("Settings", (), {})()
        export_folder = bpy.path.abspath(scn.export_folder)
        texture_folder = bpy.path.abspath(scn.texture_folder)
        tex_width = scn.tex_width
        tex_height = scn.tex_height

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
        
        texture_path_paths_cycleway = os.path.join(scn.texture_folder, "paths_cycleway")
        texture_path_paths_footway = os.path.join(scn.texture_folder, "paths_footway")
        texture_path_paths_steps = os.path.join(scn.texture_folder, "paths_steps")
        texture_path_roads_pedestrian = os.path.join(scn.texture_folder, "roads_pedestrian")
        texture_path_roads_primary = os.path.join(scn.texture_folder, "roads_primary")
        texture_path_roads_residential = os.path.join(scn.texture_folder, "roads_residential")
        texture_path_roads_secondary = os.path.join(scn.texture_folder, "roads_secondary")
        texture_path_roads_service = os.path.join(scn.texture_folder, "roads_service")
        texture_path_roads_tertiary = os.path.join(scn.texture_folder, "roads_tertiary")
        texture_path_roads_track = os.path.join(scn.texture_folder, "roads_track")
        texture_path_roads_unclasified = os.path.join(scn.texture_folder, "roads_unclasified")
        texture_path_areas_pedestrian = os.path.join(scn.texture_folder, "areas_pedestrian")

        paths_cycleway_tex = ""
        paths_footway_tex = ""
        paths_steps_tex = ""
        roads_pedestrian_tex = ""
        roads_primary_tex = ""
        roads_residential_tex = ""
        roads_secondary_tex = ""
        roads_service_tex = ""
        roads_tertiary_tex = ""
        roads_track_tex = ""
        roads_unclasified_tex = ""
        areas_pedestrian_tex = ""
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: roads generation", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        
        create_textures(texture_path_paths_cycleway,"paths_cycleway",paths_cycleway_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_paths_footway,"paths_footway",paths_footway_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_paths_steps,"paths_steps",paths_steps_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_pedestrian,"roads_pedestrian",roads_pedestrian_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_primary,"roads_primary",roads_primary_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_residential,"roads_residential",roads_residential_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_secondary,"roads_secondary",roads_secondary_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_service,"roads_service",roads_service_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_tertiary,"roads_tertiary",roads_tertiary_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_roads_track,"roads_track",roads_track_tex,export_folder,tex_width,tex_height)
        # create_textures(texture_path_roads_unclasified,"roads_unclasified",roads_unclasified_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_areas_pedestrian,"areas_pedestrian",areas_pedestrian_tex,export_folder,tex_width,tex_height)
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds")   
        return {'FINISHED'}
        
class RAILWAYS(bpy.types.Operator):
    
    bl_idname = "object.railways"
    bl_label = "Texturize railways"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        
        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
        
        start_time = time.time()
        scn = context.scene.pbr_export_settings
        settings = type("Settings", (), {})()
        export_folder = bpy.path.abspath(scn.export_folder)
        texture_folder = bpy.path.abspath(scn.texture_folder)
        tex_width = scn.tex_width
        tex_height = scn.tex_height
 
        texture_path_railways = os.path.join(scn.texture_folder, "railways")
        texture_path_areas_railways = os.path.join(scn.texture_folder, "areas_railways")
        
        railways_tex = ""
        areas_railways_tex = ""

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER 
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: railways generation", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        create_textures(texture_path_railways,"railways",railways_tex,export_folder,tex_width,tex_height)
        create_textures(texture_path_areas_railways,"areas_railways",areas_railways_tex,export_folder,tex_width,tex_height)
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds")        
        return {'FINISHED'}

class GROUND(bpy.types.Operator):
    
    bl_idname = "object.ground"
    bl_label = "Texturize ground"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        
        if os.name.lower() == 'nt':
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
        
        start_time = time.time()
        scn = context.scene.pbr_export_settings
        settings = type("Settings", (), {})()
        export_folder = bpy.path.abspath(scn.export_folder)
        texture_folder = bpy.path.abspath(scn.texture_folder)
        tex_width = scn.tex_width
        tex_height = scn.tex_height
 
        texture_path_ground = os.path.join(scn.texture_folder, "ground")
        ground_tex = ""

        global GLOB_EXPORT_FOLDER 
        global GLOB_TEXTURE_FOLDER
        
        if export_folder:
            GLOB_EXPORT_FOLDER  = export_folder
        if texture_folder:
            GLOB_TEXTURE_FOLDER = texture_folder
        
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Starting subroutine: ground/terrain generation", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        
        create_textures(texture_path_ground,"EXPORT_GOOGLE_SAT_WM",ground_tex,export_folder,tex_width,tex_height)

        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream("Subroutine completed. Please proceed with the next step once ready.", stream = None, base_time = time.time())
        print_to_stream("Note: Blender may take a moment to update the viewport. Wait until the cursor stops spinning before continuing.", stream = None, base_time = time.time())
        print_to_stream("=" * 60 + "\n", stream = None, base_time = time.time())
        print_to_stream(f"Processing took: {time.time() - start_time:.2f} seconds.")
    
        return {'FINISHED'}
        
# TODO!
def generate_roof_details(building_obj, settings):
    """Add chimneys, vents, satellite dishes"""
    roof_details = []
    
    mesh = building_obj.data
    roof_polys = [p for p in mesh.polygons if abs(p.normal.z) > settings.roof_threshold]
    
    if not roof_polys:
        return []
    
    # Find highest roof face
    max_z = max(mesh.vertices[vi].co.z for p in roof_polys for vi in p.vertices)
    
    # Place 1-3 chimneys on roof
    num_chimneys = random.randint(1, 3) if random.random() > 0.3 else 0
    
    for i in range(num_chimneys):
        # Pick random roof polygon
        poly = random.choice(roof_polys)
        center = poly.center.copy()
        center.z = max_z
        
        roof_details.append({
            "type": "chimney",
            "position": blender_to_unity_coords([center.x, center.y, center.z]),
            "rotation": [0, random.uniform(0, 360), 0],
            "variant": random.choice(["brick_narrow", "brick_wide", "metal"])
        })
    
    return roof_details

def generate_wall_details(building_obj, settings):
    """Add AC units, pipes, wall-mounted stuff"""
    wall_details = []
    
    mesh = building_obj.data
    wall_polys = [p for p in mesh.polygons if abs(p.normal.z) < settings.roof_threshold]
    
    for poly in wall_polys:
        # 30% chance of AC unit per wall face
        if random.random() > 0.7:
            continue
        
        # Place AC units on multiple floors
        num_floors = int(building_obj.dimensions.z / settings.floor_height)
        for floor in range(1, num_floors):  # Skip ground floor
            center = poly.center.copy()
            center.z = floor * settings.floor_height
            
            wall_details.append({
                "type": "ac_unit",
                "position": blender_to_unity_coords([center.x, center.y, center.z]),
                "normal": blender_to_unity_coords([poly.normal.x, poly.normal.y, poly.normal.z]),
                "rotation": calculate_rotation_from_normal(poly.normal)
            })
    
    return wall_details

def join_meshes(mesh_objects, name="_MergedWater"):
    
    if not mesh_objects:
        return None

    # Create new mesh
    merged_mesh = bpy.data.meshes.new(name)
    merged_obj = bpy.data.objects.new(name, merged_mesh)
    bpy.context.scene.collection.objects.link(merged_obj)

    # Merge all meshes into one
    bm = bmesh.new()
    for obj in mesh_objects:
        temp_mesh = obj.data.copy()
        temp_bm = bmesh.new()
        temp_bm.from_mesh(temp_mesh)
        temp_bm.transform(obj.matrix_world)
        bm.from_mesh(temp_mesh)
        bm.verts.ensure_lookup_table()
        temp_bm.free()
    bm.to_mesh(merged_mesh)
    bm.free()

    return merged_obj

class WaterCarver(bpy.types.Operator):
    
    bl_idname = "object.water_carver"
    bl_label = "Carve Water"
    bl_options = {'REGISTER', 'UNDO'}
        
    def execute(self, context):

        scn = context.scene.pbr_export_settings
        srtm_obj = bpy.data.objects.get(scn.water_obj_srtm_name)
        water_obj_depth = scn.water_obj_depth
        srtm_obj_depth = scn.water_obj_srtm_depth
        apply_mods = scn.water_obj_apply_modifiers

        print_to_stream("Beginning water carving...\n", stream=None, base_time=time.time())

        # Deselect all objects
        bpy.ops.object.select_all(action='DESELECT')

        # Ensure the Scene Collection is selected and active
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[0]

        if not srtm_obj:
            print_to_stream("SRTM mesh not found!\n", stream=None, base_time=time.time())
            return {'CANCELLED'}

        # ===== STEP 1: Collect water meshes =====
        water_collection = bpy.data.collections.get("_WaterBooleans")
        if not water_collection:
            water_collection = bpy.data.collections.new("_WaterBooleans")
            bpy.context.scene.collection.children.link(water_collection)

        parent_collection = select_top_level_collection_by_name("water")
        if not parent_collection:
            messagebox_showerror("Error", "No water collection found!")
            return {'CANCELLED'}

        all_children = get_all_objects_in_collection(parent_collection)
        water_meshes = [obj for obj in all_children if obj.type == 'MESH']

        if not water_meshes:
            self.report({'ERROR'}, "No mesh children in water object found")
            return {'CANCELLED'}

        print_to_stream(f"=== STEP 1: Preparing {len(water_meshes)} water meshes ===\n", stream=None, base_time=time.time())
        start_time = time.time()

        # Create copies of all water meshes
        water_copies = []
        for mesh in water_meshes:
            copy_mesh = mesh.copy()
            copy_mesh.data = mesh.data.copy()
            copy_mesh.matrix_world = mesh.matrix_world.copy()
            water_collection.objects.link(copy_mesh)
            copy_mesh.hide_viewport = True
            water_copies.append(copy_mesh)

        # ===== STEP 3: Merge all water meshes into one =====
        merged_water = join_meshes(water_copies, name="_MergedWater")

        # Clean up merged mesh before extrude
        bpy.context.view_layer.objects.active = merged_water
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')

        # Remove doubles / merge close vertices
        bpy.ops.mesh.remove_doubles(threshold=0.001)

        # Fill any small holes
        bpy.ops.mesh.fill_holes(sides=8)

        # Recalculate normals
        bpy.ops.mesh.normals_make_consistent(inside=False)

        bpy.ops.object.mode_set(mode='OBJECT')

        print_to_stream("All water meshes merged into one.\n", stream=None, base_time=time.time())

       # ===== STEP 4: Extrude water =====
        print_to_stream("Extruding water...\n", stream=None, base_time=time.time())
        bpy.context.view_layer.objects.active = merged_water
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Extrude to make it tall enough to punch through
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, water_obj_depth)}
        )
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        merged_water.location.z = -10 
        
        # ===== STEP 5: SOLIDIFY SRTM =====
        print_to_stream("=== STEP 2: Adding thickness to SRTM ===\n", stream=None, base_time=time.time())
        bpy.context.view_layer.objects.active = srtm_obj
        srtm_obj.select_set(True)
        solidify = srtm_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
        solidify.thickness = srtm_obj_depth
        solidify.offset = -1.0
        bpy.ops.object.modifier_apply(modifier=solidify.name)
        print_to_stream(f"SRTM now has thickness: {srtm_obj_depth}\n", stream=None, base_time=time.time())
        
        # ===== STEP 6: Add single boolean to SRTM =====
        bpy.context.view_layer.objects.active = srtm_obj
        srtm_obj.select_set(True)
        
        bool_mod = srtm_obj.modifiers.new(name="Boolean", type='BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = merged_water

        print_to_stream("Boolean modifier added to SRTM.\n", stream=None, base_time=time.time())

        # ===== STEP 7: Apply modifier if requested =====
        if apply_mods:
            bpy.context.view_layer.objects.active = srtm_obj
            bpy.ops.object.modifier_apply(modifier=bool_mod.name)
            bpy.data.objects.remove(merged_water, do_unlink=True)
            bpy.data.collections.remove(water_collection)
            print_to_stream("Boolean applied and merged water deleted.\n", stream=None, base_time=time.time())

        # Position it 
        for water_mesh in water_meshes:
            # Remove shrinkwrap modifiers
            for mod in list(water_mesh.modifiers):
                if mod.type == 'SHRINKWRAP':
                    water_mesh.modifiers.remove(mod)
            water_mesh.location.z = 1
        
        elapsed = time.time() - start_time
        print_to_stream(f"Water carving complete! Total elapsed time: {elapsed:.2f} seconds\n", stream=None, base_time=time.time())
        return {'FINISHED'}

        
# ===== Panel & Properties =====
class PBR_Exporter_Props(bpy.types.PropertyGroup):
    
    texture_folder: bpy.props.StringProperty(
        name="Texture folder",
        description="Folder containing all textures",
        default="\Textures\ folder...",
        subtype='DIR_PATH'
    )
    export_folder: bpy.props.StringProperty(
        name="Export folder",
        description="Folder where FBX and textures are saved",
        default="\Export\ folder...",
        subtype='DIR_PATH'
    )

    solidify: bpy.props.BoolProperty(
        name="Solidify objects",
        description="Apply solidify modifier to all walls",
        default=True
    )
    
    water_obj_apply_modifiers: bpy.props.BoolProperty(
        name="Apply Modifiers?",
        description="Waterway modifiers",
        default=True
    )

    wall_thickness: bpy.props.FloatProperty(name="Wall Thickness", default=0.15)
    tex_width: bpy.props.FloatProperty(name="Texture Width", default=2.0)
    tex_height: bpy.props.FloatProperty(name="Texture Height", default=2.0)
    roof_threshold: bpy.props.FloatProperty(name="Roof Normal Threshold", default=0.85)
    # Doors and windows.
    floor_height: bpy.props.FloatProperty(name="Floor Height", default=3.0, min=0.0, max=100)
    door_prob: bpy.props.FloatProperty(name="Door Probability", default=0.8, min=0.0, max=1.0)
    door_width: bpy.props.FloatProperty(name="Door Width", default=2.0)
    door_height: bpy.props.FloatProperty(name="Door Height", default=3.5)   
    window_prob: bpy.props.FloatProperty(name="Window Probability", default=0.8, min=0.0, max=1.0)
    window_width: bpy.props.FloatProperty(name="Window Width", default=1.0)
    window_height: bpy.props.FloatProperty(name="Window Height", default=1.5)
    water_obj_name: bpy.props.StringProperty(name="Water Object Name", default="map_3.osm_water")
    water_obj_depth: bpy.props.FloatProperty(name="Depth", default=25.0, min=0.1, max=100.0)
    water_obj_srtm_name: bpy.props.StringProperty(name="SRTM Object Name", default="EXPORT_GOOGLE_SAT_WM")
    water_obj_srtm_depth: bpy.props.FloatProperty(name="Srtm Depth", default=50.0, min=0.1, max=500.0)

    tree_density: bpy.props.FloatProperty(
        name="Tree Density",
        description="Approx. trees placed per square meter of forest/park area",
        default=0.02, min=0.0, max=1.0
    )
    tree_min_scale: bpy.props.FloatProperty(name="Min Tree Scale", default=0.8, min=0.1, max=10.0)
    tree_max_scale: bpy.props.FloatProperty(name="Max Tree Scale", default=1.4, min=0.1, max=10.0)
    tree_min_spacing: bpy.props.FloatProperty(
        name="Min Tree Spacing",
        description="Minimum distance in meters between placed trees",
        default=1.5, min=0.0, max=50.0
    )
    tree_seed: bpy.props.IntProperty(name="Tree Random Seed", default=0)
    tree_also_vegetation: bpy.props.BoolProperty(
        name="Also scatter on vegetation areas",
        description="In addition to 'forest' areas, also place a lighter scattering of trees on 'vegetation' areas",
        default=False
    )
    tree_terrain_obj_name: bpy.props.StringProperty(
        name="Terrain Object",
        description="Name of the terrain/SRTM object to raycast tree height against. Leave empty to use the forest mesh's own Z.",
        default="EXPORT_GOOGLE_SAT_WM"
    )
    tree_source_objects: bpy.props.StringProperty(
        name="Tree Source Objects",
        description="Comma-separated names of existing MESH objects in the scene to instance as trees (e.g. imported tree models). Leave empty to use the built-in placeholder trees.",
        default=""
    )
    tree_auto_normalize_z: bpy.props.BoolProperty(
        name="Normalize to terrain base",
        description="Subtract the terrain object's lowest point from every tree's height, so trees sit relative to local ground level (~0) instead of real-world SRTM elevation",
        default=True
    )
    tree_z_offset: bpy.props.FloatProperty(
        name="Tree Z Offset",
        description="Extra height added to every placed tree after normalization, for manual fine-tuning",
        default=13.0
    )
    
class OBJECT_PT_pbr_exporter_panel(bpy.types.Panel):
    
    bl_label = "World Builder"
    bl_idname = "OBJECT_PT_pbr_exporter_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "World Builder"

    def draw(self, context):
        layout = self.layout
        scn = context.scene.pbr_export_settings
        layout.prop(scn, "texture_folder")
        layout.prop(scn, "export_folder")
        layout.label(text="Material Settings:")
        layout.prop(scn, "solidify")
        layout.prop(scn, "wall_thickness")
        layout.prop(scn, "tex_width")
        layout.prop(scn, "tex_height")
        layout.prop(scn, "roof_threshold")
        layout.operator("object.run_pbr_export", text="1. Texturize walls & roofs")
        layout.label(text="Greenery textures:")
        layout.operator("object.greenery", text="2. Texturize greenery") 
        layout.label(text="Trees:")
        layout.prop(scn, "tree_density")
        layout.prop(scn, "tree_min_scale")
        layout.prop(scn, "tree_max_scale")
        layout.prop(scn, "tree_min_spacing")
        layout.prop(scn, "tree_seed")
        layout.prop(scn, "tree_also_vegetation")
        layout.prop(scn, "tree_terrain_obj_name")
        layout.prop(scn, "tree_source_objects")
        layout.prop(scn, "tree_auto_normalize_z")
        layout.prop(scn, "tree_z_offset")
        layout.operator("object.place_trees", text="2b. Place trees")
        layout.label(text="Waterways:")
        layout.prop(scn, "water_obj_name")
        layout.prop(scn, "water_obj_depth")
        layout.prop(scn, "water_obj_srtm_name")
        layout.prop(scn, "water_obj_srtm_depth")
        layout.prop(scn, "water_obj_apply_modifiers")
        layout.operator("object.waterways", text="3. Carve/Texturize waterways") 
        layout.label(text="Roads textures:")
        layout.operator("object.roads", text="4. Texturize ALL roads")
        layout.label(text="Railway textures:")
        layout.operator("object.railways", text="5. Texturize railways") 
        layout.label(text="Terrain textures:")
        layout.operator("object.ground", text="6. Texturize terrain (SRTM)")         
        layout.label(text="Doors & Windows:")
        layout.prop(scn, "floor_height")
        layout.prop(scn, "door_prob")
        layout.prop(scn, "door_width")
        layout.prop(scn, "door_height")
        layout.prop(scn, "window_prob")
        layout.prop(scn, "window_width")
        layout.prop(scn, "window_height")
        layout.operator("object.windows_and_doors", text="7. Decal windows & doors")
        layout.label(text="===================")
        layout.operator("object.export_data", text="8. FINISH: EXPORT ALL DATA")

# ===== Register =====

classes = [
    WorldBuilderSettings,
    BuildingMetadata,
    PBR_Exporter_Props,
    OBJECT_OT_run_pbr_export,
    GREENERY,
    TREES,
    WATERWAYS,
    ROADS,
    RAILWAYS,
    GROUND,
    WINDOWS_AND_DOORS,
    EXPORT_DATA,
    OBJECT_PT_pbr_exporter_panel,
    WaterCarver
]

def register():
    
    for cls in classes:
        bpy.utils.register_class(cls)
        
    if bpy.app.background:
        if hasattr(bpy.types.Scene, "pbr_export_settings"):
            del bpy.types.Scene.pbr_export_settings
        bpy.types.Scene.pbr_export_settings = bpy.props.PointerProperty(type=WorldBuilderSettings)
    else:
        if not hasattr(bpy.types.Scene, "pbr_export_settings"):
            bpy.types.Scene.pbr_export_settings = bpy.props.PointerProperty(type=PBR_Exporter_Props)

def unregister():
    if not bpy.app.background:
        if hasattr(bpy.types.Scene, "pbr_export_settings"):
            del bpy.types.Scene.pbr_export_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
# ----------------------------
# Register and check Console mode (headless) logic
# ----------------------------

if __name__ == "__main__":
    
    register()
    
    if bpy.app.background:
        argv = sys.argv
        args = argv[argv.index("--") + 1:] if "--" in argv else []
        params = {}
     
        for arg in args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                params[key] = auto_cast(value)
            elif arg.lower() in ("true", "false"):
                params[arg] = auto_cast(arg)
                
        apply_cli_args_to_scene(params)
        
        if "--help" in args or "-h" in args:
            print_help_message()
            sys.exit(0)
            
        print_to_stream(f"Console args loaded: {params}\n", stream=None, base_time=time.time())

        # Defaults
        defaults = {
            "wall_thickness": 0.15,
            "tex_width": 2.0,
            "tex_height": 2.0,
            "roof_threshold": 0.85,
            "floor_height": 3.0,
            "door_prob": 0.8,
            "door_width": 2.0,
            "door_height": 3.5,
            "window_prob": 0.8,
            "window_width": 1.0,
            "window_height": 1.5
        }

        # Merge defaults + CLI args
        for key, value in {**defaults, **params}.items():
            globals()[f"console_{key}"] = value
            globals()[key] = value

        # Normalize process flags
        processes = {
            "process_buildings": console_generate_buildings,
            "process_openings": console_generate_openings,
            "process_roads": console_generate_roads,
            "process_vegetation": console_generate_vegetation,
            "process_trees": console_place_trees,
            "process_waterways": console_generate_water,
            "process_railways": console_generate_railways,
            "process_terrain": console_generate_terrain
        }

        for k in processes.keys():
            params[k] = bool(params.get(k, False))

        # Run processes
        if any(params.get(k, False) for k in processes.keys()):
            any_done = False

            try:
                bpy.ops.wm.save_mainfile.poll = lambda: False
                print_to_stream(
                    "Console: Disabled default Blender saving, using custom export.\n",
                    stream=None,
                    base_time=time.time()
                )
            except Exception:
                pass

            print_to_stream(f"Console headless params: {params}\n", stream=None, base_time=time.time())
            ensure_global_export_folder()

            if "--all" in args or "--any" in args:
                run_stage("buildings", console_generate_buildings)
                run_stage("openings (windows/doors/vents)", console_generate_openings)
                run_stage("roads", console_generate_roads)
                run_stage("vegetation", console_generate_vegetation)
                run_stage("trees", console_place_trees)
                run_stage("waterways", console_generate_water)
                run_stage("railways", console_generate_railways)
                run_stage("terrain/ground", console_generate_terrain)
                any_done = True
            else:
                for key, func in processes.items():
                    if params.get(key, False):
                        print_to_stream(f"Console starting process: {key}\n", stream=None, base_time=time.time())
                        func()
                        any_done = True

            if any_done:
                print_to_stream("Console is now exporting data...\n", stream=None, base_time=time.time())
                console_export_data()
                print_to_stream("Console export complete!\n", stream=None, base_time=time.time())
