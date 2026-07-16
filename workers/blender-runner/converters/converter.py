#!/usr/bin/env python3
"""
Spot Render - File Format Converter

Converte arquivos Maya (.ms, .ma) e 3ds Max (.max) para Blender (.blend).
Usa Blender Python API para importação e conversão.

Dependências:
- Blender 3.6+ com Python
- Para .max: 需要 3ds Max ou conversor compatível (Axis Neuron, etc)

Uso:
    python converter.py input.ms output.blend
    python converter.py input.max output.blend
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Formatos suportados e extensões
SUPPORTED_FORMATS = {
    '.blend': 'blender',
    '.ms': 'maya_ascii',
    '.ma': 'maya_ascii',
    '.max': '3dsmax',
    '.fbx': 'fbx',
    '.obj': 'obj',
    '.gltf': 'gltf',
    '.glb': 'gltf',
}


def get_blender_path() -> str:
    """Retorna o caminho do Blender."""
    blender_path = os.environ.get('BLENDER_PATH', '/opt/blender/blender')
    if not os.path.exists(blender_path):
        # Tenta caminhos alternativos
        alternatives = [
            '/opt/blender-3.6.9-linux-x64/blender',
            '/usr/bin/blender',
            'blender',
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                return alt
    return blender_path


def check_blender_version(blender_path: str) -> Optional[tuple]:
    """Verifica a versão do Blender."""
    try:
        result = subprocess.run(
            [blender_path, '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip()
        # Espera formato like "Blender 3.6.9"
        if 'Blender' in output:
            version_str = output.split()[1]
            version = tuple(map(int, version_str.split('.')))
            return version
    except Exception as e:
        logger.warning(f"Não foi possível verificar versão do Blender: {e}")
    return None


def blender_import_script(input_file: str, output_file: str, format_type: str) -> str:
    """
    Gera script Python para o Blender importar o arquivo.

    Returns:
        Script Python para executar dentro do Blender.
    """
    input_path = Path(input_file).resolve().as_posix()
    output_path = Path(output_file).resolve().as_posix()

    if format_type == 'maya_ascii':
        # Blender pode importar .ma via Python (limitado)
        # Tenta usar bpy.ops.import_scene
        script = f'''
import bpy
import sys

# Limpa cena atual
bpy.ops.wm.read_factory_settings(use_empty=True)

input_file = "{input_path}"

try:
    # Tenta importar como FBX primeiro (mais compatível)
    bpy.ops.import_scene.fbx(filepath=input_file)
except Exception as e:
    print(f"FBX import failed: {{e}}")
    try:
        # Tenta importar como OBJ
        bpy.ops.import_scene.obj(filepath=input_file)
    except Exception as e2:
        print(f"OBJ import failed: {{e2}}")
        # Para .ms Maya ASCII, tentamos via pipeline
        sys.exit(1)

# Salva como .blend
bpy.ops.wm.save_as_mainfile(filepath="{output_path}")
print(f"Arquivo convertido com sucesso: {{output_path}}")
'''
    elif format_type == '3dsmax':
        # .max é muito complexo - marca como não suportado diretamente
        script = f'''
import bpy
import sys

# .max (3ds Max) não é suportado diretamente pelo Blender
# Precisaria de conversão via FBX ou software intermediário

print("ERRO: Formato .max não é suportado diretamente. Use export FBX do 3ds Max primeiro.")
sys.exit(1)
'''
    elif format_type == 'fbx':
        script = f'''
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    bpy.ops.import_scene.fbx(filepath="{input_path}")
    bpy.ops.wm.save_as_mainfile(filepath="{output_path}")
    print(f"Conversão FBX -> Blender concluída")
except Exception as e:
    print(f"Erro na importação FBX: {{e}}")
    import sys
    sys.exit(1)
'''
    elif format_type == 'obj':
        script = f'''
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    bpy.ops.import_scene.obj(filepath="{input_path}")
    bpy.ops.wm.save_as_mainfile(filepath="{output_path}")
    print(f"Conversão OBJ -> Blender concluída")
except Exception as e:
    print(f"Erro na importação OBJ: {{e}}")
    import sys
    sys.exit(1)
'''
    elif format_type == 'gltf':
        script = f'''
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)

try:
    bpy.ops.import_scene.gltf(filepath="{input_path}")
    bpy.ops.wm.save_as_mainfile(filepath="{output_path}")
    print(f"Conversão glTF -> Blender concluída")
except Exception as e:
    print(f"Erro na importação glTF: {{e}}")
    import sys
    sys.exit(1)
'''
    else:  # blender
        # Já é .blend, só copia
        script = f'''
import bpy
import shutil

src = "{input_path}"
dst = "{output_path}"
shutil.copy(src, dst)
print(f"Arquivo .blend copiado")
'''

    return script


def convert_with_blender(input_file: str, output_file: str, format_type: str) -> bool:
    """
    Converte arquivo usando Blender como conversor.

    Args:
        input_file: Caminho do arquivo de entrada
        output_file: Caminho do arquivo .blend de saída
        format_type: Tipo do arquivo (maya_ascii, 3dsmax, fbx, obj, etc)

    Returns:
        True se conversão foi bem sucedida, False caso contrário.
    """
    blender_path = get_blender_path()
    logger.info(f"Usando Blender em: {blender_path}")

    # Verifica se Blender existe
    if not os.path.exists(blender_path):
        logger.error(f"Blender não encontrado em: {blender_path}")
        return False

    # Gera script Python
    script_content = blender_import_script(input_file, output_file, format_type)

    # Salva script temporário
    script_path = Path(output_file).parent / f".convert_{Path(input_file).stem}.py"
    script_path.write_text(script_content)

    try:
        # Executa Blender em modo background com script
        cmd = [
            blender_path,
            '--background',
            '--python', str(script_path),
        ]

        logger.info(f"Executando: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minutos max
        )

        if result.returncode == 0:
            logger.info(f"Conversão bem sucedida: {output_file}")
            return True
        else:
            logger.error(f"Blender retornou código {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Timeout na conversão (10 minutos)")
        return False
    except Exception as e:
        logger.error(f"Erro durante conversão: {e}")
        return False
    finally:
        # Limpa script temporário
        if script_path.exists():
            script_path.unlink()


def convert_file(input_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Converte um arquivo para .blend.

    Args:
        input_path: Caminho do arquivo de entrada
        output_path: Caminho do arquivo de saída (opcional)

    Returns:
        Caminho do arquivo convertido ou None se falhou.
    """
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()

    if suffix not in SUPPORTED_FORMATS:
        logger.error(f"Formato não suportado: {suffix}")
        logger.error(f"Suportados: {list(SUPPORTED_FORMATS.keys())}")
        return None

    format_type = SUPPORTED_FORMATS[suffix]

    # Se já é .blend, só retorna o caminho
    if format_type == 'blender':
        logger.info("Arquivo já é .blend")
        return str(input_path)

    # Determina output
    if output_path is None:
        output_path = input_path.with_suffix('.blend')
    else:
        output_path = Path(output_path)

    # Garante que diretório de saída existe
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Converte
    if convert_with_blender(str(input_path), str(output_path), format_type):
        return str(output_path)

    return None


def main():
    if len(sys.argv) < 2:
        print("Uso: converter.py <arquivo_entrada> [arquivo_saida]")
        print(f"Formatos suportados: {list(SUPPORTED_FORMATS.keys())}")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    result = convert_file(input_file, output_file)

    if result:
        print(f"Conversão concluída: {result}")
        sys.exit(0)
    else:
        print("Falha na conversão")
        sys.exit(1)


if __name__ == '__main__':
    main()
