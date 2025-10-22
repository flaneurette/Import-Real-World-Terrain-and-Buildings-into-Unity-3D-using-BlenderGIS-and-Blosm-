bl_info = {
    "name": "Water Carve",
    "blender": (2, 83, 0),
    "category": "Object",
    "author": "Your Name",
    "description": "Carve a river into an SRTM mesh.",
    "version": (1, 0, 0),
    "support": "COMMUNITY",
}

import bpy
import bmesh


# Operator for the river carving process
class WaterCarveOperator(bpy.types.Operator):
    bl_idname = "object.river_carve"
    bl_label = "Carve Water"
    bl_options = {'REGISTER', 'UNDO'}

    water_obj_name: bpy.props.StringProperty(name="Water Object Name", default="element.8001")
    depth: bpy.props.FloatProperty(name="Depth", default=25.0, min=0.1, max=100.0)
    srtm_name: bpy.props.StringProperty(name="SRTM Object Name", default="srtm")
    srtm_depth: bpy.props.FloatProperty(name="Srtm Depth", default=50.0, min=0.1, max=500.0)

    def execute(self, context):

        # Deselect all objects first
        bpy.ops.object.select_all(action='DESELECT')
    
        # Ensure the Scene Collection is selected and active
        scene_collection = bpy.context.scene.collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[0]

        # Get the river and SRTM meshes
        river_obj = bpy.data.objects.get(self.water_obj_name)
        srtm_obj = bpy.data.objects.get(self.srtm_name)

        if not river_obj or not srtm_obj:
            self.report({'ERROR'}, "Water or SRTM mesh not found")
            return {'CANCELLED'}

        # ===== STEP 1: PREPARE RIVER MESH =====
        print("\n=== STEP 1: Preparing river mesh ===")

        river_copy = river_obj.copy()
        river_copy.data = river_obj.data.copy()  # Copy the mesh data as well
        bpy.context.collection.objects.link(river_copy)  # Link the copy to the scene
        
        # Remove shrinkwrap modifiers
        for mod in list(river_copy.modifiers):
            if mod.type == 'SHRINKWRAP':
                river_copy.modifiers.remove(mod)

        bpy.context.view_layer.objects.active = river_copy
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        
        # Extrude to make it tall enough to punch through
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={"value": (0, 0, self.depth)}
        )
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        
        # Position it to cut through both top and bottom
        river_copy.location.z = -10 
        
        print("Water mesh prepared")

        # ===== STEP 2: SOLIDIFY SRTM FIRST =====
        print("=== STEP 2: Adding thickness to SRTM ===")
        bpy.context.view_layer.objects.active = srtm_obj
        srtm_obj.select_set(True)
        
        solidify = srtm_obj.modifiers.new(name="Solidify", type='SOLIDIFY')
        solidify.thickness = self.srtm_depth  # Give it real depth
        solidify.offset = -1.0  # Extrude downward
        
        bpy.ops.object.modifier_apply(modifier=solidify.name)
        print("SRTM now has thickness")
        
        # ===== STEP 3: BOOLEAN DIFFERENCE =====
        print("\n=== STEP 3: BOOLEAN DIFFERENCE ===")
        
        bpy.context.view_layer.objects.active = srtm_obj
        srtm_obj.select_set(True)
        
        bool_mod = srtm_obj.modifiers.new(name="Boolean", type='BOOLEAN')
        bool_mod.operation = 'DIFFERENCE'
        bool_mod.object = river_copy
        
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
        print("Water carved")

        # ===== STEP 4: RESET RIVER =====
        bpy.data.objects.remove(river_copy)  # Remove the duplicate mesh after carving
        # Position it 
        river_obj.location.z = 1
        
        print("Water mesh made smaller again, and lowered into banks")
        
        print("\nWater carving complete!")
        self.report({'INFO'}, "Water carved successfully!")

        return {'FINISHED'}


# Popup for depth and object names input
class WaterCarvePopup(bpy.types.Operator):
    bl_idname = "object.river_carve_popup"
    bl_label = "Water Carve Settings"

    depth: bpy.props.FloatProperty(name="Water Depth", default=25.0, min=0.1, max=100.0)
    srtm_name: bpy.props.StringProperty(name="SRTM Object Name", default="srtm")
    srtm_depth: bpy.props.FloatProperty(name="Srtm Depth", default=50.0, min=0.1, max=500.0)
    water_obj_name: bpy.props.StringProperty(name="Water Object Name", default="element.8001")

    def execute(self, context):
        # Create the river carve operation with the user inputs
        bpy.ops.object.river_carve(water_obj_name=self.water_obj_name, depth=self.depth, srtm_name=self.srtm_name, srtm_depth=self.srtm_depth)
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "water_obj_name")
        layout.prop(self, "depth")
        layout.prop(self, "srtm_name")
        layout.prop(self, "srtm_depth")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


# Panel to launch the popup from the Object menu
class WaterCarvePanel(bpy.types.Panel):
    bl_label = "Water Carve Panel"
    bl_idname = "OBJECT_PT_river_carve"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tool"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Carve Water into SRTM Mesh")
        
        # Button to invoke the popup
        layout.operator("object.river_carve_popup")


# Add the operator to the Object menu
def menu_func(self, context):
    self.layout.operator("object.river_carve_popup", text="Water Carve")


def register():
    bpy.utils.register_class(WaterCarveOperator)
    bpy.utils.register_class(WaterCarvePopup)
    bpy.utils.register_class(WaterCarvePanel)
    bpy.types.VIEW3D_MT_object.append(menu_func)  # Add to the Object menu


def unregister():
    bpy.utils.unregister_class(WaterCarveOperator)
    bpy.utils.unregister_class(WaterCarvePopup)
    bpy.utils.unregister_class(WaterCarvePanel)
    bpy.types.VIEW3D_MT_object.remove(menu_func)  # Remove from the Object menu


if __name__ == "__main__":
    register()
