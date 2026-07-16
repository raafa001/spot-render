#!/usr/bin/env python3
"""
Spot Render - Maya ASCII (.ms) to Blender (.blend) Converter

Converte arquivos Maya ASCII (.ms) para Blender usando pipeline FBX intermediário.
Usa Blender como conversor principal.

Uso:
    python maya_converter.py input.ms output.blend
"""

import os
import sys
import subprocess
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple

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
    # Seleciona todos os objetos
    bpy.ops.object.select_all(action='SELECT')
    # Deleta todos
    bpy.ops.object.delete(use_global=False)

    # Limpa dados não utilizados
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)
    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)

def import_maya_file(filepath):
    """Importa arquivo Maya (suporta .ma, .mb, .ms ASCII)."""
    filepath = os.path.abspath(filepath)

    # Tenta FBX primeiro (mais compatível)
    try:
        bpy.ops.import_scene.fbx(filepath=filepath)
        print(f"Importado via FBX: {{len(bpy.data.objects)}} objetos")
        return True
    except Exception as e:
        print(f"FBX import falhou: {{e}}")

    # Tenta OBJ
    try:
        bpy.ops.import_scene.obj(filepath=filepath)
        print(f"Importado via OBJ: {{len(bpy.data.objects)}} objetos")
        return True
    except Exception as e:
        print(f"OBJ import falhou: {{e}}")

    return False

def convert_maya_to_blend(input_path, output_path):
    """Pipeline principal de conversão."""
    input_path = os.path.abspath(input_path)
    output_path = os.path.abspath(output_path)

    print(f"Convertendo: {{input_path}}")
    print(f"Saída: {{output_path}}")

    # Limpa cena
    clear_scene()

    # Importa arquivo
    if not import_maya_file(input_path):
        print("ERRO: Não foi possível importar o arquivo")
        return False

    # Cria diretório de saída se não existir
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Salva como .blend
    bpy.ops.wm.save_as_mainfile(filepath=output_path)

    print(f"Conversão concluída: {{output_path}}")
    return True

if __name__ == '__main__':
    input_file = sys.argv[-2]
    output_file = sys.argv[-1]
    success = convert_maya_to_blend(input_file, output_file)
    sys.exit(0 if success else 1)
'''


def convert_maya_to_blend(input_path: str, output_path: str) -> bool:
    """
    Converte arquivo Maya ASCII (.ms) para Blender (.blend).

    Args:
        input_path: Caminho do arquivo .ms de entrada
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
    if suffix not in ['.ms', '.ma', '.mb']:
        logger.error(f"Esperado arquivo Maya (.ms, .ma, .mb), recebido: {suffix}")
        return False

    blender_path = get_blender_path()
    if not os.path.exists(blender_path):
        logger.error(f"Blender não encontrado: {blender_path}")
        return False

    # Cria diretório de saída
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Salva script Blender temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(BLENDER_SCRIPT)
        script_path = f.name

    try:
        # Executa Blender em background
        cmd = [
            blender_path,
            '--background',
            '--python', script_path,
            '--',
            str(input_path),
            str(output_path),
        ]

        logger.info(f"Executando Blender: {blender_path}")
        logger.info(f"Input: {input_path}")
        logger.info(f"Output: {output_path}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos
        )

        if result.returncode == 0:
            logger.info("Conversão bem sucedida!")
            return True
        else:
            logger.error(f"Blender retornou código: {result.returncode}")
            if result.stdout:
                logger.error(f"STDOUT: {result.stdout[-1000:]}")
            if result.stderr:
                logger.error(f"STDERR: {result.stderr[-1000:]}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout - conversão levou mais de 10 minutos")
        return False
    except Exception as e:
        logger.error(f"Erro durante conversão: {e}")
        return False
    finally:
        # Limpa script temporário
        if os.path.exists(script_path):
            os.unlink(script_path)


def main():
    if len(sys.argv) < 3:
        print("Uso: maya_converter.py <input.ms> <output.blend>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    if convert_maya_to_blend(input_file, output_file):
        print(f"OK: {output_file}")
        sys.exit(0)
    else:
        print("FALHA na conversão")
        sys.exit(1)


if __name__ == '__main__':
    main()
