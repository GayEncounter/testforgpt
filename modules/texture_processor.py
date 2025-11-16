import cv2
import numpy as np


class TextureProcessor:
    def __init__(self, config):
        self.config = config

    def process_all_textures(self, fbx_path, bin_data, work_dirs):
        texture_data = {}

        if bin_data['textures'].get('bump'):
            bump_path = bin_data['textures']['bump']
            normal_path = self.convert_bump_to_normal(bump_path, work_dirs)
            texture_data['normal'] = normal_path
        if bin_data['textures'].get('detail'):
            detail_path = bin_data['textures']['detail']
            detail_results = self.process_detail_texture(
                detail_path,
                bin_data['textures'].get('bump'),
                bin_data['material_params'],
                work_dirs
            )
            texture_data.update(detail_results)
        texture_data.update(self.process_other_textures(bin_data['textures'], work_dirs))
        return texture_data

    def convert_bump_to_normal(self, bump_path, work_dirs):
        print(f"Конвертируем bump в normal: {bump_path.name}")
        try:
            if bump_path.suffix.lower() == '.dds':
                bump_img = self.load_dds_texture(bump_path)
            else:
                bump_img = cv2.imread(str(bump_path), cv2.IMREAD_GRAYSCALE)

            if bump_img is None:
                raise ValueError(f"Не удалось загрузить bump текстуру: {bump_path}")
            target_res = self.config['global_settings']['texture_resolution']
            if max(bump_img.shape) != target_res:
                bump_img = cv2.resize(bump_img, (target_res, target_res))
            bump_img = bump_img.astype(np.float32) / 255.0
            scale = self.config['textures']['bump_to_normal']['scale']

            grad_x = cv2.Sobel(bump_img, cv2.CV_32F, 1, 0, ksize=3) * scale
            grad_y = cv2.Sobel(bump_img, cv2.CV_32F, 0, 1, ksize=3) * scale
            if self.config['textures']['bump_to_normal']['invert_x']:
                grad_x = -grad_x
            if self.config['textures']['bump_to_normal']['invert_y']:
                grad_y = -grad_y

            normal_map = np.zeros((bump_img.shape[0], bump_img.shape[1], 3), dtype=np.float32)
            normal_map[:, :, 0] = grad_x
            normal_map[:, :, 1] = grad_y
            normal_map[:, :, 2] = 1.0

            norm = np.sqrt(np.sum(normal_map ** 2, axis=2))
            normal_map[:, :, 0] /= norm
            normal_map[:, :, 1] /= norm
            normal_map[:, :, 2] /= norm

            normal_map = (normal_map + 1.0) * 0.5 * 255.0
            normal_map = np.clip(normal_map, 0, 255).astype(np.uint8)

            output_path = work_dirs['textures'] / f"{bump_path.stem}_normal.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), normal_map)

            print(f"Normal map создана: {output_path.name}")
            return output_path

        except Exception as e:
            print(f"Ошибка конвертации bump в normal: {e}")
            return None

    def process_detail_texture(self, detail_path, bump_path, material_params, work_dirs):
        print(f"Обрабатываем detail текстуру: {detail_path.name}")

        try:
            detail_img = cv2.imread(str(detail_path), cv2.IMREAD_COLOR)
            if detail_img is None:
                raise ValueError(f"Не удалось загрузить detail текстуру: {detail_path}")
            detail_r, detail_g, detail_b = cv2.split(detail_img)
            self.save_detail_channels(detail_r, detail_g, detail_b, detail_path, work_dirs)

            final_detail = self.bake_detail_texture(
                detail_r, detail_g, detail_b,
                bump_path, material_params, work_dirs, detail_path
            )

            detail_normal = self.generate_detail_normal(final_detail, work_dirs, detail_path)

            return {
                'detail_final': final_detail,
                'detail_normal': detail_normal
            }

        except Exception as e:
            print(f"Ошибка обработки detail текстуры: {e}")
            return {}

    def save_detail_channels(self, detail_r, detail_g, detail_b, detail_path, work_dirs):
        base_name = detail_path.stem.replace('_detail', '')

        raw_dir = work_dirs['details_raw']
        raw_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(raw_dir / f"{base_name}_detail_R.png"), detail_r)
        cv2.imwrite(str(raw_dir / f"{base_name}_detail_G.png"), detail_g)
        cv2.imwrite(str(raw_dir / f"{base_name}_detail_B.png"), detail_b)

        print("Detail каналы сохранены")

    def bake_detail_texture(self, detail_r, detail_g, detail_b, bump_path, material_params, work_dirs, detail_path):
        if bump_path and bump_path.exists():
            bump_img = cv2.imread(str(bump_path), cv2.IMREAD_COLOR)
            if bump_img is not None:
                mask = bump_img[:, :, 2]
            else:
                mask = np.full(detail_r.shape, 127, dtype=np.uint8) # костыль, пока так
        else:
            mask = np.full(detail_r.shape, 127, dtype=np.uint8) # костыль, пока так
        mask = mask.astype(np.float32) / 255.0

        weight_b = np.clip(1.0 - 2.0 * np.abs(mask - 0.0), 0, 1)
        weight_g = np.clip(1.0 - 2.0 * np.abs(mask - 0.5), 0, 1)
        weight_r = np.clip(1.0 - 2.0 * np.abs(mask - 1.0), 0, 1)
        total_weight = weight_r + weight_g + weight_b
        weight_r /= total_weight
        weight_g /= total_weight
        weight_b /= total_weight

        final_detail = (
                weight_r * detail_r.astype(np.float32) +
                weight_g * detail_g.astype(np.float32) +
                weight_b * detail_b.astype(np.float32)
        ).astype(np.uint8)

        output_path = work_dirs['details_baked'] / f"{detail_path.stem}_final.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), final_detail)

        print(f"Запеченная detail текстура сохранена: {output_path.name}")
        return output_path

    def generate_detail_normal(self, detail_path, work_dirs, original_detail_path):
        try:
            detail_img = cv2.imread(str(detail_path), cv2.IMREAD_GRAYSCALE)
            if detail_img is None:
                return None
            detail_img = detail_img.astype(np.float32) / 255.0
            scale = 1.0

            grad_x = cv2.Sobel(detail_img, cv2.CV_32F, 1, 0, ksize=3) * scale
            grad_y = cv2.Sobel(detail_img, cv2.CV_32F, 0, 1, ksize=3) * scale

            normal_map = np.zeros((detail_img.shape[0], detail_img.shape[1], 3), dtype=np.float32)
            normal_map[:, :, 0] = grad_x
            normal_map[:, :, 1] = grad_y
            normal_map[:, :, 2] = 1.0

            # Нормализация
            norm = np.sqrt(np.sum(normal_map ** 2, axis=2))
            normal_map[:, :, 0] /= norm
            normal_map[:, :, 1] /= norm
            normal_map[:, :, 2] /= norm

            normal_map = (normal_map + 1.0) * 0.5 * 255.0
            normal_map = np.clip(normal_map, 0, 255).astype(np.uint8)

            base_name = original_detail_path.stem.replace('_detail', '')
            output_path = work_dirs['details_baked'] / f"{base_name}_detail_normal.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), normal_map)

            print(f"Detail normal map создана: {output_path.name}")
            return output_path

        except Exception as e:
            print(f"⚠Не удалось создать detail normal map: {e}")
            return None

    def process_other_textures(self, textures, work_dirs):
        processed = {}

        for tex_type, tex_path in textures.items():
            if tex_path and tex_type not in ['bump', 'detail']:
                processed_path = self.process_generic_texture(tex_path, work_dirs)
                if processed_path:
                    processed[tex_type] = processed_path

        return processed

    def process_generic_texture(self, tex_path, work_dirs):
        try:
            img = cv2.imread(str(tex_path), cv2.IMREAD_UNCHANGED)
            if img is None:
                return None

            target_res = self.config['global_settings']['texture_resolution']
            if max(img.shape[:2]) != target_res:
                img = cv2.resize(img, (target_res, target_res))

            output_path = work_dirs['textures'] / f"{tex_path.stem}.png"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(output_path), img)

            return output_path

        except Exception as e:
            print(f"Ошибка обработки текстуры {tex_path.name}: {e}")
            return None

    def load_dds_texture(self, dds_path):
        # По хорошему сделать загрузку DDS через ImageMagick или DirectXTex
        print(f"⚠️ DDS загрузка не реализована для: {dds_path.name}")
        return None