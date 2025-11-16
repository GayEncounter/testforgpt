import struct

class BinParser:
    def __init__(self, config):
        self.config = config

    def parse(self, fbx_path):
        bin_path = self.find_bin_file(fbx_path)
        if not bin_path:
            return None

        print(f"Парсинг .bin файла: {bin_path.name}")

        try:
            with open(bin_path, 'rb') as f:
                data = f.read()
            bin_data = self.decode_bin_structure(data)
            texture_info = self.extract_texture_info(fbx_path)
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
            # Metro-specific patterns
            fbx_path.parent / (fbx_path.stem + '_model.bin'),
        ]

        for bin_path in possible_names:
            if bin_path.exists():
                return bin_path
        return None

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

    def extract_texture_info(self, fbx_path):
        textures = {}
        model_dir = fbx_path.parent
        texture_patterns = {
            'bump': ['*_bump.dds', '*_bump.png', '*_bump.tga'],
            'detail': ['*_detail.dds', '*_detail.png', '*_detail.tga'],
            'specular': ['*_specular.dds', '*_spec.png', '*_specular.tga'],
            'albedo': ['*_albedo.dds', '*_diffuse.dds', '*_color.dds', '*.dds']  # fallback
        }
        for tex_type, patterns in texture_patterns.items():
            textures[tex_type] = self.find_texture_file(model_dir, patterns, fbx_path.stem)
        return textures

    def find_texture_file(self, directory, patterns, model_name):
        for pattern in patterns:
            search_pattern = pattern.replace('*', model_name)
            matches = list(directory.glob(search_pattern))
            if matches:
                return matches[0]
        return None