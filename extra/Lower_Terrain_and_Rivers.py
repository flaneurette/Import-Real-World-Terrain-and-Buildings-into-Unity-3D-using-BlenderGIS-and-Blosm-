import bpy
import bmesh
from bpy.props import FloatProperty, IntProperty, BoolProperty
from bpy.types import Operator
from mathutils import Vector
from math import radians, sin, cos

class OBJECT_OT_RiverCarver(Operator):
    """Carve a river into the terrain mesh"""
    bl_idname = "object.river_carver"
    bl_label = "River Carver"
    bl_options = {'REGISTER', 'UNDO'}

    depth: FloatProperty(
        name="Depth",
        description="Depth of the river carving",
        default=7.0,
        min=0.1,
        max=50.0,
        unit='LENGTH'
    )

    angle: IntProperty(
        name="Wall Angle",
        description="Angle of the river walls (70-90)",
        default=80,
        min=70,
        max=90
    )

    width_factor: FloatProperty(
        name="Width Factor",
        description="Factor to adjust river width",
        default=1.0,
        min=0.1,
        max=5.0
    )

    smooth_iterations: IntProperty(
        name="Smooth Iterations",
        description="Number of smoothing iterations",
        default=2,
        min=0,
        max=10
    )

    preserve_buildings: BoolProperty(
        name="Preserve Buildings",
        description="Prevent carving under buildings",
        default=True
    )

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None and
                context.active_object.type == 'MESH' and
                'srtm' in context.active_object.name.lower())

    def execute(self, context):
        river_obj = None
        srtm_obj = context.active_object
        building_objs = []

        # Find river object (element.5970)
        for obj in context.scene.objects:
            if 'element.5970' in obj.name:
                river_obj = obj
                break

        if not river_obj:
            self.report({'ERROR'}, "River object (element.5970) not found")
            return {'CANCELLED'}

        # Find building objects (tan colored)
        for obj in context.scene.objects:
            if obj.type == 'MESH' and obj != srtm_obj and obj != river_obj:
                # Simple check for buildings (tan colored)
                if obj.active_material and obj.active_material.diffuse_color:
                    color = obj.active_material.diffuse_color
                    # Check if color is in tan range (simple check)
                    if (0.6 < color.r < 0.9 and 0.5 < color.g < 0.8 and 0.3 < color.b < 0.6):
                        building_objs.append(obj)

        # Convert angle to slope factor
        slope_angle = radians(self.angle)
        slope_factor = 1.0 / sin(slope_angle)

        # Create a bmesh copy of the SRTM mesh
        bm = bmesh.new()
        bm.from_mesh(srtm_obj.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Get world matrix for transformations
        srtm_matrix = srtm_obj.matrix_world
        river_matrix = river_obj.matrix_world

        # Create a BVHTree from the river mesh for proximity checks
        river_bm = bmesh.new()
        river_bm.from_mesh(river_obj.data)
        river_bm.transform(river_matrix)
        river_bvhtree = mathutils.bvhtree.BVHTree.FromBMesh(river_bm)

        # Create BVHTrees for buildings if preserving them
        building_bvhtrees = []
        if self.preserve_buildings:
            for building in building_objs:
                building_bm = bmesh.new()
                building_bm.from_mesh(building.data)
                building_bm.transform(building.matrix_world)
                building_bvhtrees.append(mathutils.bvhtree.BVHTree.FromBMesh(building_bm))

        # Get the closest distance and normal for each vertex
        for vert in bm.verts:
            # Get position in world space
            world_pos = srtm_matrix @ vert.co

            # Check if vertex is near the river
            dist, normal, index, _ = river_bvhtree.find_nearest(world_pos)

            # Skip if too far from river
            if dist > river_obj.dimensions.x * self.width_factor:
                continue

            # Check if vertex is under a building
            if self.preserve_buildings:
                is_under_building = False
                for building_bvhtree in building_bvhtrees:
                    _, _, _, d = building_bvhtree.find_nearest(world_pos)
                    if d < 0.1:  # Small threshold to detect if under building
                        is_under_building = True
                        break

                if is_under_building:
                    continue

            # Calculate how much to lower this vertex based on distance from river center
            # Vertices closer to the center get lowered more
            distance_factor = min(1.0, dist / (river_obj.dimensions.x * self.width_factor * 0.5))
            depth_factor = 1.0 - (distance_factor ** 2)  # More aggressive falloff

            # Calculate the lowering amount with slope
            lower_amount = self.depth * depth_factor * (1.0 - (distance_factor ** slope_factor))

            # Lower the vertex
            vert.co -= normal * lower_amount

        # Smooth the modified area
        if self.smooth_iterations > 0:
            # Get vertices that were modified
            modified_verts = [v for v in bm.verts if (srtm_matrix @ v.co).length != v.co.length]

            # Create a vertex group for the modified area
            if not srtm_obj.vertex_groups.get("RiverCarving"):
                srtm_obj.vertex_groups.new(name="RiverCarving")

            vgroup = srtm_obj.vertex_groups["RiverCarving"]
            for i, v in enumerate(bm.verts):
                if v in modified_verts:
                    vgroup.add([i], 1.0, 'REPLACE')

            # Apply smoothing
            for _ in range(self.smooth_iterations):
                for v in modified_verts:
                    avg_co = Vector((0, 0, 0))
                    count = 0
                    for e in v.link_edges:
                        other_v = e.other_vert(v)
                        if other_v in modified_verts:
                            avg_co += other_v.co
                            count += 1

                    if count > 0:
                        avg_co /= count
                        v.co = avg_co

        # Update the mesh
        bm.to_mesh(srtm_obj.data)
        srtm_obj.data.update()

        # Free resources
        bm.free()
        river_bm.free()

        self.report({'INFO'}, f"River carved with depth {self.depth}m and angle {self.angle}°")
        return {'FINISHED'}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "depth")
        layout.prop(self, "angle")
        layout.prop(self, "width_factor")
        layout.prop(self, "smooth_iterations")
        layout.prop(self, "preserve_buildings")

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_RiverCarver.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_RiverCarver)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_RiverCarver)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()
