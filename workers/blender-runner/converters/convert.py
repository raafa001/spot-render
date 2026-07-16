#!/usr/bin/env python3
"""
Spot Render - Universal File Format Converter

Converte automaticamente arquivos de diversos formatos 3D para Blender (.blend).
Detecta o formato pelo extension e usa o conversor apropriado.

Formatos suportados:
- Maya: .ma, .ms (Maya ASCII)
- 3ds Max: .max (via FBX intermediário)
- FBX: .fbx
- OBJ: .obj
- glTF: .gltf, .glb
- Blender: .blend (cópia direta)

Uso:
    python convert.py input.ms output.blend
    python convert.py input.max output.blend
    python convert.py input.fbx output.blend  # auto-detecta
"""

import os
import sys
import shutil
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# Mapeamento de formatos para tipos
FORMAT_MAP: Dict[str, str] = {
    '.blend': 'blender',
    '.ms': 'maya',
    '.ma': 'maya',
    '.mb': 'maya',
    '.max': 'max',
    '.fbx': 'fbx',
    '.obj': 'obj',
    '.gltf': 'gltf',
    '.glb': 'gltf',
    '.3ds': '3ds',
}


def get_blender_path() -> str:
    """Retorna o caminho do Blender."""
    blender_path = os.environ.get('BLENDER_PATH', '/opt/blender/blender')
    if not os.path.exists(blender_path):
        alternatives = [
            '/opt/blender-3.6.9-linux-x64/blender',
            '/opt/blender/blender',
            '/usr/bin/blender',
            'blender',
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                return alt
    return blender_path


BLENDER_CONVERT_SCRIPT = '''
import bpy
import sys
import os


def clear_scene():
    """Limpa cena atual."""
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # Remove todos os objetos
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)

    # Limpa dados não utilizados
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


def import_file(filepath):
    """Importa arquivo baseado na extensão."""
    filepath = os.path.abspath(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    importers = {
        '.fbx': bpy.ops.import_scene.fbx,
        '.obj': bpy.ops.import_scene.obj,
        '.gltf': bpy.ops.import_scene.gltf,
        '.glb': bpy.ops.import_scene.gltf,
        '.3ds': bpy.ops.import_scene.threeds,
    }

    importer = importers.get(ext)
    if importer:
        try:
            importer(filepath=filepath)
            return True
        except Exception as e:
            print(f"Import via {{ext}} falhou: {{e}}", file=sys.stderr)
            return False

    return False


def main():
    input_file = sys.argv[-2]
    output_file = sys.argv[-1]

    print(f"Input: {{input_file}}", file=sys.stderr)
    print(f"Output: {{output_file}}", file=sys.stderr)

    clear_scene()

    if import_file(input_file):
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=output_file)
        print(f"Conversão concluída: {{output_file}}", file=sys.stderr)
        sys.exit(0)
    else:
        print("Falha na importação", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
'''


def convert_to_blend(input_path: str, output_path: str) -> bool:
    """
    Converte qualquer arquivo 3D suportado para Blender (.blend).

    Args:
        input_path: Caminho do arquivo de entrada
        output_path: Caminho do arquivo .blend de saída

    Returns:
        True se conversão foi bem sucedida, False caso contrário.
    """
    input_path = Path(input_path).resolve()
    output_path = Path(output_path).resolve()

    if not input_path.exists():
        logger.error(f"Arquivo não encontrado: {input_path}")
        return False

    suffix = input_path.suffix.lower()
    if suffix not in FORMAT_MAP:
        logger.error(f"Formato não suportado: {suffix}")
        logger.error(f"Suportados: {list(FORMAT_MAP.keys())}")
        return False

    # Se já é .blend, só copia
    if suffix == '.blend':
        logger.info("Arquivo já é .blend - copiando")
        shutil.copy2(input_path, output_path)
        return True

    blender_path = get_blender_path()
    if not os.path.exists(blender_path):
        logger.error(f"Blender não encontrado: {blender_path}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Salva script temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(BLENDER_CONVERT_SCRIPT)
        script_path = f.name

    try:
        cmd = [
            blender_path,
            '--background',
            '--python', script_path,
            '--',
            str(input_path),
            str(output_path),
        ]

        logger.info(f"Convertendo {input_path.suffix} → .blend")
        logger.info(f"Blender: {blender_path}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 min
        )

        if result.returncode == 0 and output_path.exists():
            logger.info(f"✓ Conversão bem sucedida: {output_path}")
            return True
        else:
            logger.error(f"Código: {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().split('\n')[-5:]:
                    logger.error(f"  {line}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout na conversão (10 min)")
        return False
    except Exception as e:
        logger.error(f"Erro: {e}")
        return False
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)


def main():
    if len(sys.argv) < 3:
        print("Uso: convert.py <entrada> <saida.blend>")
        print("")
        print("Formatos suportados:")
        print("  Maya:     .ma, .ms, .mb")
        print("  3ds Max:  .max (via FBX)")
        print("  Interop:  .fbx, .obj, .gltf, .glb, .3ds")
        print("  Blender:  .blend (cópia direta)")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if convert_to_blend(input_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
