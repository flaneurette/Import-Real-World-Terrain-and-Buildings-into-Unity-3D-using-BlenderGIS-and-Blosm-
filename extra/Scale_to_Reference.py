import bpy
import os
import ctypes

bl_info = {
    "name": "Scale & Align mesh to Reference",
    "blender": (2, 83, 0),
    "category": "Object",
    "author": "Flaneurette",
    "description": "Scale and align mesh objects to match a reference mesh with real-world dimensions automatically"
}

# Only include mesh objects and empties
def get_mesh_objects(self, context):
    return [(obj.name, obj.name, "") for obj in bpy.data.objects if obj.type in ['MESH', 'EMPTY']]

# Get the file path of the imported model (fallback to the current directory if not available)
def get_imported_file_path(obj):
    if hasattr(obj, "data") and hasattr(obj.data, "filepath"):
        return os.path.dirname(bpy.path.abspath(obj.data.filepath))
    return bpy.path.abspath("//")  # Default to the project directory

class OBJECT_OT_scale_align_reference(bpy.types.Operator):
    bl_idname = "object.scale_align_reference"
    bl_label = "Scale & Align"
    bl_options = {'REGISTER', 'UNDO'}

    axis: bpy.props.EnumProperty(
        name="Axis",
        description="Axis or dimension to match",
        items=[('X', "X", ""),
               ('Y', "Y", ""),
               ('Z', "Z", ""),
               ('MAX', "Max", "Match largest dimension")],
        default='MAX'
    )

    reference_name: bpy.props.EnumProperty(
        name="Reference Object",
        description="Choose the reference mesh object",
        items=get_mesh_objects
    )

    target_name: bpy.props.EnumProperty(
        name="Target Object",
        description="Choose the target mesh object",
        items=get_mesh_objects
    )

    export_format: bpy.props.EnumProperty(
        name="Export Format",
        description="Choose the export format",
        items=[('FBX', "FBX", ""),
               ('OBJ', "OBJ", ""),
               ('GLB', "GLB", "")],
        default='FBX'
    )

    def execute(self, context):

        if os.name == 'nt':  # Windows only
            # Show the Blender console window
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
            
        ref = bpy.data.objects.get(self.reference_name)
        target = bpy.data.objects.get(self.target_name)

        if not ref or not target:
            self.report({'ERROR'}, "Reference or Target object not found!")
            return {'CANCELLED'}

        ref_dims = ref.dimensions
        target_dims = target.dimensions

        # Debugging: Print the actual dimensions of the reference and target objects
        self.report({'INFO'}, f"Reference dimensions (Blender units): {ref_dims}")
        self.report({'INFO'}, f"Target dimensions (Blender units): {target_dims}")

        # Safety check for zero dimensions
        if max(target_dims) == 0 or max(ref_dims) == 0:
            self.report({'ERROR'}, "Reference or Target object has zero size!")
            return {'CANCELLED'}

        # Calculate scale factor based on the reference dimensions (Blender units = real-world)
        scale_factor_height = 10.0 / ref_dims.z if ref_dims.z != 0 else 1.0
        scale_factor_width = 1.0 / ref_dims.x if ref_dims.x != 0 else 1.0

        # Debugging: Print the scale factor for the Z-axis
        self.report({'INFO'}, f"Scale factor (height): {scale_factor_height:.3f}")

        # Choose the axis to scale
        if self.axis == 'X':
            scale_factor = scale_factor_width
        elif self.axis == 'Y':
            scale_factor = scale_factor_height
        elif self.axis == 'Z':
            scale_factor = scale_factor_height
        else:  # MAX
            scale_factor = max(scale_factor_height, scale_factor_width)

        # Skip scaling if the factor is 1 (no change)
        if scale_factor == 1:
            self.report({'INFO'}, "No scaling needed (target and reference are the same size).")
            return {'FINISHED'}

        # Apply scale
        target.scale = [s * scale_factor for s in target.scale]
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.transform_apply(scale=True)

        # Align location & rotation
        target.location = ref.location
        target.rotation_euler = ref.rotation_euler

        # Export model
        # self.export_model(target, context, ref.name)

        return {'FINISHED'}

class OBJECT_OT_export_model(bpy.types.Operator):
    bl_idname = "object.export_model"
    bl_label = "Export Model"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        if os.name == 'nt':  # Windows only
            # Show the Blender console window
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 5)
            
        scene = context.scene
        target = bpy.data.objects.get(scene.scale_target)
        
        if not target:
            self.report({'ERROR'}, "Target object not found!")
            return {'CANCELLED'}
            
        # Get the path where the model was imported from
        path = get_imported_file_path(target)
        if not path:
            path = bpy.path.abspath("//")  # Default to the project directory

        filename = f"{target.name}_scaled.{scene.export_format.lower()}"
        export_path = os.path.join(path, filename)

        bpy.ops.object.select_all(action='DESELECT')

        all_objects = [obj for obj in bpy.data.objects if obj.type in {'EMPTY', 'MESH'}]
    
        if not all_objects:
            self.report({'ERROR'}, "No objects found in scene")
            return {'CANCELLED'}

        # Reload all textures to absolute paths
        self.report({'INFO'}, "Reloading textures...")
        for img in bpy.data.images:
            if img.source == 'FILE' and img.filepath:
                try:
                    abs_path = bpy.path.abspath(img.filepath)
                    if os.path.exists(abs_path):
                        img.filepath = abs_path  # Make absolute
                        img.reload()
                        self.report({'INFO'}, f"Reloaded: {img.name}")
                    else:
                        self.report({'WARNING'}, f"Missing: {img.name} at {abs_path}")
                except Exception as e:
                    self.report({'ERROR'}, f"Failed to reload: {img.name} - {e}")

        ref = bpy.data.objects.get(scene.scale_ref)
        print("Getting object: " + ref.name)
        if ref:
            for child in ref.children:
                child.select_set(False)
            ref.select_set(False)
        print("Deselected " + ref.name + " for export")
        # Store reference object name before deleting it
        reference_name = ref.name

        # Loop through all objects in the scene and select everything except the reference object
        for obj in bpy.data.objects:
            if obj.name != reference_name:  # Exclude reference object
                obj.select_set(True)
                
        try:
            # Export all selected objects to FBX format
            if scene.export_format == 'FBX':
                bpy.ops.export_scene.fbx(
                    filepath=export_path,
                    global_scale=1.0,
                    use_selection=True,
                    object_types={'MESH', 'EMPTY'},  # Include both meshes and empties
                    use_mesh_modifiers=True,  # Ensure modifiers are applied
                    use_mesh_edges=False,
                    use_tspace=False,
                    use_custom_props=True,
                    add_leaf_bones=False,
                    bake_space_transform=False,
                    path_mode='COPY',
                    embed_textures=True,
                    axis_forward='-Z',
                    axis_up='Y',
                    apply_unit_scale=True,
                    mesh_smooth_type='FACE',
                    apply_scale_options='FBX_SCALE_ALL',
                    bake_anim=False
                )

            elif scene.export_format == 'OBJ':
                bpy.ops.export_scene.obj(
                    filepath=export_path,
                    use_selection=True,
                    use_materials=True  # Export with materials (textures)
                )

            elif scene.export_format == 'GLB':
                bpy.ops.export_scene.gltf(
                    filepath=export_path,
                    use_selection=True,
                    export_format='GLTF_EMBEDDED',  # Export embedded textures within the GLB file
                    export_materials=True  # Ensure materials (textures) are exported
                )

            self.report({'INFO'}, f"Exported '{target.name}' to: {export_path}")

        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {str(e)}")
            return {'CANCELLED'}

        return {'FINISHED'}

class VIEW3D_PT_scale_align_panel(bpy.types.Panel):
    bl_label = "Scale & Align to Reference"
    bl_idname = "VIEW3D_PT_scale_align_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Scale Model"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "scale_axis")
        layout.prop(scene, "scale_ref")
        layout.prop(scene, "scale_target")
        layout.prop(scene, "export_format")  # Export format selection
        layout.operator("object.scale_align_reference")
        layout.operator("object.export_model")


def register():
    bpy.utils.register_class(OBJECT_OT_scale_align_reference)
    bpy.utils.register_class(VIEW3D_PT_scale_align_panel)
    bpy.utils.register_class(OBJECT_OT_export_model)

    bpy.types.Scene.scale_axis = bpy.props.EnumProperty(
        name="Axis",
        description="Axis or dimension to match",
        items=[('X', "X", ""),
               ('Y', "Y", ""),
               ('Z', "Z", ""),
               ('MAX', "Max", "Match largest dimension")],
        default='MAX'
    )

    bpy.types.Scene.scale_ref = bpy.props.EnumProperty(
        name="Reference Object",
        description="Reference mesh object",
        items=get_mesh_objects
    )

    bpy.types.Scene.scale_target = bpy.props.EnumProperty(
        name="Target Object",
        description="Target mesh object",
        items=get_mesh_objects
    )

    bpy.types.Scene.export_format = bpy.props.EnumProperty(
        name="Export Format",
        description="Choose the export format",
        items=[('FBX', "FBX", ""),
               ('OBJ', "OBJ", ""),
               ('GLB', "GLB", "")],
        default='FBX'
    )


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_scale_align_reference)
    bpy.utils.unregister_class(VIEW3D_PT_scale_align_panel)
    bpy.utils.unregister_class(OBJECT_OT_export_model)
    del bpy.types.Scene.scale_axis
    del bpy.types.Scene.scale_ref
    del bpy.types.Scene.scale_target
    del bpy.types.Scene.export_format


if __name__ == "__main__":
    register()
