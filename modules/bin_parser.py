import struct
from pathlib import Path


class BinParser:
    def __init__(self, config, input_root=None):
        self.config = config
        self.input_root = Path(input_root) if input_root else None

    def parse(self, fbx_path):
        bin_path = self.find_bin_file(fbx_path)
        if not bin_path:
            return None

        print(f"Парсинг .bin файла: {bin_path.name}")

        try:
            with open(bin_path, 'rb') as f:
                data = f.read()
            bin_data = self.decode_bin_structure(data)
            texture_info = self.extract_texture_info(bin_path)
            material_params = self.extract_material_params(bin_data)

            return {
                'textures': texture_info,
                'material_params': material_params,
                'raw_data': bin_data  # Сырые данные для отладки
            }

        except Exception as e:
            print(f"Ошибка парсинга .bin файла: {e}")
            return None

    def find_bin_file(self, fbx_path):
        possible_names = [
            fbx_path.with_suffix('.bin'),
            fbx_path.parent / (fbx_path.stem + '.bin'),
            fbx_path.parent / (fbx_path.stem + '_model.bin'),
        ]

        for bin_path in possible_names:
            if bin_path.exists():
                return bin_path

        texture_dirs = self.discover_texture_directories(fbx_path)
        model_name = fbx_path.stem.lower()

        for tex_dir in texture_dirs:
            match = self.search_texture_bin(tex_dir, model_name)
            if match:
                return match
        return None

    def discover_texture_directories(self, fbx_path):
        texture_dirs = set()
        candidate_names = ['textures', 'texture', 'tex']

        for parent in fbx_path.parents:
            for child in parent.iterdir():
                if child.is_dir() and child.name.lower() in candidate_names:
                    texture_dirs.add(child)

        if self.input_root and self.input_root.exists():
            for child in self.input_root.iterdir():
                if child.is_dir() and child.name.lower() in candidate_names:
                    texture_dirs.add(child)

        return texture_dirs

    def search_texture_bin(self, texture_dir, model_name):
        best_match = None
        best_score = -1
        for bin_path in texture_dir.rglob('*.bin'):
            stem = bin_path.stem.lower()
            if stem == model_name:
                return bin_path
            if model_name in stem:
                score = len(model_name)
            else:
                score = self.partial_match_score(model_name, stem)
            if score > best_score:
                best_match = bin_path
                best_score = score
        return best_match

    def partial_match_score(self, model_name, bin_stem):
        model_parts = [part for part in model_name.replace('-', '_').split('_') if part]
        score = 0
        for part in model_parts:
            if part and part in bin_stem:
                score += len(part)
        return score

    def decode_bin_structure(self, data):
        result = {}

        try:
            offset = 0
            if len(data) >= 4:
                result['magic'] = struct.unpack_from('I', data, offset)[0]
                offset += 4
            texture_paths = self.extract_strings(data)
            result['texture_paths'] = texture_paths
            result['material_params'] = self.parse_material_parameters(data)

        except Exception as e:
            print(f"Ошибка декодирования .bin структуры: {e}")

        return result

    def extract_strings(self, data):
        strings = []
        current_string = ""
        for byte in data:
            if 32 <= byte <= 126:  # Печатные ASCII символы
                current_string += chr(byte)
            else:
                if len(current_string) > 3 and (
                        '/' in current_string or '\\' in current_string or '.' in current_string):
                    strings.append(current_string)
                current_string = ""
        return strings

    def parse_material_parameters(self, data):
        params = {
            'detail_scale': 6.0,  # Значение по умолчанию
            'normal_strength': 1.0,
            'specular_level': 0.5
        }
        try:
            for i in range(len(data) - 4):
                value = struct.unpack_from('f', data, i)[0]
                if 0.1 <= value <= 20.0:
                    if 4.0 <= value <= 8.0:
                        params['detail_scale'] = value
                    elif 0.5 <= value <= 2.0:
                        params['normal_strength'] = value
        except:
            pass

        return params

    def extract_texture_info(self, bin_path):
        textures = {}
        texture_dir = bin_path.parent
        base_name = bin_path.stem
        texture_patterns = {
            'bump': [f"{base_name}_bump.dds", f"{base_name}_bump.png", f"{base_name}_bump.tga"],
            'detail': [f"{base_name}_det.dds", f"{base_name}_det.png", f"{base_name}_detail.tga", f"{base_name}_detail.dds"],
            'specular': [f"{base_name}_specular.dds", f"{base_name}_spec.dds", f"{base_name}_spec.png"],
            'albedo': [f"{base_name}.dds", f"{base_name}.tga", f"{base_name}_diffuse.dds", f"{base_name}_color.tga"],
        }

        for tex_type, patterns in texture_patterns.items():
            textures[tex_type] = self.find_texture_file(texture_dir, patterns)
        return textures

    def find_texture_file(self, directory, candidates):
        for candidate in candidates:
            tex_path = directory / candidate
            if tex_path.exists():
                return tex_path
        return None
