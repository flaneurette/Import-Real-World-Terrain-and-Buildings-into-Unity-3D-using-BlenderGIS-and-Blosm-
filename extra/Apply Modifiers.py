bl_info = {
    "name": "Apply All Modifiers (Optimized)",
    "blender": (2, 83, 0),
    "category": "Object",
    "author": "Your Name",
    "description": "Apply all modifiers on all objects efficiently, handling special cases.",
    "version": (1, 0, 0),
    "support": "COMMUNITY",
}

import bpy
import time

# Optimized function to apply all modifiers to all objects in the scene
class OBJECT_OT_apply_all_modifiers(bpy.types.Operator):
    bl_idname = "object.apply_all_modifiers"
    bl_label = "Apply All Modifiers (Optimized)"
    bl_options = {'REGISTER', 'UNDO'}

    # Batch size for processing to avoid Blender lock-up
    batch_size = 10

    def execute(self, context):
        # Track number of objects processed for feedback
        processed_count = 0
        start_time = time.time()

        # List to store objects to be processed
        objects_to_process = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH' and obj.modifiers]

        # Log how many objects to process
        print(f"Starting batch processing of {len(objects_to_process)} objects.")

        # Process objects in batches
        for i, obj in enumerate(objects_to_process):
            # Ensure we don't lock up Blender
            if i % self.batch_size == 0 and i > 0:
                print(f"Processed {i} objects. Taking a break...")  # Log progress
                time.sleep(0.1)  # Allow Blender to update the UI

            # Apply modifiers for each object
            for mod in obj.modifiers:
                try:
                    # Handle special cases for modifiers like Boolean and Shrinkwrap
                    if mod.type == 'BOOLEAN' or mod.type == 'SHRINKWRAP':
                        # Apply via bpy.ops.object.modifier_apply() for Boolean and Shrinkwrap
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.modifier_apply(modifier=mod.name)
                        processed_count += 1
                except Exception as e:
                    # Log the error if a modifier can't be applied
                    print(f"Failed to apply modifier '{mod.name}' on '{obj.name}': {e}")
                    self.report({'ERROR'}, f"Failed to apply modifier '{mod.name}' on '{obj.name}': {e}")

        # Log the total time taken
        elapsed_time = time.time() - start_time
        print(f"Batch processing completed. Total modifiers applied: {processed_count}")
        print(f"Elapsed time: {elapsed_time:.2f} seconds.")

        self.report({'INFO'}, f"Applied {processed_count} modifiers. Time taken: {elapsed_time:.2f} seconds.")
        return {'FINISHED'}

# Add the operator to the Object menu
def menu_func(self, context):
    self.layout.operator(OBJECT_OT_apply_all_modifiers.bl_idname)

# Register and unregister functions
def register():
    bpy.utils.register_class(OBJECT_OT_apply_all_modifiers)
    bpy.types.VIEW3D_MT_object.append(menu_func)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_apply_all_modifiers)
    bpy.types.VIEW3D_MT_object.remove(menu_func)

if __name__ == "__main__":
    register()
