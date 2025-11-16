from pathlib import Path



class VMDLGenerator:
    def __init__(self, config):
        self.config = config

    def generate(self, fbx_path, model_data, vmat_path, work_dirs):
        print(f"Генерация .vmdl модели для: {fbx_path.name}")

        model_name = fbx_path.stem
        vmdl_content = self.create_vmdl_content(model_name, model_data, vmat_path)
        vmdl_path = work_dirs['output'] / f"{model_name}.vmdl"

        with open(vmdl_path, 'w', encoding='utf-8') as f:
            f.write(vmdl_content)

        print(f".vmdl файл создан: {vmdl_path.name}")
        return vmdl_path

    def create_vmdl_content(self, model_name, model_data, vmat_path):
        content = "<!-- kv3 encoding:text:version{e21c7f3c-8a33-41c5-9977-a76d3a32aa0d} format:generic:version{7412167c-06e9-4698-aff2-e63eb59037e7} -->\n"
        content += "{\n"
        content += self.generate_render_mesh_list(model_data, model_name)
        content += self.generate_physics_shape_list(model_data)
        content += self.generate_game_data_list()
        content += self.generate_material_section(vmat_path)
        content += self.generate_scale_section(model_data)

        content += "}\n"
        return content

    def generate_render_mesh_list(self, model_data, model_name):
        section = '\tRenderMeshList = \n\t[\n'

        if model_data.get('lod_files'):
            for i, lod_path in enumerate(model_data['lod_files']):
                relative_path = self.make_relative_path(lod_path)
                section += f'\t\t// LOD Level {i}\n'
                section += f'\t\t{{\n'
                section += f'\t\t\tMesh = "{relative_path}"\n'
                section += f'\t\t\tLOD = {i}\n'
                section += f'\t\t}},\n'
        else:
            relative_path = f"./{model_name}_LOD0.fbx"
            section += f'\t\t{{\n'
            section += f'\t\t\tMesh = "{relative_path}"\n'
            section += f'\t\t\tLOD = 0\n'
            section += f'\t\t}},\n'

        section += '\t]\n'
        return section

    def generate_physics_shape_list(self, model_data):
        section = '\tPhysicsShapeList = \n\t[\n'

        if model_data.get('physics_file'):
            physics_path = self.make_relative_path(model_data['physics_file'])
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

    def generate_material_section(self, vmat_path):
        if vmat_path:
            relative_path = self.make_relative_path(vmat_path)
            section = f'\tDefaultMaterialGroup = "{relative_path}"\n'
        else:
            section = '\tDefaultMaterialGroup = "materials/default.vmat"\n'
        return section

    def generate_scale_section(self, model_data):
        applied_scale = model_data.get('scale_applied', 1.0)
        section = f'\t// Масштаб применен при конвертации: {applied_scale}\n'
        section += f'\tScale = {applied_scale}\n'
        return section

    def make_relative_path(self, file_path):
        if isinstance(file_path, Path):
            return f"./{file_path.name}"
        return f"./{Path(file_path).name}"