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
6. In the addon's prefences, set the filepath to the FlatBuffers `flatc.exe` file.
7. Close preferences.

---

# Usage
  ## Importing
  1. **Make sure you have the `.minfo`, `.skeleton`, and `.mmesh` for a model all in the same folder together. Remember, `.mmesh` files are found under `model_streaming/lod0/` They need to all be together in order for the importer to work.**
  You can extract models and other files from Granblue Fantasy: Relink using [GBFRDataTools](https://github.com/Nenkai/GBFRDataTools/releases).
  2. Go to `File > Import > Granblue Fantasy Relink (.minfo)`
  3. Drag in the model's `.minfo` file and press the `Import` button.
  4. Done! Some models may fail to import currently, please open an issue to let us know.

  ## Exporting
  ### Warning: Exporting still has some issues and you are likely to encounter many issues.
  1. **Make sure you create a folder to export to, and place a copy of the model's original `.minfo` in that folder.**
      * **Do not place any of the other `.skeleton` or `.mmesh` files in this folder, they will be overridden!**
  2. Enusre your model is set up according to the [Exporting Checklist](https://github.com/WistfulHopes/GBFRBlenderTools?tab=readme-ov-file#exporting-checklist).
  3. Go to `File > Export > Granblue Fantasy Relink (.mmesh)`
  4. Name the model to the same name as the `.minfo` (i.e. Should be `pl1400.mmesh` for `pl1400.minfo`)
  5. Press the `Export` button and wait.
  6. Done! Your exported model's generated `.minfo`, `.mmesh`, and `.skeleton` files can be found in the `_Exported_Minfo` folder created where you exported to.
  ## Exporting Checklist
  This list is subject to change as model exporting changes and is more fully understood.
  * The model must have an armature and a mesh.
  * The model can only have 1 Mesh object, you must join all meshes together.
  * Each material must be assigned a material index using the addon's [Tool Shelf Panel](https://github.com/WistfulHopes/GBFRBlenderTools/blob/main/README.md#tool-shelf). These indices correspond with the materials list found in the model's `.mmat` files.
  * The mesh cannot have any vertices with zero vertex group weights assigned to it. Use the `Select Zero Weights` button in the GBFR tool shelf panel to select them. It is up to you to deal with them via weight painting, deleting, etc.
  * The arnature's bone names must match to the GBFR Bone Index names if they are to be animated. Use an original game model to see the naming scheme of humanoid bones (TODO: Create viewable bone name list).
  * The armature must be pointed upwards on the Z-Axis. Remember to `CTRL+A > All Transforms` to apply all transforms on the Armature.
  * Models can only have 1 UV Map.
  * The GBFR Model format has a limit of 65535 total vertex group weights. Your model should have a reasonable amount of bones to accomodate this, if not merge the bones down.
  * Bone collection/group names can only contain alphanumeric characters, no special characters (i.e. Japanese characters)

  ## Tool Shelf 
  ### (Press `N` in the `3D View` to open the tool shelf, then click the `GBFR` Tab)
  * `Split Mesh along UVs:` Prevents the textures from looking warped in areas on export. (Makes sure to separate vertices that are shared among 2 separate UV islands).
  * `Sort Materials:` Sorts the order of the materials list so it should be close enough to how they import. Helps with stopping materials from going invisible when out of order.
  * `Limit & Normalize Weights:` Limits all vertex weights to 4 groups and normalizes them.
  * `Translate Bones:` Allows you to switch between the GBFR bone names and Unity/Blender standard bone names.
  * `Separate by Materials:` Separates the model's main mesh into several meshes, one for each material. Also renames them to the material names.
  * `Join all meshes:` Joins all the model's meshes into 1 mesh.
  * `Select Zero Weight Vertices:` Selects all vertices that are not connected to any bones. Exporting with 0 weight vertices fails, so this prevents this highlights the unweighted vertices for you to deal with.
  * `Flip Normals:` Flips the facing of selected geometry in edit mode, so if the model appears inside out, you can flip the facing so it's right-side out.
  * `Remove Doubles:` Joins vertices that are very close together but not joined.
  
  * `Materials Section:` Use this section to set the material indices of the materials that will correlate with the materials listed in the `.mmat`s.

---

## Discord (EN)
Join the Relink Modding Discord For help, guidance & more!

<a href="https://discord.gg/gbsG4CDsru">
  <img src="https://discordapp.com/api/guilds/1203608338344976434/widget.png?style=banner2" alt="Discord Banner 1"/>
</a>

# Credits
* [@WistfulHopes](https://github.com/WistfulHopes)
* [@AlphaSatanOmega](https://github.com/AlphaSatanOmega)

## Additional Credits: 
* [@WolfieBeat](https://github.com/WolfieBeat) - Select Zero Weight Vertices script
* [@bujyu-uo](https://github.com/bujyu-uo) - Bone Collection importing
* [@rurires](https://github.com/rurires) - Miscellaneous export fixes
