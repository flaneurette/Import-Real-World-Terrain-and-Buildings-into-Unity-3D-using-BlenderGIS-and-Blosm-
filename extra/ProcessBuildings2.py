import random
import os
import shutil
import bpy
import bmesh
from mathutils import Vector

# ===== CONFIG =====
texture_folder = r"C:\Users\Gebruiker\Desktop\GAME\Textures"
roof_texture_file = r"C:\Users\Gebruiker\Desktop\GAME\Textures\roof.png"
unity_export_folder = r"C:\Users\Gebruiker\Desktop\GAME\Export"
texture_width = 2.0
texture_height = 2.0
roof_z_threshold = 0.85

# Create export structure
os.makedirs(os.path.join(unity_export_folder, "Models"), exist_ok=True)
os.makedirs(os.path.join(unity_export_folder, "Textures"), exist_ok=True)

# ===== HELPER FUNCTIONS =====
def copy_texture_for_unity(image_path, export_folder):
    """Copy texture to Unity export folder"""
    if not os.path.exists(image_path):
        return None
    
    filename = os.path.basename(image_path)
    dest_path = os.path.join(export_folder, "Textures", filename)
    
    try:
        shutil.copy2(image_path, dest_path)
        return dest_path
    except Exception as e:
        print(f"Failed to copy {filename}: {e}")
        return None

def get_or_create_material(texture_path, mat_name):
    """Create a material with texture"""
    mat = bpy.data.materials.get(mat_name)
    if mat:
        return mat
    
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    nodes.clear()
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    tex_node = nodes.new(type='ShaderNodeTexImage')
    
    output.location = (300, 0)
    bsdf.location = (0, 0)
    tex_node.location = (-300, 0)
    
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
    
    if os.path.exists(texture_path):
        tex_node.image = bpy.data.images.load(texture_path)
    
    return mat

def generate_face_uvs(mesh, face, uv_layer, tex_width, tex_height):
    """Generate planar UVs for a face"""
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
        loop = mesh.loops[loop_index]
        vert = mesh.vertices[loop.vertex_index]
        
        u = vert.co.dot(u_axis) / tex_width
        v = vert.co.dot(v_axis) / tex_height
        
        uv_layer.data[loop_index].uv = (u, v)

def prepare_mesh_fast(obj):
    """Prepare mesh using BMesh (fast, no mode switching)"""
    try:
        mesh = obj.data
        
        # Clear custom normals
        if mesh.has_custom_normals:
            mesh.free_normals_split()
        
        # Use BMesh for triangulation
        bm = bmesh.new()
        bm.from_mesh(mesh)
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        
        bm.to_mesh(mesh)
        bm.free()
        
        mesh.update()
        return True
        
    except Exception as e:
        print(f"Error preparing {obj.name}: {e}")
        return False

# ===== GET TEXTURES =====
print("\n" + "="*50)
print("COLLECTING TEXTURES")
print("="*50)

if not os.path.exists(texture_folder):
    print(f"ERROR: Texture folder not found: {texture_folder}")
    exit()

wall_textures = [
    os.path.join(texture_folder, f)
    for f in os.listdir(texture_folder)
    if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    and f.lower() != 'roof.png'
]

if not wall_textures:
    print("ERROR: No wall textures found!")
    exit()

if not os.path.exists(roof_texture_file):
    print(f"ERROR: Roof texture not found: {roof_texture_file}")
    exit()

print(f"Found {len(wall_textures)} wall textures")
print(f"Found roof texture")

# ===== COPY TEXTURES =====
print("\n" + "="*50)
print("COPYING TEXTURES TO UNITY")
print("="*50)

used_textures = set()

for tex_path in wall_textures:
    copy_texture_for_unity(tex_path, unity_export_folder)
    used_textures.add(tex_path)

copy_texture_for_unity(roof_texture_file, unity_export_folder)
used_textures.add(roof_texture_file)

print(f"✓ Copied {len(used_textures)} textures")

# ===== CREATE MATERIALS =====
print("\n" + "="*50)
print("CREATING MATERIALS")
print("="*50)

wall_materials = []
for tex_path in wall_textures:
    mat_name = f"WallMat_{os.path.splitext(os.path.basename(tex_path))[0]}"
    mat = get_or_create_material(tex_path, mat_name)
    wall_materials.append(mat)

roof_material = get_or_create_material(roof_texture_file, "RoofMat")

print(f"Created {len(wall_materials)} wall materials")
print(f"Created roof material")

# ===== GET ALL MESH OBJECTS =====
print("\n" + "="*50)
print("COLLECTING MESH OBJECTS")
print("="*50)

def get_all_children(obj):
    """Recursively get all children of an object"""
    all_children = []
    for child in obj.children:
        all_children.append(child)
        all_children.extend(get_all_children(child))
    return all_children

# ===== GET ALL MESH OBJECTS FROM SELECTED PARENT =====
selected = bpy.context.selected_objects

if not selected:
    print("No object selected! Select the parent of your buildings.")
    all_mesh_objects = []
else:
    parent = selected[0]  # Use first selected object as parent
    all_children = get_all_children(parent)
    all_mesh_objects = [obj for obj in all_children if obj.type == 'MESH']
    print(f"✓ Found {len(all_mesh_objects)} mesh children under '{parent.name}'")

# ===== ADD STOCHASTIC SEEDS TO OBJECTS =====
print("\n" + "="*50)
print("ADDING STOCHASTIC SEEDS FOR UNITY")
print("="*50)

seed_count = 0
for obj in all_mesh_objects:
    # Generate random seed for stochastic sampling in Unity
    obj["StochasticSeed"] = random.random()
    
    # Store material/texture info for Unity script
    if obj.data.materials:
        mat_name = obj.data.materials[0].name
        obj["MaterialName"] = mat_name
    
    seed_count += 1

print(f"✓ Added random seeds to {seed_count} objects")

# ===== APPLY MATERIALS & UVS =====
print("\n" + "="*50)
print("APPLYING MATERIALS & UVS")
print("="*50)

processed = 0
for obj in all_mesh_objects:
    processed += 1
    if processed % 50 == 0:
        print(f"  Processing {processed}/{len(all_mesh_objects)}...")
    
    mesh = obj.data
    
    # Ensure UV layer
    if not mesh.uv_layers:
        mesh.uv_layers.new(name="UVMap")
    uv_layer = mesh.uv_layers.active
    
    # Clear existing materials
    mesh.materials.clear()
    
    # Add both materials
    mesh.materials.append(random.choice(wall_materials))
    mesh.materials.append(roof_material)
    
    # Assign materials to faces
    for poly in mesh.polygons:
        is_roof = abs(poly.normal.z) > roof_z_threshold
        poly.material_index = 1 if is_roof else 0
        generate_face_uvs(mesh, poly, uv_layer, texture_width, texture_height)
    
    mesh.update()

print(f"Applied materials to {len(all_mesh_objects)} objects")

# ===== PREPARE MESHES FOR EXPORT =====
print("\n" + "="*50)
print("PREPARING MESHES FOR EXPORT")
print("="*50)

objects_to_export = []
processed = 0

for obj in all_mesh_objects:
    processed += 1
    if processed % 50 == 0:
        print(f"Preparing {processed}/{len(all_mesh_objects)}...")
    
    if prepare_mesh_fast(obj):
        objects_to_export.append(obj)

print(f"{len(objects_to_export)} meshes ready")

# ===== EXPORT FBX =====
print("\n" + "="*50)
print("EXPORTING FBX")
print("="*50)

export_path = os.path.join(unity_export_folder, "Models", "buildings.fbx")

bpy.ops.object.select_all(action='DESELECT')
for obj in objects_to_export:
    obj.select_set(True)

print("Writing FBX file...")
bpy.ops.export_scene.fbx(
    filepath=export_path,
    use_selection=True,
    object_types={'MESH'},
    use_mesh_modifiers=False,
    mesh_smooth_type='OFF',
    use_mesh_edges=False,
    use_tspace=False,
    use_custom_props=True,  # ← CRITICAL: Export custom properties!
    add_leaf_bones=False,
    bake_space_transform=False,
    path_mode='COPY',
    embed_textures=True,
    axis_forward='-Z',
    axis_up='Y',
    apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_ALL',
    bake_anim=False
)

# ===== EXPORT SEED MAPPING (FOR UNITY REFERENCE) =====
print("\n" + "="*50)
print("CREATING SEED REFERENCE FILE")
print("="*50)

seed_file_path = os.path.join(unity_export_folder, "stochastic_seeds.txt")
with open(seed_file_path, 'w') as f:
    f.write("# Stochastic Seeds for Unity\n")
    f.write("# Format: ObjectName | Seed | MaterialName\n\n")
    for obj in objects_to_export:
        seed = obj.get("StochasticSeed", 0.5)
        mat = obj.get("MaterialName", "Unknown")
        f.write(f"{obj.name} | {seed:.6f} | {mat}\n")

print(f"✓ Created seed reference file: {seed_file_path}")

# ===== COMPLETION SUMMARY =====
print("\n" + "="*50)
print("EXPORT COMPLETE!")
print("="*50)
print(f"FBX: {export_path}")
print(f"Textures: {os.path.join(unity_export_folder, 'Textures')}")
print(f"Seeds: {seed_file_path}")
print(f"Meshes: {len(objects_to_export)}")
print(f"Materials: {len(used_textures)}")
print("\nStochastic seeds have been embedded in FBX!")
print("   Unity shader will use these for randomization")
print("\n" + "="*50)
print("UNITY IMPORT:")
print("="*50)
print("1. Copy 'Export' folder to Unity Assets")
print("2. Import the shader into shaders folder. Then import ApplyStochasticMaterials.cs script into the scripts folder")
print("3. Select FBX → Inspector → Materials:")
print("   - 'Extract Materials'")
print("   - 'Use External Materials (Legacy)'")
print("4. Model tab:")
print("   - Normals: 'Calculate'")
print("   - Tangents: 'Calculate Mikktspace'")
print("5. Drag FBX into Hierarchy. Then drag and drop ApplyStochasticMaterials.cs script to inspector")
print("5.1. Then drag shader file into slot")
print("6. Right click on script: Run 'Apply Stochastic Materials' from context menu")
print("="*50)
print("\nScript complete!")
