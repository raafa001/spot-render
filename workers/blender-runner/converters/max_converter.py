#!/usr/bin/env python3
"""
Spot Render - 3ds Max (.max) to Blender (.blend) Converter

Converte arquivos 3ds Max (.max) para Blender usando pipeline FBX intermediário.

NOTA: .max é um formato proprietário da Autodesk. A conversão direta não é
possível sem software intermediário. Este conversor:

1. Para arquivos .max com FBX exportado: usa Blender para converter FBX -> .blend
2. Para uso completo, recomenda-se exportar .max para FBX primeiro usando 3ds Max

Alternativas para conversão:
1. Exportar manualmente de 3ds Max para FBX/OBJ
2. Usar Autodesk Maya ou 3ds Max com script de export
3. Usar serviços de conversão em nuvem

Uso:
    python max_converter.py input.max output.blend
    python max_converter.py input.fbx output.blend  # FBX também suportado
"""

import os
import sys
import subprocess
import logging
import tempfile
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_blender_path() -> str:
    """Retorna o caminho do Blender."""
    blender_path = os.environ.get('BLENDER_PATH', '/opt/blender/blender')
    if not os.path.exists(blender_path):
        alternatives = [
            '/opt/blender-3.6.9-linux-x64/blender',
            '/usr/bin/blender',
            'blender',
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                return alt
    return blender_path


BLENDER_SCRIPT = '''
import bpy
import sys
import os

def clear_scene():
    """Limpa todos os objetos, materiais e meshes da cena."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)

def import_file(filepath):
    """Importa arquivo para Blender."""
    filepath = os.path.abspath(filepath)
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.fbx':
        try:
            bpy.ops.import_scene.fbx(filepath=filepath)
            print(f"Importado FBX: {{len(bpy.data.objects)}} objetos")
            return True
        except Exception as e:
            print(f"FBX import falhou: {{e}}")

    elif ext == '.obj':
        try:
            bpy.ops.import_scene.obj(filepath=filepath)
            print(f"Importado OBJ: {{len(bpy.data.objects)}} objetos")
            return True
        except Exception as e:
            print(f"OBJ import falhou: {{e}}")

    elif ext == '.gltf' or ext == '.glb':
        try:
            bpy.ops.import_scene.gltf(filepath=filepath)
            print(f"Importado glTF: {{len(bpy.data.objects)}} objetos")
            return True
        except Exception as e:
            print(f"glTF import falhou: {{e}}")

    elif ext == '.3ds':
        try:
            bpy.ops.import_scene.threeds(filepath=filepath)
            print(f"Importado 3DS: {{len(bpy.data.objects)}} objetos")
            return True
        except Exception as e:
            print(f"3DS import falhou: {{e}}")

    return False

def convert_to_blend(input_path, output_path):
    """Pipeline principal de conversão."""
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    print(f"Convertendo: {{input_path}}")
    print(f"Saída: {{output_path}}")

    clear_scene()

    if not import_file(input_path):
        print("ERRO: Não foi possível importar o arquivo")
        return False

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=output_path)

    print(f"Conversão concluída: {{output_path}}")
    return True

if __name__ == '__main__':
    input_file = sys.argv[-2]
    output_file = sys.argv[-1]
    success = convert_to_blend(input_file, output_file)
    sys.exit(0 if success else 1)
'''


def convert_max_to_blend(input_path: str, output_path: str) -> bool:
    """
    Converte arquivo 3ds Max ou FBX para Blender (.blend).

    Args:
        input_path: Caminho do arquivo .max ou .fbx de entrada
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
    if suffix not in ['.max', '.fbx', '.obj', '.gltf', '.glb', '.3ds']:
        logger.error(f"Formato não suportado: {suffix}")
        logger.error("Suportados: .max, .fbx, .obj, .gltf, .glb, .3ds")
        return False

    blender_path = get_blender_path()
    if not os.path.exists(blender_path):
        logger.error(f"Blender não encontrado: {blender_path}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(BLENDER_SCRIPT)
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

        logger.info(f"Executando: {blender_path}")
        logger.info(f"Input: {input_path}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )

        if result.returncode == 0:
            logger.info("Conversão bem sucedida!")
            return True
        else:
            logger.error(f"Código de retorno: {result.returncode}")
            if result.stdout:
                logger.error(f"STDOUT: {result.stdout[-1000:]}")
            if result.stderr:
                logger.error(f"STDERR: {result.stderr[-1000:]}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout na conversão")
        return False
    except Exception as e:
        logger.error(f"Erro: {e}")
        return False
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)


def main():
    if len(sys.argv) < 3:
        print("Uso: max_converter.py <input.max|fbx|obj> <output.blend>")
        print("")
        print("Para arquivos .max, recomenda-se primeiro exportar para FBX/OBJ")
        print("usando 3ds Max, ثم استخدام Blender للتحويل النهائي.")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if convert_max_to_blend(input_file, output_file):
        print(f"OK: {output_file}")
        sys.exit(0)
    else:
        print("FALHA")
        sys.exit(1)


if __name__ == '__main__':
    main()
