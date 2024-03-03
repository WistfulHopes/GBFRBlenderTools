# GBFR Blender Tools
Granblue Fantasy Relink model Importer/Exporter for Blender

# [Download](https://github.com/WistfulHopes/GBFRBlenderTools/releases)

# Requirements
* [Blender](https://www.blender.org/download/)
* [FlatBuffers - Windows.flatc.binary.zip](https://github.com/google/flatbuffers/releases)

# Installation
1. To import the models into blender you need to download and install the [`io_gbfr_blender_tools.zip`](https://github.com/WistfulHopes/GBFRBlenderTools/releases) file.
2. In blender go to `Edit > Preferences`
3. Go to the `Add-ons` tab and hit `Install...` in the top right.
4. Drag in the `io_gbfr_blender_tools.zip` file and install it.
5. Toggle on the checkbox for the addon.
6. In the addon's prefences, set the filepath to the FlatBuffers `flatc.exe` file.
7. Close preferences.

# Usage
* ## Importing
1. **Make sure you have the `.minfo`, `.skeleton`, and `.mmesh` for a model all in the same folder together. Remember, `.mmesh` files are found under `model_streaming/lod0/` They need to all be together in order for the importer to work.**
You can extract models and other files from Granblue Fantasy: Relink using [GBFRDataTools](https://github.com/Nenkai/GBFRDataTools/releases).
2. Go to `File > Import > Granblue Fantasy Relink (.minfo)`
3. Drag in the model's `.minfo` file and press the `Import` button.
4. Done! Some models may fail to import currently, please open an issue to let us know.

* ## Exporting
  ### Warning: Exporting still has some issues and you are likely to encounter many issues.
1. **Make sure you create a folder to export to, and place a copy of the model's original `.minfo` in that folder.
    * Do not place any of the other `.skeleton` or `.mmesh` files in this folder, they will be overridden!
2. Enusre your model is set up according to the [Exporting Checklist](https://github.com/WistfulHopes/GBFRBlenderTools?tab=readme-ov-file#exporting-checklist).
3. Go to `File > Export > Granblue Fantasy Relink (.mmesh)`
4. Name the model to the same name as the `.minfo` (i.e. Should be `pl1400.mmesh` for `pl1400.minfo`)
5. Press the `Export` button and wait.
6. Done! Your exported model's generated `.minfo`, `.mmesh`, and `.skeleton` files can be found in the `_Exported_Minfo` folder created where you exported to.
* ## Exporting Checklist
  This list is subject to change as model exporting changes and is more fully understood.
  * The model must have an armature and a mesh.
  * The model can only have 1 Mesh object, you must join all meshes together.
  * The mesh's material list must be in the same order as it was upon import. If it's out of order, separate by materials and join the meshes one by one in the correct order.
  * The mesh cannot have any vertices with zero vertex group weights assigned to it. Use the `Select Zero Weights` button in the GBFR tool shelf panel to select them. It is up to you to deal with them via weight painting, deleting, etc.
  * The arnature's bone names must match to the GBFR Bone Index names if they are to be animated. Use an original game model to see the naming scheme of humanoid bones (TODO: Create viewable bone name list).
  * The armature must be pointed upwards on the Z-Axis. Remember to `CTRL+A > All Transforms` to apply all transforms on the Armature.

## Discord (EN)
Join the Relink Modding Discord For help, guidance & more!

<a href="https://discord.gg/gbsG4CDsru">
  <img src="https://discordapp.com/api/guilds/1203608338344976434/widget.png?style=banner2" alt="Discord Banner 1"/>
</a>

# Credits
* [@WistfulHopes](https://github.com/WistfulHopes)
* [@AlphaSatanOmega](https://github.com/AlphaSatanOmega)

## Additional Credits: 
* [@WolfieBeat](https://github.com/WolfieBeat) - Select Zero Vertices script
