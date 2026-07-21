<h1 align="center">GBFR Blender Tools</h1>
<h3 align="center">An Addon for Blender for Importing/Exporting and Working with Models from Granblue Fantasy: Relink</h3>

<h1 align="center"><a href="https://github.com/WistfulHopes/GBFRBlenderTools/releases/latest/download/io_gbfr_blender_tools.zip">Download</a></h1>

---

# Requirements
* [Blender (3.5 or Higher)](https://www.blender.org/download/)
* [FlatBuffers - Windows.flatc.binary.zip](https://github.com/google/flatbuffers/releases)

# Installation
1. To import the models into blender you need to download and install the [`io_gbfr_blender_tools.zip`](https://github.com/WistfulHopes/GBFRBlenderTools/releases) file.
2. In blender go to `Edit > Preferences`
3. Go to the `Add-ons` tab and hit `Install...` in the top right.
4. Drag in the `io_gbfr_blender_tools.zip` file and install it.
5. Toggle on the checkbox for the addon.
  5a. In the addon's prefences, set the filepath to the folder where you extracted the game's data to.
6. Close preferences.

---
# Usage
  ## Importing
  1. Extract/Locate the model's `.minfo` file (plus the `.skeleton` file if it has one) from the model folder, and the `.mmesh` files from each `model_streaming/lod#` folder.
> [!IMPORTANT]
> You can extract models and other files from Granblue Fantasy: Relink using [GBFRDataTools](https://github.com/Nenkai/GBFRDataTools/releases).
> To learn how to extract files go to: [Granblue Fantasy - Relink Modding](https://nenkai.github.io/relink-modding/tutorials/file_extraction/)
  2. Go to `File > Import > Granblue Fantasy Relink (.minfo)`
  3. Drag in the model's `.minfo` file and press the `Select .minfo` button.
  4. You will then be prompted to locate and enter the `model_streaming` folder where the `lod#` & `shadowlod#` folders are.
     Once there, press the `Auto-Select .mmesh Folder(s)` button to import the model with the selected LODs.
     1. Using the ☑️ checkboxes on the right you can select the LODs you wish to import.
  5. Done!
> [!WARNING]
> Some models may fail to import currently, please open an issue to let us know.

  ## Exporting
  1. **Make sure you create a folder to export to, exporting to the same folder as the orignal files my overwite them!**
  2. Ensure your model is set up according to the [Exporting Checklist](https://github.com/WistfulHopes/GBFRBlenderTools?tab=readme-ov-file#exporting-checklist).
  3. Go to `File > Export > Granblue Fantasy Relink (.mmesh)`
  4. Specify an export name. This should be the same name as the original `.minfo` (i.e. Should be `pl1400.mmesh` for `pl1400.minfo`)
  5. (Optional) Press the `Create model/model_streaming Folder` checkbox on the right if your exported files in folders that mimic the game's data folder structure. 
    Useful for easy drag & drop to create/update mods!
  6. Press the `Export` button and wait.
  7. Done! Your exported model's generated `.minfo`, `.skeleton`, and `.mmesh` files can be found in the folder created where you exported to.
> [!WARNING]
> Please open an issue to let us know of any errors encountered during export.

  ## Exporting Checklist
> [!NOTE]
> This list is subject to change as model exporting changes and is more fully understood.
  * The model hierarchy must be structured like so:
    ```
    -> Root - An Armature or Empty
      -> lod# - Empty only, where `#` is a number from `0-3`
        -> Mesh - Can be any number of these under `lod#`
    ```
    Example:
    <br><img width="234" height="244" alt="image" src="https://github.com/user-attachments/assets/debef38a-7dfb-4502-bc61-51f86725d234" /> 
  * Each material must be assigned a material index using the addon's [Tool Shelf Panel](https://github.com/WistfulHopes/GBFRBlenderTools/blob/main/README.md#tool-shelf). These indices correspond with the materials list found in the model's `.mmat` files.
  * A mesh attached to a model with an armature needs to have at least 1 Vertex Group (no vertices need to be assigned).
  * Each vertex on a mesh can only be assigned up to 8 vertex groups. Use the `Limit & Normalize Weights` in the GBFR Panel to limit them.
  * The armature's bone names must match to the GBFR Bone Index names if they are to be animated. Use an original game model to see the naming scheme of humanoid bones.
  * All objects on the model must be pointed upwards on the Z-Axis, otherwise elements of the model may be rotated incorrectly. Remember to `CTRL+A > All Transforms` to apply all transforms for all objects on the model.
  * Models can have a maximum of 2 UV Maps.
  * Models can have 1 set of Vertex Colors.
  * Bone collection/group names can only contain alphanumeric characters, no special characters (i.e. Japanese characters)

  ## Tool Shelf 
  ### (Press `N` in the `3D View` to open the tool shelf, then click the `GBFR` Tab)
  * `Split Mesh along UVs`: Prevents the textures from looking warped in areas on export. (Makes sure to separate vertices that are shared among 2 separate UV islands).
  * `Limit & Normalize Weights`: Limits all vertex weights to 4/8 groups and normalizes them.
  * `Remove Unused Vertex Groups`: Removes any vertex groups that lack a corresponding bone.
  * `Translate Bones`: Allows you to switch between the GBFR bone names and Unity/Blender standard bone names.
  * `Separate by Materials`: Separates the selected meshes into several meshes, one for each material. Also renames them to the material names.
  * `Join all meshes`: Joins all the meshes under the same parent into 1 mesh.
  * `Select Zero Weight Vertices`: Selects all vertices that are not connected to any bones. Exporting with 0 weight vertices may cause issue, so this prevents this highlights the unweighted vertices for you to deal with.
  * `Flip Normals`: Flips the facing of selected geometry in edit mode, so if the model appears inside out, you can flip the facing so it's right-side out.
  * `Remove Doubles`: Joins vertices that are very close together but not joined.
  
  * `Materials Section`: Use this section to set the material indices of the materials that will correlate with the materials listed in the `.mmat`s.
  
  * `Advanced Section`: Use this section to edit miscellaneous properties of the `.minfo`
    * `LOD Screen Size Thresholds`: The minimum vertical % of the screen of which the model must take up in order to swap to to the corresponding LOD model. The order is `lod0`,`lod1`,`lod2`,`lod3`
    * `Fade between LODs`: Whether to fade between LOD changes or not.
    * `Near Camera Bound Radius`:
    * `Near Camera Detection Scale`:
    * `Fade Out Distance`: Distance at which the object starts fading out for the camera.
    * `Use Bone Bounds for Fade`:
    * `Camera Near Fade aabb Radius`:
    * `Minimum Screen % Render Thresholds`: The minimum vertical % of the screen different parts of the model must take up in order to render.
      * `Min. Mesh Screen Size`: The main model
      * `Min. Shadow Screen Size`: The shadow cast by the model
      * `Min. Outline Screen Size`: The outline on the model

---

## Discord (EN)
Join the Relink Modding Discord For help, guidance & more!

<a href="https://discord.gg/gbsG4CDsru">
  <img src="https://discordapp.com/api/guilds/1203608338344976434/widget.png?style=banner2" alt="Discord Banner 1"/>
</a>

# Credits
* [@WistfulHopes](https://github.com/WistfulHopes) - Initial Plugin creation and Model reverse engineering   <a href="https://ko-fi.com/wistfulhopes" width="40%"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support WistfulHopes on Ko-Fi"></a>
* [@AlphaSatanOmega](https://github.com/AlphaSatanOmega) - Plugin updates and maintenance   <a href="https://ko-fi.com/alphasatanomega" width="40%"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support AlphaSatanOmega on Ko-Fi"></a>

## Additional Credits:
* [@Nenkai](https://github.com/Nenkai) - Reverse Engineering, Documenting, and so much more 💚   <a href="https://ko-fi.com/nenkai" width="40%"><img src="https://ko-fi.com/img/githubbutton_sm.svg" alt="Support Nenkai on Ko-Fi"></a>
* [@WolfieBeat](https://github.com/WolfieBeat) - Select Zero Weight Vertices script
* [@bujyu-uo](https://github.com/bujyu-uo) - Bone Collection importing
* [@rurires](https://github.com/rurires) - Miscellaneous export fixes
