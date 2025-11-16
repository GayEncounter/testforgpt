# import aspose.threed as a3d
#
# # Создание новой сцены
#
# scene = a3d.Scene.from_file("source/Diaochan/H_Diaochan (merge).fbx")

# !/usr/bin/env python3

import os
import sys
import yaml
import argparse
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.bin_parser import BinParser
from modules.texture_processor import TextureProcessor
from modules.blender_operator import BlenderOperator
from modules.vmat_generator import VMatGenerator
from modules.vmdl_generator import VMDLGenerator


class FBXToVMDLConverter:

    def __init__(self, config_path="config.yaml"):
        self.load_config(config_path)
        self.setup_directories()

    def load_config(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        print("Конфигурация загружена")

    def setup_directories(self):
        self.work_dirs = {
            'input': Path('input'),
            'output': Path('output'),
            'temp': Path('temp'),
            'textures': Path('output/textures'),
            'details_raw': Path('temp/details_RGB'),
            'details_baked': Path('output/textures/details_baked')
        }

        for dir_path in self.work_dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        print("Рабочие директории созданы")
        self.input_root = self.work_dirs['input']

    def find_fbx_files(self, input_dir=None):
        if input_dir is None:
            input_dir = self.work_dirs['input']

        fbx_files = list(input_dir.rglob('*.fbx'))
        print(f"Найдено {len(fbx_files)} FBX файлов")
        return fbx_files

    def process_single_model(self, fbx_path):
        print(f"\nНачинаем обработку: {fbx_path.name}")

        try:
            context = self.prepare_output_context(fbx_path)

            bin_data = self.parse_bin_file(fbx_path)
            if not bin_data:
                print(f".bin файл не найден для {fbx_path.name}, используются настройки по умолчанию")
                bin_data = self.get_default_bin_data()

            texture_data = self.process_textures(fbx_path, bin_data, context)
            model_data = self.process_geometry(fbx_path, bin_data, context)
            vmat_path = self.generate_vmat(fbx_path, texture_data, bin_data, context)
            if model_data:
                self.generate_vmdl(fbx_path, model_data, vmat_path, context)

            print(f"Успешно обработано: {fbx_path.name}")
            return True

        except Exception as e:
            print(f"Ошибка при обработке {fbx_path.name}: {str(e)}")
            return False

    def parse_bin_file(self, fbx_path):
        bin_parser = BinParser(self.config, self.input_root)
        return bin_parser.parse(fbx_path)

    def get_default_bin_data(self):
        return {
            'textures': {
                'bump': None,
                'detail': None,
                'specular': None,
                'albedo': None
            },
            'material_params': {
                'detail_scale': 6.0,
                'normal_strength': 1.0,
                'specular_level': 0.5
            }
        }

    def process_textures(self, fbx_path, bin_data, context):
        processor = TextureProcessor(self.config)
        work_dirs = self.work_dirs.copy()
        work_dirs['textures'] = context['texture_output_dir']
        work_dirs['details_raw'] = context['details_raw_dir']
        work_dirs['details_baked'] = context['details_baked_dir']
        return processor.process_all_textures(fbx_path, bin_data, work_dirs)

    def process_geometry(self, fbx_path, bin_data, context):
        blender_op = BlenderOperator(self.config)
        work_dirs = self.work_dirs.copy()
        work_dirs['model_output'] = context['model_output_dir']
        return blender_op.process_model(fbx_path, work_dirs)

    def generate_vmat(self, fbx_path, texture_data, bin_data, context):
        vmat_gen = VMatGenerator(self.config)
        work_dirs = self.work_dirs.copy()
        work_dirs['model_output'] = context['model_output_dir']
        return vmat_gen.generate(fbx_path, texture_data, bin_data, work_dirs)

    def generate_vmdl(self, fbx_path, model_data, vmat_path, context):
        vmdl_gen = VMDLGenerator(self.config)
        work_dirs = self.work_dirs.copy()
        work_dirs['model_output'] = context['model_output_dir']
        return vmdl_gen.generate(fbx_path, model_data, vmat_path, work_dirs)

    def prepare_output_context(self, fbx_path):
        relative_path = self.get_relative_model_path(fbx_path)
        model_output_dir = (self.work_dirs['output'] / relative_path.parent).resolve()
        texture_output_dir = model_output_dir / 'textures'
        details_raw_dir = texture_output_dir / 'details_raw'
        details_baked_dir = texture_output_dir / 'details_baked'

        for directory in [model_output_dir, texture_output_dir, details_raw_dir, details_baked_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        return {
            'relative_path': relative_path,
            'model_output_dir': model_output_dir,
            'texture_output_dir': texture_output_dir,
            'details_raw_dir': details_raw_dir,
            'details_baked_dir': details_baked_dir
        }

    def get_relative_model_path(self, fbx_path):
        try:
            return fbx_path.relative_to(self.input_root)
        except Exception:
            return Path(fbx_path.name)

    def batch_convert(self, input_dir=None):
        if input_dir:
            self.input_root = input_dir
        fbx_files = self.find_fbx_files(input_dir)
        success_count = 0
        for fbx_path in fbx_files:
            if self.process_single_model(fbx_path):
                success_count += 1
        print(f"\nИтог: {success_count}/{len(fbx_files)} моделей успешно сконвертировано")
        return success_count


def main():
    parser = argparse.ArgumentParser(description='Конвертер FBX to VMDL для S&Box')
    parser.add_argument('--input', '-i', help='Входная директория с FBX файлами')
    parser.add_argument('--single', '-s', help='Конвертировать один FBX файл')
    parser.add_argument('--config', '-c', default='config.yaml', help='Путь к файлу конфигурации')
    args = parser.parse_args()
    converter = FBXToVMDLConverter(args.config)
    if args.single:
        fbx_path = Path(args.single)
        if fbx_path.exists():
            converter.input_root = fbx_path.parent
            converter.process_single_model(fbx_path)
        else:
            print(f"Файл не найден: {args.single}")
    elif args.input:
        converter.batch_convert(Path(args.input))
    else:
        converter.batch_convert()


if __name__ == "__main__":
    main()
    os.system("pause")  # или input("Нажмите Enter, чтобы выйти...")