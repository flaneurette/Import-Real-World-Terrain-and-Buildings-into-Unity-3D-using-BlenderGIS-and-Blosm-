# Carving Out Waterways

This guide walks you through the process of carving out waterways such as rivers, lakes, and ponds to create realistic depth in your terrain. Since SRTM data lacks bathymetric information for waterways, we can manually carve them to enhance realism.

### Requirements:
- Blender (version 2.83 or later)
- `Water_Carver.py` script

---

## Step 1 - Install the Water_Carver Addon

Before you start carving, ensure that your data is processed as outlined in the earlier sections of the README. This should be the second step in your process.

1. **Install the Addon**  
   - Open Blender and go to:  
     `Edit → Preferences → Add-ons`  
   - Click the **Install** button, and select the `Water_Carver.py` script.  
   - Once installed, make sure to check the box next to the addon to activate it.

2. **Carve Waterways**  
   - In Blender, **do not** select any object. It’s best to select the **Scene Collection** instead.  
   - Switch to **Object Mode** and click the **Object** button.  
   - You will see the addon appear in the dialogue below. Click it to start the process.

3. **Water Carver Popup**  
   - A popup will appear. In this window, you’ll need to:
     - Select the **SRTM** by name.
     - Select the **Waterway Object** by name.
     - Set the **depth** for both layers (ensure the SRTM layer has enough depth to carve).
   - Press **Carve** and wait for the process to complete. If you encounter any jagged polygons, it means the operation failed. Simply press `Ctrl + Z` to undo and try again.
   
   Your waterway will now be carved into the SRTM mesh!

---

### Tips:
- Ensure the SRTM layer has enough depth to allow proper carving.
- Always make a backup of your project before performing destructive operations like carving.
