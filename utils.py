import bpy

def format_exception(exception_string): # raise_noob_readable_exception
	# Prints a much more noticable exception for people to read.
    return f"\n\n==============================\n!!!HEY YOU, READ THIS!!!\n==============================\n{exception_string}"

def utils_set_mode(mode):
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode=mode, toggle=False)

def utils_select_active(obj):
	bpy.context.view_layer.objects.active = obj