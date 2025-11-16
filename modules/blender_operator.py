import subprocess
import json
from pathlib import Path


class BlenderOperator:
    def __init__(self, config):
        self.config = config
        print(config['global_settings']['paths']['blender'])
        self.blender_path = "C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe"

    def process_model(self, fbx_path, work_dirs):
        print(f"Обработка геометрии в Blender: {fbx_path.name}")
        output_dir = Path(work_dirs.get('model_output', work_dirs['output'])).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        blender_script = self.generate_blender_script(fbx_path, output_dir)
        script_path = work_dirs['temp'] / "blender_processor.py"

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(blender_script)

        try:
            cmd = [
                self.blender_path,
                '--background',
                '--python', str(script_path),
                '--factory-startup'
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                encoding='utf-8',
                errors='ignore'
            )

            if result.returncode == 0:
                print("Обработка в Blender завершена успешно")
                return self.get_processed_data(fbx_path, output_dir)
            else:
                print(f"Ошибка Blender: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("Таймаут обработки в Blender")
            return None
        except Exception as e:
            print(f"Ошибка запуска Blender: {e}")
            return None

    def generate_blender_script(self, fbx_path, output_dir):
        lod_levels = self.config['lod']['levels']
        global_scale = self.config['global_settings']['global_scale']
        physics_ratio = self.config['physics']['decimation_ratio']

        model_name = fbx_path.stem
        base_output_path = (output_dir / model_name).resolve()
        base_output_str = str(base_output_path).replace('\\', '/')
        fbx_path_str = str(fbx_path.resolve()).replace('\\', '/')

        script = f"""
import bpy
import bmesh
from mathutils import Vector
import os

bpy.ops.wm.read_factory_settings(use_empty=True)

print("Импорт FBX...")
bpy.ops.import_scene.fbx(filepath=r"{fbx_path_str}")

print("Применение масштаба...")
for obj in bpy.context.scene.objects:
    obj.scale = Vector(({global_scale}, {global_scale}, {global_scale}))

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
if not mesh_objects:
    raise Exception("Не найдены меши в импортированном файле")

main_object = mesh_objects[0]
bpy.context.view_layer.objects.active = main_object

lod_files = []
lod_levels = {lod_levels}

print("Генерация LOD...")
for i, ratio in enumerate(lod_levels):
    bpy.ops.object.select_all(action='DESELECT')
    main_object.select_set(True)
    bpy.context.view_layer.objects.active = main_object
    bpy.ops.object.duplicate()

    lod_object = bpy.context.active_object
    lod_object.name = f"{{main_object.name}}_LOD{{i}}"

    if ratio < 1.0:
        decimate = lod_object.modifiers.new(name="Decimate", type='DECIMATE')
        decimate.ratio = ratio
        bpy.ops.object.modifier_apply(modifier=decimate.name)

    lod_suffix = "" if i == 0 else "_LOD" + str(i)
    lod_path = r"{base_output_str}" + lod_suffix + ".fbx"
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
    print(f"LOD{{i}} сохранен: {{lod_path}}")

    bpy.ops.object.delete()

print("Генерация коллизии...")
bpy.ops.object.select_all(action='DESELECT')
main_object.select_set(True)
bpy.context.view_layer.objects.active = main_object
bpy.ops.object.duplicate()

physics_object = bpy.context.active_object
physics_object.name = f"{{main_object.name}}_physics"

decimate = physics_object.modifiers.new(name="Decimate", type='DECIMATE')
decimate.ratio = {physics_ratio}
bpy.ops.object.modifier_apply(modifier=decimate.name)

physics_path = r"{base_output_str}_physics.fbx"
bpy.ops.object.select_all(action='DESELECT')
physics_object.select_set(True)
bpy.context.view_layer.objects.active = physics_object

bpy.ops.export_scene.fbx(
    filepath=physics_path,
    use_selection=True,
    apply_scale_options='FBX_SCALE_ALL',
    mesh_smooth_type='EDGE'
)

print(f"Коллизия сохранена: {{physics_path}}")

import json
result_data = {{
    'lod_files': lod_files,
    'physics_file': physics_path,
    'original_file': r"{fbx_path_str}",
    'scale_applied': {global_scale}
}}

info_path = r"{base_output_str}_processing_info.json"
with open(info_path, 'w') as f:
    json.dump(result_data, f, indent=2)

print("Обработка завершена!")
"""

        return script

    def get_processed_data(self, fbx_path, output_dir):
        info_path = output_dir / f"{fbx_path.stem}_processing_info.json"
        try:
            with open(info_path, 'r') as f:
                return json.load(f)
        except:
            return {
                'lod_files': [],
                'physics_file': None,
                'scale_applied': self.config['global_settings']['global_scale']
            }