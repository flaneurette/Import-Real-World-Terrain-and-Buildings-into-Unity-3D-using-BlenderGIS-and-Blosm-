bl_info = {
    "name": "Export Terrain Heightmap (Fixed)",
    "author": "ChatGPT",
    "version": (1, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Object > Export Heightmap",
    "description": "Export selected mesh as a normalized heightmap PNG for GIS",
    "category": "Import-Export",
}

import bpy
import numpy as np
from bpy.props import IntProperty, StringProperty
from bpy.types import Operator

class EXPORT_OT_heightmap_fixed(Operator):
    bl_idname = "export.heightmap_fixed"
    bl_label = "Export Heightmap (Fixed)"
    bl_options = {'REGISTER', 'UNDO'}

    resolution: IntProperty(
        name="Resolution",
        default=512,
        min=16,
        max=4096
    )

    filepath: StringProperty(
        name="File Path",
        default="C:/Users/Gebruiker/Desktop/heightmap.png",
        subtype='FILE_PATH'
    )

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object")
            return {'CANCELLED'}

        mesh = obj.data
        coords = [v.co for v in mesh.vertices]

        # Z bounds
        zs = [v.z for v in coords]
        min_z = min(zs)
        max_z = max(zs)
        if max_z - min_z < 1e-6:
            self.report({'ERROR'}, "Mesh has almost no height difference")
            return {'CANCELLED'}

        # grid
        xs = np.linspace(min(v.x for v in coords), max(v.x for v in coords), self.resolution)
        ys = np.linspace(min(v.y for v in coords), max(v.y for v in coords), self.resolution)
        zz = np.zeros((self.resolution, self.resolution), dtype=np.float32)

        # sample nearest vertex
        for i, y in enumerate(ys):
            for j, x in enumerate(xs):
                closest = min(coords, key=lambda v: (v.x - x)**2 + (v.y - y)**2)
                zz[i, j] = closest.z

        # normalize 0-1 and flip vertically for GIS
        zz_norm = (zz - min_z) / (max_z - min_z)
        zz_norm = np.flipud(zz_norm)

        # convert to 8-bit image
        zz_img = (zz_norm * 255).astype(np.uint8)

        # create Blender image
        img = bpy.data.images.new("Heightmap", width=self.resolution, height=self.resolution)
        pixels = []
        for row in zz_img:
            for val in row:
                pixels.extend([val / 255, val / 255, val / 255, 1.0])  # RGBA
        img.pixels = pixels

        # ensure folder exists
        import os
        folder = os.path.dirname(self.filepath)
        if not os.path.exists(folder):
            os.makedirs(folder)

        img.filepath_raw = self.filepath
        img.file_format = 'PNG'
        img.save()

        self.report({'INFO'}, f"Heightmap saved: {self.filepath}")
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(EXPORT_OT_heightmap_fixed.bl_idname)

def register():
    bpy.utils.register_class(EXPORT_OT_heightmap_fixed)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(EXPORT_OT_heightmap_fixed)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()
