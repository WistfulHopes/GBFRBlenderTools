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
## Importing
1. **Make sure you have the `.minfo`, `.skeleton`, and `.mmesh` for a model all in the same folder together. Remember, `.mmesh` files are found under `model_streaming/lod0/` They need to all be together in order for the importer to work.**
You can extract models and other files from Granblue Fantasy: Relink using [GBFRDataTools](https://github.com/Nenkai/GBFRDataTools/releases)
2. Go to `File > Import > Granblue Fantasy Relink (.minfo)
3. Drag in the model's `.minfo` file and press import.
4. Done! Some models may fail to import currently, please open an issue to let us know.

## Exporting

# Credits
* [@WistfulHopes](https://github.com/WistfulHopes)
* [@AlphaSatanOmega](https://github.com/AlphaSatanOmega)

## Additional Credits: 
* [@WolfieBeat](https://github.com/WolfieBeat) - Select Zero Vertices script
