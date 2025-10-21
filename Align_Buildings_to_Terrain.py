bl_info = {
    "name": "Align Buildings to Terrain (Lowest Vertex)",
    "author": "ChatGPT",
    "version": (1, 3),
    "blender": (2, 83, 0),
    "location": "View3D > Object > Align Buildings",
    "description": "Aligns buildings to SRTM terrain mesh using lowest vertex",
    "category": "Object",
}

import bpy
import bmesh
import mathutils
from mathutils.bvhtree import BVHTree
import logging

logger = logging.getLogger("AlignBuildings")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class OBJECT_OT_align_buildings_lowest(bpy.types.Operator):
    bl_idname = "object.align_buildings_lowest"
    bl_label = "Align Buildings (Lowest Vertex)"
    bl_options = {'REGISTER', 'UNDO'}

    terrain_name: bpy.props.StringProperty(name="Terrain Object")
    buildings_collection: bpy.props.StringProperty(name="Buildings Collection")
    offset: bpy.props.FloatProperty(name="Z Offset", default=0.0)

    def execute(self, context):
        terrain = bpy.data.objects.get(self.terrain_name)
        buildings_coll = bpy.data.collections.get(self.buildings_collection)

        if terrain is None:
            self.report({'ERROR'}, f"Terrain object '{self.terrain_name}' not found")
            return {'CANCELLED'}
        if buildings_coll is None:
            self.report({'ERROR'}, f"Buildings collection '{self.buildings_collection}' not found")
            return {'CANCELLED'}

        depsgraph = context.evaluated_depsgraph_get()
        eval_terrain = terrain.evaluated_get(depsgraph)
        mesh = eval_terrain.to_mesh()

        # Triangulate terrain for BVH
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(mesh)
        bm.free()

        # Build BVH
        verts = [v.co.copy() for v in mesh.vertices]
        faces = [p.vertices[:] for p in mesh.polygons]
        bvh = BVHTree.FromPolygons(verts, faces, all_triangles=True)

        def terrain_z_at(x, y):
            origin = mathutils.Vector((x, y, 10000))
            direction = mathutils.Vector((0, 0, -1))
            hit = bvh.ray_cast(origin, direction)
            if hit[0] is None:
                logger.warning(f"No terrain hit at ({x}, {y})")
                return None
            return hit[0].z

        moved_count = 0
        for obj in buildings_coll.objects:
            if obj.type != 'MESH':
                continue
            # Find lowest vertex in world space
            world_verts = [obj.matrix_world @ v.co for v in obj.data.vertices]
            min_vert = min(world_verts, key=lambda v: v.z)
            terrain_z = terrain_z_at(min_vert.x, min_vert.y)
            if terrain_z is not None:
                delta_z = terrain_z - min_vert.z + self.offset
                obj.location.z += delta_z
                logger.info(f"Moved '{obj.name}' by {delta_z:.3f} to match terrain")
                moved_count += 1
            else:
                logger.warning(f"Skipped '{obj.name}' (outside terrain bounds)")

        eval_terrain.to_mesh_clear()
        self.report({'INFO'}, f"Buildings moved: {moved_count}")
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

def menu_func(self, context):
    self.layout.operator(OBJECT_OT_align_buildings_lowest.bl_idname)

def register():
    bpy.utils.register_class(OBJECT_OT_align_buildings_lowest)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_align_buildings_lowest)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()
