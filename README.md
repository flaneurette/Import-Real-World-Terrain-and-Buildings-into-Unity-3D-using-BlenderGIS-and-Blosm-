# Import Real-World Terrain and Buildings into Unity 3D  
**Using BlenderGIS, Blosm, and a Custom Alignment Script**

This guide walks you through importing accurate real-world landscapes and buildings into Unity, using **BlenderGIS**, **Blosm**, and a simple Python script to align buildings perfectly with the terrain.

Requirements: Blender, BlenderGIS addon, Blosm Addon (formerly known as blender-osm) and a OpenTopography API key (= free)

Minimal Blender version: 2.83.0

Credits: 

I wrote the manual and workflow

ChatGPT wrote the Python Script helper. (Heavylifted the proper Ray tracing for me)

Wishing you good luck, because it's not easy!

---

## Step 1 - Create the Base Map in BlenderGIS

Start with a fresh Blender project.

1. **Open BlenderGIS**  
   Go to:  
   `Web Geodata → Basemap`  
   Choose **Google Mercator**, and zoom in on the location you want to export.  
   Press `Esc` once you’re satisfied with the area.

2. **Get Elevation Data**  
   Again, in BlenderGIS: click **Get Elevation (SRTM)**.  
   This downloads a terrain mesh with elevation data.

3. **Merge DEM Objects**  
   Select the `srtm` object, then select each child (`DEM`, `DEM.001`, etc.).  
   Press **Ctrl + J** to join them into one object.  (alternatively: In inspector click Apply, or: click Object -> Join if that didnt work. In any case, there should be only one mesh left!)
   Your terrain is now one complete mesh.

4. **Export the Terrain**  
   With ONLY the srtm mesh selected, go to `File → Export → Wavefront (.OBJ)`  
   Save it somewhere handy.

5. **Record the Coordinates**  
   Open `BlenderGIS → Logs`.  
   Scroll down to find the coordinates (N, W, E, S) in the URL that BlenderGIS fetched. (it's close to the bottom of the log, scrol horizontal to see it)
   Write them down - you’ll need these for Blosm.

**Save your project** and close it.

---

## Step 2 - Import the Terrain and Buildings via Blosm

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

> **Note:** Blosm doesn’t yet perfectly align buildings to the terrain - we’ll fix that next.

---

## Step 3 - Align Buildings to Terrain with a Custom Script

Now we’ll use a Blender add-on to automatically set all buildings to their correct terrain height.

1. **Install the Script**
   - Go to `Edit → Preferences → Add-ons → Install`
   - Select your file:  
     `Align_Buildings_to_Terrain.py`
   - Enable the add-on.

2. **Run the Script**
   - In **Object Mode**, select all your buildings.
   - Go to `Object → Align Buildings to Terrain`
   - In the box: manually type the name of the elevation object: i.e. srtm, and the object containting all building meshes: i.e. map_3.osm_buildings (no extension! just the names so the script knows what the terrain and the where the buildings are!)
   - The script now adjusts every building’s Z-position to match the terrain beneath it.

>  **Tip:** The script even includes a configurable *offset*, so you can make buildings “sink” slightly into the terrain for a snug fit. (I used -0.5 to have a good offset)

---

##  Step 4 - Export to Unity 3D

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

Click **Export FBX** - done!

---

## Step 5 - Import into Unity

1. Drag your `.fbx` into Unity’s **Assets** folder.  
2. Place it in the scene - your terrain and buildings should align perfectly.  
3. Adjust materials, add textures, and enjoy your realistic 3D map!

---

## Optional: Carve deeper waterways!
Now, if you want to carve out waterways deeper and more realistic, you can do that with the other README. There is a seperate README and script, which you can also run if you want to carve deeper wateryways than the SRTM provides (which is rather shallow as the SRTM lacks bathymetric information)

## Summary

You’ve just built a complete **real-world terrain and building pipeline** from BlenderGIS → Blosm → Unity, including:
- Accurate **SRTM elevation data**  
- Real **OpenStreetMap buildings**  
- Perfect **terrain alignment** with a Python helper script  
- Clean **FBX export** ready for Unity  

---

## Bonus Tips

- To make the terrain more lightweight, use the **Decimate Modifier** in Blender.  
- If you want better lighting, bake **Ambient Occlusion** before exporting.  
- For larger scenes, split imports into multiple tiles to manage performance.

---
