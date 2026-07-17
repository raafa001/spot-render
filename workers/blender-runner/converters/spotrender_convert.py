#!/usr/bin/env python3
"""
Spot Render - Universal 3D File Converter

Converte automaticamente arquivos de diversos formatos 3D para Blender (.blend).
Inclui validação de arquivos para garantir que são genuínos dos seus formatos.

Formatos suportados:
- Blender: .blend (cópia direta)
- Maya: .ma, .ms (Maya ASCII)
- Maya Binary: .mb
- 3ds Max: .max (via FBX intermediário)
- FBX: .fbx (binary e ASCII)
- OBJ: .obj (Wavefront)
- glTF: .gltf, .glb
- 3DS: .3ds (3D Studio)
- STL: .stl (ASCII e Binary)
- PLY: .ply
- Collada: .dae

Uso:
    python spotrender_convert.py input.ms output.blend
    python spotrender_convert.py input.max output.blend --validate
    python spotrender_convert.py --validate-only input.fbx
"""

import os
import sys
import json
import shutil
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Adiciona path para imports relativos
sys.path.insert(0, str(Path(__file__).parent))

from validators import FileValidator, ValidationResult, ValidationStatus

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# =============================================================================
# Format Configuration
# =============================================================================

SUPPORTED_FORMATS: Dict[str, str] = {
    '.blend': 'blender',
    '.ms': 'maya_ascii',
    '.ma': 'maya_ascii',
    '.mb': 'maya_binary',
    '.max': '3dsmax',
    '.fbx': 'fbx',
    '.obj': 'obj',
    '.gltf': 'gltf',
    '.glb': 'glb',
    '.3ds': '3ds',
    '.stl': 'stl',
    '.ply': 'ply',
    '.dae': 'collada',
    '.dxf': 'dxf',
}


def get_blender_path() -> str:
    """Retorna o caminho do Blender."""
    blender_path = os.environ.get('BLENDER_PATH', '/opt/blender/blender')
    if not os.path.exists(blender_path):
        alternatives = [
            '/opt/blender-4.0.0-linux-x64/blender',
            '/opt/blender-3.6.9-linux-x64/blender',
            '/opt/blender/blender',
            '/usr/bin/blender',
            'blender',
        ]
        for alt in alternatives:
            if os.path.exists(alt):
                return alt
    return blender_path


# =============================================================================
# Blender Import Script Generator
# =============================================================================

def generate_blender_import_script(
    input_file: str,
    output_file: str,
    format_type: str,
    cleanup: bool = True
) -> str:
    """
    Gera script Python para Blender importar o arquivo.

    Args:
        input_file: Caminho do arquivo de entrada
        output_file: Caminho do arquivo .blend de saída
        format_type: Tipo do arquivo
        cleanup: Se deve limpar a cena antes de importar

    Returns:
        Script Python para executar dentro do Blender
    """

    input_path = Path(input_file).resolve().as_posix()
    output_path = Path(output_file).resolve().as_posix()

    cleanup_code = '''
# Limpa cena atual
bpy.ops.wm.read_factory_settings(use_empty=True)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj)
for block in bpy.data.meshes:
    if block.users == 0:
        bpy.data.meshes.remove(block)
for block in bpy.data.materials):
    if block.users == 0:
        bpy.data.materials.remove(block)
''' if cleanup else ''

    import_code = _generate_import_code(format_type, input_path)

    save_code = f'''
# Salva como .blend
os.makedirs(os.path.dirname("{output_path}"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath="{output_path}")
print(f"CONVERSION_SUCCESS:{{output_path}}")
'''

    return f'''
import bpy
import sys
import os

{cleanup_code}

{import_code}

{save_code}
'''


def _generate_import_code(format_type: str, input_path: str) -> str:
    """Gera código de importação baseado no formato."""

    importers = {
        'fbx': '''
try:
    bpy.ops.import_scene.fbx(filepath="{path}")
    print("Importado FBX: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO FBX: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'obj': '''
try:
    bpy.ops.import_scene.obj(filepath="{path}")
    print("Importado OBJ: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO OBJ: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'gltf': '''
try:
    bpy.ops.import_scene.gltf(filepath="{path}")
    print("Importado glTF: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO glTF: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        '3ds': '''
try:
    bpy.ops.import_scene.threeds(filepath="{path}")
    print("Importado 3DS: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO 3DS: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'stl': '''
try:
    bpy.ops.import_mesh.stl(filepath="{path}")
    print("Importado STL: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO STL: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'ply': '''
try:
    bpy.ops.import_mesh.ply(filepath="{path}")
    print("Importado PLY: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO PLY: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'collada': '''
try:
    bpy.ops.wm.collada_import(filepath="{path}")
    print("Importado Collada: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO Collada: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'dxf': '''
try:
    bpy.ops.import_scene.dxf(filepath="{path}")
    print("Importado DXF: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO DXF: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        'maya_ascii': '''
# Maya ASCII - tenta via FBX ou OBJ primeiro
try:
    bpy.ops.import_scene.fbx(filepath="{path}")
    print("Importado Maya ASCII via FBX: {{len(bpy.data.objects)}} objetos")
except:
    try:
        bpy.ops.import_scene.obj(filepath="{path}")
        print("Importado Maya ASCII via OBJ: {{len(bpy.data.objects)}} objetos")
    except Exception as e:
        print(f"ERRO Maya ASCII: {{e}}")
        print("Maya ASCII pode requerer exportação manual para FBX")
        sys.exit(1)
'''.format(path=input_path),

        'maya_binary': '''
try:
    bpy.ops.import_scene.fbx(filepath="{path}")
    print("Importado Maya Binary via FBX: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO Maya Binary: {{e}}")
    sys.exit(1)
'''.format(path=input_path),

        '3dsmax': '''
# 3ds Max - tenta via FBX
print("ATENCAO: .max requer export FBX do 3ds Max primeiro")
print("Tentando importar como FBX...")
try:
    bpy.ops.import_scene.fbx(filepath="{path}")
    print("Importado 3ds Max via FBX: {{len(bpy.data.objects)}} objetos")
except Exception as e:
    print(f"ERRO 3ds Max: {{e}}")
    print("Recomendacao: Exporte o .max para FBX usando 3ds Max")
    sys.exit(1)
'''.format(path=input_path),

        'blender': '''
# Já é .blend - só copia
print("Arquivo ja e .blend - copiando")
import shutil
shutil.copy("{path}", "{output}")
'''.format(path=input_path, output="${output_path}"),
    }

    return importers.get(format_type, '''
print("ERRO: Formato nao suportado")
sys.exit(1)
''')


# =============================================================================
# Conversion Pipeline
# =============================================================================

class ConversionError(Exception):
    """Exceção para erros de conversão."""
    pass


class FileConversionPipeline:
    """
    Pipeline de conversão de arquivos 3D para Blender.

    Fluxo:
    1. Valida arquivo de entrada
    2. Executa conversão via Blender Python API
    3. Verifica arquivo de saída
    """

    def __init__(self, blender_path: Optional[str] = None, validate: bool = True):
        """
        Args:
            blender_path: Caminho do executável Blender
            validate: Se deve validar arquivos antes da conversão
        """
        self.blender_path = blender_path or get_blender_path()
        self.validate = validate
        self.validator = FileValidator() if validate else None

    def validate_input(self, input_path: str) -> ValidationResult:
        """
        Valida arquivo de entrada.

        Args:
            input_path: Caminho do arquivo

        Returns:
            Resultado da validação
        """
        if not self.validator:
            return ValidationResult(
                filepath=input_path,
                status=ValidationStatus.VALID,
                message="Validação desabilitada"
            )

        result = self.validator.validate(input_path)
        if not result.is_valid:
            logger.warning(f"Arquivo pode estar inválido: {result.message}")
        return result

    def get_format_type(self, input_path: str) -> Optional[str]:
        """Retorna tipo de formato pela extensão."""
        suffix = Path(input_path).suffix.lower()
        return SUPPORTED_FORMATS.get(suffix)

    def convert(
        self,
        input_path: str,
        output_path: str,
        force: bool = False
    ) -> bool:
        """
        Converte arquivo para .blend.

        Args:
            input_path: Caminho do arquivo de entrada
            output_path: Caminho do arquivo .blend de saída
            force: Se True, ignora validação

        Returns:
            True se conversão foi bem sucedida

        Raises:
            ConversionError: Se conversão falhar
        """
        input_path = Path(input_path).resolve()
        output_path = Path(output_path).resolve()

        # 1. Valida entrada
        if not force:
            validation = self.validate_input(str(input_path))
            if not validation.is_valid and validation.status != ValidationStatus.UNKNOWN:
                raise ConversionError(f"Validação falhou: {validation.message}")

        # 2. Verifica arquivo existe
        if not input_path.exists():
            raise ConversionError(f"Arquivo não encontrado: {input_path}")

        # 3. Determina formato
        format_type = self.get_format_type(str(input_path))
        if not format_type:
            raise ConversionError(f"Formato não suportado: {input_path.suffix}")

        # 4. Se já é .blend, só copia
        if format_type == 'blender':
            logger.info("Arquivo já é .blend - copiando")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, output_path)
            return True

        # 5. Verifica Blender existe
        if not os.path.exists(self.blender_path):
            raise ConversionError(f"Blender não encontrado: {self.blender_path}")

        # 6. Cria script temporário
        output_path.parent.mkdir(parents=True, exist_ok=True)

        script_content = generate_blender_import_script(
            str(input_path),
            str(output_path),
            format_type
        )

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(script_content)
            script_path = f.name

        try:
            # 7. Executa Blender
            cmd = [
                self.blender_path,
                '--background',
                '--python', script_path,
                '--',
                str(input_path),
                str(output_path),
            ]

            logger.info(f"Convertendo: {input_path.suffix} → .blend")
            logger.debug(f"Comando: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutos
            )

            # 8. Verifica resultado
            if result.returncode == 0 and output_path.exists():
                logger.info(f"✓ Conversão bem sucedida: {output_path}")
                return True
            else:
                error_msg = self._parse_error(result.stderr, result.stdout)
                raise ConversionError(f"Conversão falhou: {error_msg}")

        except subprocess.TimeoutExpired:
            raise ConversionError("Timeout na conversão (10 minutos)")
        except Exception as e:
            raise ConversionError(f"Erro durante conversão: {e}")
        finally:
            # Cleanup script temporário
            if os.path.exists(script_path):
                os.unlink(script_path)

    def _parse_error(self, stderr: str, stdout: str) -> str:
        """Extrai mensagem de erro do output do Blender."""
        combined = stderr + stdout

        # Procura mensagens de erro comuns
        if 'CONVERSION_SUCCESS' in combined:
            return ""  # Sucesso

        if 'Traceback' in combined:
            # Extrai só o erro relevante
            lines = combined.split('\n')
            for i, line in enumerate(lines):
                if 'Error' in line or 'ERRO' in line:
                    return line.strip()

        return combined[-500:] if len(combined) > 500 else combined.strip()

    def convert_batch(
        self,
        inputs: List[Tuple[str, str]],
        stop_on_error: bool = False
    ) -> Dict[str, bool]:
        """
        Converte múltiplos arquivos.

        Args:
            inputs: Lista de tuplas (input_path, output_path)
            stop_on_error: Se True, para ao primeiro erro

        Returns:
            Dict com input_path -> success
        """
        results = {}

        for input_path, output_path in inputs:
            try:
                success = self.convert(input_path, output_path)
                results[input_path] = success
            except ConversionError as e:
                logger.error(f"Erro: {e}")
                results[input_path] = False
                if stop_on_error:
                    break

        return results


# =============================================================================
# CLI Interface
# =============================================================================

def convert_file(
    input_path: str,
    output_path: Optional[str] = None,
    validate: bool = True,
    force: bool = False
) -> Optional[str]:
    """
    Converte um arquivo para .blend.

    Args:
        input_path: Caminho do arquivo de entrada
        output_path: Caminho do arquivo de saída (opcional)
        validate: Se deve validar arquivo
        force: Se deve forçar conversão mesmo com arquivo inválido

    Returns:
        Caminho do arquivo convertido ou None se falhou
    """
    input_path = Path(input_path)

    # Determina output
    if output_path is None:
        output_path = input_path.with_suffix('.blend')
    else:
        output_path = Path(output_path)

    # Executa conversão
    pipeline = FileConversionPipeline(validate=validate)

    try:
        if pipeline.convert(str(input_path), str(output_path), force=force):
            return str(output_path)
    except ConversionError as e:
        logger.error(f"Erro: {e}")

    return None


def validate_only(filepath: str) -> bool:
    """
    Apenas valida um arquivo.

    Returns:
        True se arquivo é válido
    """
    validator = FileValidator()
    result = validator.validate(filepath)
    print(result)
    return result.is_valid


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Spot Render - Conversor de arquivos 3D para Blender",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
    %(prog)s input.ms output.blend
    %(prog)s input.max output.blend --validate
    %(prog)s --validate-only input.fbx
    %(prog)s --batch inputs.txt

Formatos suportados:
  Blender: .blend
  Maya: .ma, .ms, .mb
  3ds Max: .max
  Interop: .fbx, .obj, .gltf, .glb, .3ds, .stl, .ply, .dae, .dxf
"""
    )

    parser.add_argument('input', nargs='?', help="Arquivo de entrada")
    parser.add_argument('output', nargs='?', help="Arquivo de saída (.blend)")
    parser.add_argument('--validate-only', action='store_true', help="Apenas valida arquivo")
    parser.add_argument('--batch', help="Arquivo com lista de conversões (input|output por linha)")
    parser.add_argument('--no-validate', action='store_true', help="Desabilita validação")
    parser.add_argument('--force', action='store_true', help="Força conversão mesmo com arquivo inválido")
    parser.add_argument('--blender-path', help="Caminho do Blender")
    parser.add_argument('--json-output', help="Saída em formato JSON")

    args = parser.parse_args()

    # Configura pipeline
    pipeline = FileConversionPipeline(
        blender_path=args.blender_path,
        validate=not args.no_validate
    )

    results = {}

    if args.validate_only and args.input:
        # Modo validação
        success = validate_only(args.input)
        sys.exit(0 if success else 1)

    elif args.batch:
        # Modo batch
        batch_file = Path(args.batch)
        if not batch_file.exists():
            logger.error(f"Arquivo batch não encontrado: {args.batch}")
            sys.exit(1)

        conversions = []
        with open(batch_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 2:
                    conversions.append((parts[0].strip(), parts[1].strip()))

        logger.info(f"Processando {len(conversions)} arquivos...")
        results = pipeline.convert_batch(conversions)

    elif args.input and args.output:
        # Conversão simples
        try:
            if pipeline.convert(args.input, args.output, force=args.force):
                logger.info(f"OK: {args.output}")
                sys.exit(0)
            else:
                logger.error("Falha na conversão")
                sys.exit(1)
        except ConversionError as e:
            logger.error(f"Erro: {e}")
            sys.exit(1)

    elif args.input:
        # Sem output - usa mesmo nome com .blend
        output = str(Path(args.input).with_suffix('.blend'))
        try:
            if pipeline.convert(args.input, output, force=args.force):
                logger.info(f"OK: {output}")
                sys.exit(0)
            else:
                logger.error("Falha na conversão")
                sys.exit(1)
        except ConversionError as e:
            logger.error(f"Erro: {e}")
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)

    # Resumo para batch
    if results:
        success = sum(1 for v in results.values() if v)
        logger.info(f"\nConcluído: {success}/{len(results)} conversões bem-sucedidas")

        if args.json_output:
            with open(args.json_output, 'w') as f:
                json.dump(results, f, indent=2)

        sys.exit(0 if success == len(results) else 1)


if __name__ == '__main__':
    main()
