# 🌍 Import Real-World Terrain and Buildings into Unity 3D  
**Using BlenderGIS, Blosm, and a Custom Alignment Script**

This guide walks you through importing accurate real-world landscapes and buildings into Unity, using **BlenderGIS**, **Blosm**, and a simple Python script to align buildings perfectly with the terrain.

Requirements: Blender, BlenderGID addon, Blosm Addon (formerly known as blender-osm)

---

## 🧭 Step 1 — Create the Base Map in BlenderGIS

Start with a fresh Blender project.

1. **Open BlenderGIS**  
   Go to:  
   `Web Geodata → Basemap`  
   Choose **Google Mercator**, and zoom in on the location you want to export.  
   Press `Esc` once you’re satisfied with the area.

2. **Get Elevation Data**  
   Click **Get Elevation (SRTM)**.  
   This downloads a terrain mesh with elevation data.

3. **Merge DEM Objects**  
   Select the `srtm` object, then select each child (`DEM`, `DEM.001`, etc.).  
   Press **Ctrl + J** to join them into one object.  
   Your terrain is now one complete mesh.

4. **Export the Terrain**  
   Go to `File → Export → Wavefront (.OBJ)`  
   Save it somewhere handy.

5. **Record the Coordinates**  
   Open `BlenderGIS → Logs`.  
   Scroll down to find the coordinates (N, W, E, S).  
   Write them down — you’ll need these for Blosm.

💾 **Save your project** and close it.

---

## 🏗 Step 2 — Import the Terrain and Buildings via Blosm

Open a **new Blender project**.

1. **Import the SRTM Mesh**  
   Go to `File → Import → Wavefront (.OBJ)`  
   Import the terrain you exported earlier.

2. **Open the Side Panel**  
   Press **N** to open the right sidebar, then select the **Blosm** tab.

3. **Configure Blosm Import**
   - **Extent:** Paste or manually enter the coordinates from BlenderGIS logs.  
     (N, W, E, S)
   - **Import Source:** `Server` (no `.OSM` file needed)
   - **Terrain:** Select your imported `srtm` mesh.
   - **Objects:** Check all layers you want (buildings, roads, etc.)
   - **Roof Shape:** Choose your preferred style.
   - **Options:**  
     - Uncheck **Import as single object** (we want multiple).  
     - Check **Relative to initial import**.

4. **Import!**  
   Click the **Import** button.  
   Blosm fetches the OSM data and places it relative to your SRTM mesh.

> 🧩 **Note:** Blosm doesn’t yet perfectly align buildings to the terrain — we’ll fix that next.

---

## 🧠 Step 3 — Align Buildings to Terrain with a Custom Script

Now we’ll use a Blender add-on to automatically set all buildings to their correct terrain height.

1. **Install the Script**
   - Go to `Edit → Preferences → Add-ons → Install`
   - Select your file:  
     `Align_Buildings_to_Terrain.py`
   - Enable the add-on.

2. **Run the Script**
   - In **Object Mode**, select all your buildings.
   - Go to `Object → Align Buildings to Terrain`
   - The script now adjusts every building’s Z-position to match the terrain beneath it.

> 🪄 **Tip:** The script even includes a configurable *offset*, so you can make buildings “sink” slightly into the terrain for a snug fit.

---

## 🧱 Step 4 — Export to Unity 3D

Finally, let’s bring it into Unity.

1. Go to `File → Export → FBX (.fbx)`
2. Use these settings:

| Setting | Value |
|----------|--------|
| **Path Mode** | Copy *(click the small file icon beside it)* |
| **Selected Objects** | ✅ Checked |
| **Apply Transform** | ✅ Checked |
| **Apply Scalings** | FBX All |
| **Geometry → Smoothing** | Face |
| **Apply Modifiers** | ✅ Checked |

Click **Export FBX** — done!

---

## 🚀 Step 5 — Import into Unity

1. Drag your `.fbx` into Unity’s **Assets** folder.  
2. Place it in the scene — your terrain and buildings should align perfectly.  
3. Adjust materials, add textures, and enjoy your realistic 3D map!

---

## ✅ Summary

You’ve just built a complete **real-world terrain and building pipeline** from BlenderGIS → Blosm → Unity, including:
- Accurate **SRTM elevation data**  
- Real **OpenStreetMap buildings**  
- Perfect **terrain alignment** with a Python helper script  
- Clean **FBX export** ready for Unity  

---

## 💡 Bonus Tips

- To make the terrain more lightweight, use the **Decimate Modifier** in Blender.  
- If you want better lighting, bake **Ambient Occlusion** before exporting.  
- For larger scenes, split imports into multiple tiles to manage performance.

---
