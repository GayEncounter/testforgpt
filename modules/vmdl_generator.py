import os
from pathlib import Path


class VMDLGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, fbx_path, model_data, vmat_path, work_dirs):
        print(f"Генерация .vmdl модели для: {fbx_path.name}")

        model_name = fbx_path.stem
        output_dir = Path(work_dirs.get('model_output', work_dirs['output'])).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        vmdl_content = self.create_vmdl_content(model_name, model_data, vmat_path, output_dir)
        vmdl_path = output_dir / f"{model_name}.vmdl"

        with open(vmdl_path, 'w', encoding='utf-8') as f:
            f.write(vmdl_content)

        print(f".vmdl файл создан: {vmdl_path.name}")
        return vmdl_path

    def create_vmdl_content(self, model_name, model_data, vmat_path, output_dir):
        content = "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n"
        content += "{\n"
        content += self.generate_render_mesh_list(model_data, model_name, output_dir)
        content += self.generate_physics_shape_list(model_data, output_dir)
        content += self.generate_game_data_list()
        content += self.generate_material_section(vmat_path, output_dir)
        content += self.generate_scale_section(model_data)

        content += "}\n"
        return content

    def generate_render_mesh_list(self, model_data, model_name, output_dir):
        section = '\tRenderMeshList = \n\t[\n'

        if model_data.get('lod_files'):
            for i, lod_path in enumerate(model_data['lod_files']):
                relative_path = self.make_relative_path(lod_path, output_dir)
                section += f'\t\t// LOD Level {i}\n'
                section += f'\t\t{{\n'
                section += f'\t\t\tMesh = "{relative_path}"\n'
                section += f'\t\t\tLOD = {i}\n'
                section += f'\t\t}},\n'
        else:
            relative_path = f"./{model_name}.fbx"
            section += f'\t\t{{\n'
            section += f'\t\t\tMesh = "{relative_path}"\n'
            section += f'\t\t\tLOD = 0\n'
            section += f'\t\t}},\n'

        section += '\t]\n'
        return section

    def generate_physics_shape_list(self, model_data, output_dir):
        section = '\tPhysicsShapeList = \n\t[\n'

        if model_data.get('physics_file'):
            physics_path = self.make_relative_path(model_data['physics_file'], output_dir)
            section += f'\t\t{{\n'
            section += f'\t\t\tShape = "{physics_path}"\n'
            section += f'\t\t\tPhysicsType = "PhysicsMeshFromRender"\n'
            section += f'\t\t}},\n'
        else:
            section += f'\t\t{{\n'
            section += f'\t\t\tPhysicsType = "PhysicsMeshFromRender"\n'
            section += f'\t\t}},\n'

        section += '\t]\n'
        return section

    def generate_game_data_list(self):
        section = '\tGameDataList = \n\t[\n'
        section += '\t\t{\n'
        section += '\t\t\tGameData = "static_prop"\n'
        section += '\t\t}\n'
        section += '\t]\n'
        return section

    def generate_material_section(self, vmat_path, output_dir):
        if vmat_path:
            relative_path = self.make_relative_path(vmat_path, output_dir)
            section = f'\tDefaultMaterialGroup = "{relative_path}"\n'
        else:
            section = '\tDefaultMaterialGroup = "materials/default.vmat"\n'
        return section

    def generate_scale_section(self, model_data):
        applied_scale = model_data.get('scale_applied', 1.0)
        section = f'\t// Масштаб применен при конвертации: {applied_scale}\n'
        section += f'\tScale = {applied_scale}\n'
        return section

    def make_relative_path(self, file_path, base_dir):
        if not file_path:
            return ""
        file_path = Path(file_path).resolve()
        base_dir = Path(base_dir).resolve()
        try:
            rel_path = file_path.relative_to(base_dir)
        except ValueError:
            rel_path = Path(os.path.relpath(file_path, base_dir))
        normalized = str(rel_path).replace('\\', '/')
        return f"./{normalized}"
