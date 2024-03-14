import os
import subprocess
import re
import json
import sys
import shutil
import copy
import time
# GBFR Blender .json export to .minfo converter
# Version 3.0
# By AlphaSatanOmega - https://github.com/AlphaSatanOmega
# Drag and drop the original .minfo and the Blender export .json onto this .py file

# Convert flatc json data string to proper json data string with quotes
def preprocess_flatbuffers_json(json_data):
    return re.sub(r'(\w+)(?=\s*:)', r'"\1"', json_data) # Use regular expression to wrap field names in quotes

def replace_mesh_info(flatc_json, blender_json, magic = None):
    # Load json data from files
    flatc_json_data = json.loads(flatc_json)
    blender_json_data = json.loads(blender_json)

    if magic: # Overwrite magic if number provided
        flatc_json_data["magic"] = magic

    # Replace the mesh info in the flatc json with the mesh info from the blender export json
    keys_to_replace = ["mesh_buffers", "chunks", "vertex_count", "poly_count_x3", "buffer_types"]
    for lod_index in range(len(flatc_json_data["lods"])):
        for key in keys_to_replace:
            flatc_json_data["lods"][lod_index][key] = blender_json_data[key]
    # Just set the lods array to contain the Highest LOD
    flatc_json_data["lods"] = [flatc_json_data["lods"][0]]

    # Replace the bones_to_weight_indices list with the blender export list
    flatc_json_data["bones_to_weight_indices"] = blender_json_data["bones_to_weight_indices"]

    # Replace Sub meshes
    flatc_json_data["sub_meshes"] = blender_json_data["sub_meshes"]

    """
    # Get submesh names
    blender_json_submesh_names = blender_json_data["SubMeshes"]
    flatc_json_submesh_names = []
    for flatc_submesh in flatc_json_data["SubMeshes"]:
        flatc_json_submesh_names.append(flatc_submesh["Name"])
    # If a submesh name from blender is not in the flatc submeshes, 
    # duplicate the last submesh and change its name to match
    for blender_submesh_name in blender_json_submesh_names:
        if blender_submesh_name not in flatc_json_submesh_names:
            new_submesh = copy.deepcopy(flatc_json_data["SubMeshes"][-1])
            new_submesh["Name"] = blender_submesh_name
            flatc_json_data["SubMeshes"].append(new_submesh)
    """

    return json.dumps(flatc_json_data, indent=2) # Convert and return

def convert_minfo(flatc_path, minfo_path, blender_json_path, magic = None):
    print ("Start MInfo Conversion.")
    
    if os.path.dirname(minfo_path) != os.path.dirname(blender_json_path):
        raise Exception("\n\nERROR: A copy of the .minfo needs to be in same location as you are exporting to.")
    
    script_dir = os.path.dirname(__file__) # Get the script directory
    export_dir = os.path.dirname(blender_json_path) # Get blender export directory
    flatc_temp_dir = os.path.join(export_dir, "_flatc_temp")
    minfo_fbs_path = os.path.join(script_dir,"MInfo_ModelInfo.fbs") # Get the FlatBuffers Schema
#    flatc_path = os.path.join(script_dir, "flatc.exe") # Get the path to flatc.exe in the same directory
    model_name = os.path.splitext(os.path.basename(minfo_path))[0] # Get the model name from the minfo
    
    # Generate json from .minfo file using flatc.exe

    print(flatc_path, "-o", f"{flatc_temp_dir}", "--json", f"{minfo_fbs_path}", "--", f"{minfo_path}", "--raw-binary")
    
    command = [flatc_path, "-o", f"{flatc_temp_dir}", "--json", f"{minfo_fbs_path}", "--", f"{minfo_path}", "--raw-binary", "--no-warnings"]
    subprocess.run(command, check=True)
    # flatc json gets stored to a temp folder
    flatc_json_path = os.path.join(flatc_temp_dir, f"{model_name}.json") 
    print(f"Generated: {flatc_json_path}")
    
    # Open the json files
    with open(flatc_json_path, 'r') as flatc_file, open(blender_json_path, 'r') as blender_file:
        flatc_json = flatc_file.read()
        blender_json = blender_file.read()
        flatc_json = preprocess_flatbuffers_json(flatc_json) # Fix flatc json
        
    # Replace the mesh info of flatc json with blender export json's mesh info
    modified_flatc_json = replace_mesh_info(flatc_json, blender_json, magic)
    # print(modified_flatc_json)
    # Save modified flatc to a file in the same directory as the script
    # os.path.join(export_dir, f"{model_name}.json")
    modified_flatc_json_file = blender_json_path # Overwrite blender json file
    with open(modified_flatc_json_file, 'w') as file:
        file.write(modified_flatc_json)
    print(f"Replaced mesh info in {flatc_json_path} with mesh info from {minfo_path}")

    # Create output directory next to original .minfo
    output_dir = os.path.join(os.path.dirname(minfo_path), "_Exported_MInfo")
    os.makedirs(output_dir, exist_ok=True)

    # Run flatc.exe to generate binary minfo from the modified json
    command = [flatc_path, "-o", f"{flatc_temp_dir}", "--binary", f"{minfo_fbs_path}", modified_flatc_json_file, "--no-warnings"]
    subprocess.run(command, check=True)
    # Rename the .bin otuput to .minfo
    binary_output_file = os.path.join(flatc_temp_dir, f"{model_name}.bin")
    minfo_output_file = binary_output_file.replace(".bin", '.minfo')
    os.rename(binary_output_file, minfo_output_file)
    print(f"Modified {minfo_output_file} generated.")
    # Move minfo to output_dir
    try: os.remove(os.path.join(output_dir, f"{model_name}.minfo")) # Remove copy if exists
    except: print(f"No copy of {model_name}.minfo found in {output_dir}, moving.")
    shutil.move(minfo_output_file, output_dir)
    
    # Move all the Blender export files into the output_dir
    blender_export_file_exts = [".mmesh", ".skeleton", ".json"]
    for file_ext in blender_export_file_exts:
        original_file_path = os.path.join(export_dir, f"{model_name}{file_ext}")
        try: os.remove(os.path.join(output_dir, f"{model_name}{file_ext}")) # Remove copy if exists
        except Exception as e: 
            print(str(e))
            print(f"No copy of {model_name}{file_ext} found in {output_dir}, moving.")
        shutil.move(original_file_path, output_dir)
        
    # Remove _flatc_temp safely
    os.remove(os.path.join(flatc_temp_dir, f"{model_name}.json")) # Remove json first
    os.rmdir(flatc_temp_dir) # Then delete the folder since it should be empty, fails otherwise
    print(f"Removed {flatc_temp_dir}")
    
    print(f"Modified JSON and binary files moved to: {output_dir}")


def main():
    input_file_1 = sys.argv[1]
    input_file_2 = sys.argv[2]
    # Check which file is the .minfo and which is the .json
    if input_file_1.lower().endswith('.minfo') and input_file_2.lower().endswith('.json'):
        minfo_path = input_file_1
        blender_json_path = input_file_2
    elif input_file_1.lower().endswith('.json') and input_file_2.lower().endswith('.minfo'):
        minfo_path = input_file_2
        blender_json_path = input_file_1
    else:
        print("Error: Incorrect files input. The inputs should be an .minfo and a .json file.")
    # print(minfo_path, blender_json_path)

    # Process the files
    try:
        convert_minfo(minfo_path, blender_json_path)
        print("\nConversion Complete!")
    except Exception as e:
        print(str(e))

if __name__ == "__main__":
    main()
    input("\nPress any key to exit...")