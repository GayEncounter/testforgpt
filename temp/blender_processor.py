
import bpy
import bmesh
from mathutils import Vector
import os

bpy.ops.wm.read_factory_settings(use_empty=True)

print("Импорт FBX...")
bpy.ops.import_scene.fbx(filepath=r"input\meshes\static\alley_props\namoroz_l10_03.fbx")

print("Применение масштаба...")
for obj in bpy.context.scene.objects:
    obj.scale = Vector((0.33, 0.33, 0.33))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
if not mesh_objects:
    raise Exception("Не найдены меши в импортированном файле")

main_object = mesh_objects[0]
bpy.context.view_layer.objects.active = main_object

lod_files = []
lod_levels = [1.0, 0.5, 0.25, 0.1]

print("Генерация LOD...")
for i, ratio in enumerate(lod_levels):
    bpy.ops.object.select_all(action='DESELECT')
    main_object.select_set(True)
    bpy.context.view_layer.objects.active = main_object
    bpy.ops.object.duplicate()

    lod_object = bpy.context.active_object
    lod_object.name = f"{main_object.name}_LOD{i}"

    if ratio < 1.0:
        decimate = lod_object.modifiers.new(name="Decimate", type='DECIMATE')
        decimate.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=decimate.name)

    lod_path = r"output\namoroz_l10_03_LOD{i}.fbx"
    bpy.ops.object.select_all(action='DESELECT')
    lod_object.select_set(True)
    bpy.context.view_layer.objects.active = lod_object

    bpy.ops.export_scene.fbx(
        filepath=lod_path,
        use_selection=True,
        apply_scale_options='FBX_SCALE_ALL',
        mesh_smooth_type='EDGE',
        add_leaf_bones=False,
        use_armature_deform_only=False,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_simplify_factor=1.0,
        path_mode='COPY'
    )

    lod_files.append(lod_path)
    print(f"LOD{i} сохранен: {lod_path}")

    bpy.ops.object.delete()

print("Генерация коллизии...")
bpy.ops.object.select_all(action='DESELECT')
main_object.select_set(True)
bpy.context.view_layer.objects.active = main_object
bpy.ops.object.duplicate()

physics_object = bpy.context.active_object
physics_object.name = f"{main_object.name}_physics"

decimate = physics_object.modifiers.new(name="Decimate", type='DECIMATE')
decimate.ratio = 0.05
bpy.ops.object.modifier_apply(modifier=decimate.name)

physics_path = r"output\namoroz_l10_03_physics.fbx"
bpy.ops.object.select_all(action='DESELECT')
physics_object.select_set(True)
bpy.context.view_layer.objects.active = physics_object

bpy.ops.export_scene.fbx(
    filepath=physics_path,
    use_selection=True,
    apply_scale_options='FBX_SCALE_ALL',
    mesh_smooth_type='EDGE'
)

print(f"Коллизия сохранена: {physics_path}")

import json
result_data = {
    'lod_files': lod_files,
    'physics_file': physics_path,
    'original_file': r"input\meshes\static\alley_props\namoroz_l10_03.fbx",
    'scale_applied': 0.33
}

info_path = r"output\namoroz_l10_03_processing_info.json"
with open(info_path, 'w') as f:
    json.dump(result_data, f, indent=2)

print("Обработка завершена!")
