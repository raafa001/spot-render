#!/usr/bin/env python3
"""
Spot Render - 3D File Format Validator

Valida se arquivos 3D são genuínos dos seus respectivos formatos.
Detecta formato pelo magic bytes (file signatures) e não apenas pela extensão.

Formatos suportados:
- Blender: .blend (magic: BLENDER)
- Maya ASCII: .ma, .ms (Maya ASCII format)
- Maya Binary: .mb (Maya Binary format)
- 3ds Max: .max (Autodesk 3ds Max)
- FBX: .fbx (Filmbox)
- OBJ: .obj (Wavefront)
- glTF: .gltf, .glb (GL Transmission Format)
- 3DS: .3ds (3D Studio)
- DXF: .dxf (Drawing Exchange Format)
- STL: .stl (Stereolithography)
- PLY: .ply (Polygon File Format)

Uso:
    python file_validator.py arquivo.max
    python file_validator.py --check-dir /path/to/files
"""

import os
import sys
import struct
import zipfile
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum


# =============================================================================
# Magic Bytes e File Signatures
# =============================================================================

@dataclass
class FormatSignature:
    """Assinatura de formato de arquivo 3D."""
    name: str
    extensions: List[str]
    magic_bytes: Optional[bytes] = None
    magic_offset: int = 0
    is_text: bool = False
    text_pattern: Optional[str] = None  # Regex pattern for text formats


# Assinaturas conhecidas
FORMAT_SIGNATURES: Dict[str, FormatSignature] = {
    'blender': FormatSignature(
        name='Blender',
        extensions=['.blend'],
        magic_bytes=b'BLENDER',
        magic_offset=0
    ),

    'maya_ascii': FormatSignature(
        name='Maya ASCII',
        extensions=['.ma', '.ms'],
        is_text=True,
        text_pattern=r'^#\s*Maya\s+\d+'
    ),

    'maya_binary': FormatSignature(
        name='Maya Binary',
        extensions=['.mb'],
        magic_bytes=b'Maya Binary'
    ),

    '3dsmax': FormatSignature(
        name='3ds Max',
        extensions=['.max'],
        magic_bytes=b'\xC0\x2D\x3D\x00',  # 3DS Max magic
        magic_offset=0
    ),

    'fbx': FormatSignature(
        name='FBX',
        extensions=['.fbx'],
        magic_bytes=b'Kaydara FBX Binary',
        magic_offset=0
    ),

    'fbx_ascii': FormatSignature(
        name='FBX ASCII',
        extensions=['.fbx'],
        is_text=True,
        text_pattern=r'^; FBX'
    ),

    'obj': FormatSignature(
        name='Wavefront OBJ',
        extensions=['.obj'],
        is_text=True,
        text_pattern=r'^(v|vt|vn|f|o|g|mtllib|usemtl)\s'
    ),

    'gltf': FormatSignature(
        name='glTF',
        extensions=['.gltf', '.glb'],
        is_text=True,
        text_pattern=r'^\s*\{'
    ),

    '3ds': FormatSignature(
        name='3D Studio',
        extensions=['.3ds'],
        magic_bytes=b'\x4D\x4D\x01\x03',  # 3DS magic
        magic_offset=0
    ),

    'dxf': FormatSignature(
        name='DXF',
        extensions=['.dxf'],
        is_text=True,
        text_pattern=r'^\s*(0|SECTION|EOF)'
    ),

    'stl_ascii': FormatSignature(
        name='STL ASCII',
        extensions=['.stl'],
        is_text=True,
        text_pattern=r'^solid\s+\S'
    ),

    'stl_binary': FormatSignature(
        name='STL Binary',
        extensions=['.stl'],
        magic_bytes=b'\x00\x00\x00\x00',  # Binary STL header
        magic_offset=0
    ),

    'ply': FormatSignature(
        name='PLY',
        extensions=['.ply'],
        is_text=True,
        text_pattern=r'^ply\s'
    ),

    'collada': FormatSignature(
        name='Collada DAE',
        extensions=['.dae'],
        is_text=True,
        text_pattern=r'^<\?xml'
    ),

    'ifc': FormatSignature(
        name=' IFC',
        extensions=['.ifc'],
        is_text=True,
        text_pattern=r'^ISO-10303'
    ),
}


# Mapeamento de extensão para formato padrão
EXTENSION_TO_FORMAT: Dict[str, List[str]] = {}
for fmt_id, sig in FORMAT_SIGNATURES.items():
    for ext in sig.extensions:
        if ext not in EXTENSION_TO_FORMAT:
            EXTENSION_TO_FORMAT[ext] = []
        EXTENSION_TO_FORMAT[ext].append(fmt_id)


# =============================================================================
# Validation Result
# =============================================================================

class ValidationStatus(Enum):
    """Status da validação."""
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    CORRUPTED = "corrupted"
    WRONG_EXTENSION = "wrong_extension"


@dataclass
class ValidationResult:
    """Resultado da validação de um arquivo."""
    filepath: str
    status: ValidationStatus
    detected_format: Optional[str] = None
    expected_formats: List[str] = None
    message: str = ""
    details: Dict = None

    def __post_init__(self):
        if self.expected_formats is None:
            self.expected_formats = []
        if self.details is None:
            self.details = {}

    @property
    def is_valid(self) -> bool:
        return self.status == ValidationStatus.VALID

    def __str__(self) -> str:
        if self.is_valid:
            return f"✓ {self.filepath} - {self.detected_format} (válido)"
        elif self.status == ValidationStatus.WRONG_EXTENSION:
            return f"✗ {self.filepath} - extensão não corresponde ao formato ({self.detected_format})"
        elif self.status == ValidationStatus.INVALID:
            return f"✗ {self.filepath} - arquivo inválido"
        elif self.status == ValidationStatus.CORRUPTED:
            return f"✗ {self.filepath} - arquivo corrompido"
        else:
            return f"? {self.filepath} - formato desconhecido"


# =============================================================================
# File Validators
# =============================================================================

class FileValidator:
    """Validador de arquivos 3D."""

    def __init__(self, strict: bool = True):
        """
        Args:
            strict: Se True, extensão deve corresponder ao formato detectado
        """
        self.strict = strict

    def validate(self, filepath: str) -> ValidationResult:
        """
        Valida um arquivo 3D.

        Args:
            filepath: Caminho do arquivo

        Returns:
            ValidationResult com o resultado
        """
        path = Path(filepath)

        if not path.exists():
            return ValidationResult(
                filepath=filepath,
                status=ValidationStatus.INVALID,
                message=f"Arquivo não encontrado: {filepath}"
            )

        if path.stat().st_size == 0:
            return ValidationResult(
                filepath=filepath,
                status=ValidationStatus.INVALID,
                message="Arquivo vazio"
            )

        extension = path.suffix.lower()
        expected_formats = EXTENSION_TO_FORMAT.get(extension, [])

        # Tenta detectar formato
        detected_format = self._detect_format(path)

        if detected_format is None:
            # Formato desconhecido
            return ValidationResult(
                filepath=filepath,
                status=ValidationStatus.UNKNOWN,
                expected_formats=expected_formats,
                message="Não foi possível determinar o formato"
            )

        # Verifica se extensão corresponde
        if extension not in FORMAT_SIGNATURES[detected_format].extensions:
            return ValidationResult(
                filepath=filepath,
                status=ValidationStatus.WRONG_EXTENSION,
                detected_format=detected_format,
                expected_formats=expected_formats,
                message=f"Extensão {extension} não corresponde ao formato {detected_format}"
            )

        # Verifica se arquivo está bem formado
        if not self._check_integrity(path, detected_format):
            return ValidationResult(
                filepath=filepath,
                status=ValidationStatus.CORRUPTED,
                detected_format=detected_format,
                expected_formats=expected_formats,
                message="Arquivo parece estar corrompido"
            )

        return ValidationResult(
            filepath=filepath,
            status=ValidationStatus.VALID,
            detected_format=detected_format,
            expected_formats=expected_formats,
            message="Arquivo válido"
        )

    def _detect_format(self, path: Path) -> Optional[str]:
        """Detecta formato pelo conteúdo."""
        try:
            # Lê os primeiros bytes para análise
            with open(path, 'rb') as f:
                header_bytes = f.read(256)

            header_text = header_bytes.decode('utf-8', errors='ignore')
            header_text_lower = header_text.lower()

            # Verifica cada formato
            for fmt_id, sig in FORMAT_SIGNATURES.items():
                if sig.magic_bytes:
                    # Binary signature check
                    if sig.magic_offset + len(sig.magic_bytes) <= len(header_bytes):
                        file_magic = header_bytes[sig.magic_offset:sig.magic_offset + len(sig.magic_bytes)]
                        if file_magic == sig.magic_bytes:
                            return fmt_id
                elif sig.is_text and sig.text_pattern:
                    # Text pattern check
                    try:
                        if re.match(sig.text_pattern, header_text, re.MULTILINE | re.IGNORECASE):
                            return fmt_id
                    except re.error:
                        continue

            # Special cases
            return self._detect_special_format(path, header_bytes, header_text)

        except Exception as e:
            print(f"Erro ao detectar formato: {e}", file=sys.stderr)
            return None

    def _detect_special_format(self, path: Path, header_bytes: bytes, header_text: str) -> Optional[str]:
        """Detecta formatos especiais que precisam de lógica adicional."""

        # .glb é binary glTF - verifica JSON header
        if path.suffix.lower() == '.glb':
            try:
                # glTF binary tem magic bytes 0x46546C67 (gLTF)
                if header_bytes[0:4] == b'glTF':
                    return 'gltf'
            except:
                pass

        # FBX pode ter diferentes magic bytes
        if path.suffix.lower() == '.fbx':
            if b'FBX' in header_bytes[:20]:
                return 'fbx'

        # STL Binary - verifica estrutura
        if path.suffix.lower() == '.stl':
            if header_text.startswith('solid'):
                # Pode ser ASCII ou binary - verifica tamanho
                if path.stat().st_size < 1000000:  # < 1MB provavelmente ASCII
                    return 'stl_ascii'
            else:
                # Binary STL
                try:
                    # Binary STL tem 80-byte header + 4-byte triangle count
                    triangle_count = struct.unpack('<I', header_bytes[80:84])[0]
                    expected_size = 84 + triangle_count * 50
                    if abs(path.stat().st_size - expected_size) < 100:
                        return 'stl_binary'
                except:
                    pass

        # 3ds Max - tenta detectar por estrutura
        if path.suffix.lower() == '.max':
            # 3ds Max files têm padrões específicos
            if 0xC0 in header_bytes or 0x3D in header_bytes:
                return '3dsmax'

        # Maya ASCII
        if path.suffix.lower() in ['.ma', '.ms']:
            # Procura indicadores Maya
            if 'maya' in header_text_lower or 'Mel' in header_text:
                return 'maya_ascii'
            # Procura versão
            if re.search(r'format\s*:\s*ascii', header_text, re.IGNORECASE):
                return 'maya_ascii'

        return None

    def _check_integrity(self, path: Path, format_id: str) -> bool:
        """
        Verifica integridade básica do arquivo.

        Returns:
            True se arquivo parece válido
        """
        try:
            if format_id == 'blender':
                return self._check_blender(path)
            elif format_id in ('fbx', 'fbx_ascii'):
                return self._check_fbx(path)
            elif format_id == 'gltf':
                return self._check_gltf(path)
            elif format_id == 'obj':
                return self._check_obj(path)
            elif format_id in ('stl_ascii', 'stl_binary'):
                return self._check_stl(path, format_id)
            elif format_id == '3ds':
                return self._check_3ds(path)
            elif format_id in ('maya_ascii', 'maya_binary'):
                return self._check_maya(path)
            elif format_id == '3dsmax':
                return self._check_3dsmax(path)
            return True  # Para formatos não verificados, assume válido

        except Exception as e:
            print(f"Erro ao verificar integridade: {e}", file=sys.stderr)
            return False

    def _check_blender(self, path: Path) -> bool:
        """Verifica integridade de arquivo Blender."""
        try:
            with open(path, 'rb') as f:
                # Verifica magic bytes
                magic = f.read(7)
                if magic != b'BLENDER':
                    return False

                # Verifica versão
                version = f.read(3)
                version_str = version.decode('ascii')
                if not version_str.isdigit():
                    return False

                return True
        except:
            return False

    def _check_fbx(self, path: Path) -> bool:
        """Verifica integridade de arquivo FBX."""
        try:
            with open(path, 'rb') as f:
                data = f.read()

            # Binary FBX
            if data[:20] == b'Kaydara FBX Binary':
                return True

            # ASCII FBX
            if data[:5] == b'; FBX':
                # Verifica parênteses balanceados
                return data.count(b'(') > 0

            return False
        except:
            return False

    def _check_gltf(self, path: Path) -> bool:
        """Verifica integridade de arquivo glTF."""
        try:
            suffix = path.suffix.lower()

            if suffix == '.glb':
                # Binary glTF - verifica estrutura
                with open(path, 'rb') as f:
                    # Header 12 bytes: magic(4) + version(4) + length(4)
                    header = f.read(12)
                    if len(header) < 12:
                        return False

                    magic = struct.unpack('<I', header[0:4])[0]
                    if magic != 0x46546C67:  # 'glTF'
                        return False

                    version = struct.unpack('<I', header[4:8])[0]
                    if version not in (1, 2):
                        return False

                    return True
            else:
                # glTF JSON - tenta parsear
                with open(path, 'r', encoding='utf-8') as f:
                    import json
                    json.load(f)
                    return True
        except:
            return False

    def _check_obj(self, path: Path) -> bool:
        """Verifica integridade de arquivo OBJ."""
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Deve ter pelo menos uma linha válida
            valid_lines = 0
            for line in lines[:100]:  # Check first 100 lines
                line = line.strip()
                if line and not line.startswith('#'):
                    if re.match(r'^[vfvntp]\s', line):
                        valid_lines += 1

            return valid_lines > 0
        except:
            return False

    def _check_stl(self, path: Path, format_id: str) -> bool:
        """Verifica integridade de arquivo STL."""
        try:
            if format_id == 'stl_ascii':
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Deve ter 'solid' e 'facet' ou 'endsolid'
                has_solid = 'solid' in content.lower()
                has_facet = 'facet' in content.lower() or 'endsolid' in content.lower()
                return has_solid and has_facet
            else:
                # Binary STL
                with open(path, 'rb') as f:
                    header = f.read(80)
                    if len(header) < 80:
                        return False

                    triangle_count = struct.unpack('<I', f.read(4))[0]
                    expected_size = 80 + 4 + triangle_count * 50

                    return abs(path.stat().st_size - expected_size) < 1000
        except:
            return False

    def _check_3ds(self, path: Path) -> bool:
        """Verifica integridade de arquivo 3DS."""
        try:
            with open(path, 'rb') as f:
                magic = f.read(2)
                return magic == b'\x4D\x4D'
        except:
            return False

    def _check_maya(self, path: Path, format_id: str) -> bool:
        """Verifica integridade de arquivo Maya."""
        try:
            with open(path, 'rb') as f:
                data = f.read(100)

            if format_id == 'maya_ascii':
                text = data.decode('utf-8', errors='ignore')
                return 'maya' in text.lower() or 'Mel' in text
            else:
                # Maya Binary
                return b'Maya Binary' in data or len(data) > 0
        except:
            return False

    def _check_3dsmax(self, path: Path) -> bool:
        """Verifica integridade de arquivo 3ds Max."""
        try:
            with open(path, 'rb') as f:
                data = f.read(256)

            # 3ds Max tem padrões reconhecíveis
            # Não há magic bytes oficiais, então fazemos check básico
            if len(data) < 4:
                return False

            # Verifica se tem bytes não-nulos
            non_null = sum(1 for b in data if b != 0)
            return non_null > 10
        except:
            return False


# =============================================================================
# Batch Validation
# =============================================================================

def validate_directory(dir_path: str, recursive: bool = True) -> List[ValidationResult]:
    """
    Valida todos os arquivos 3D em um diretório.

    Args:
        dir_path: Caminho do diretório
        recursive: Se True, busca recursivamente

    Returns:
        Lista de resultados
    """
    validator = FileValidator()
    results = []

    extensions = list(EXTENSION_TO_FORMAT.keys())
    pattern = f"**/*[{' '.join(extensions)}]" if recursive else "*[.3ds]"

    path = Path(dir_path)
    for ext in extensions:
        if recursive:
            files = list(path.rglob(f"*{ext}"))
        else:
            files = list(path.glob(f"*{ext}"))

        for filepath in files:
            result = validator.validate(str(filepath))
            results.append(result)

    return results


def print_validation_report(results: List[ValidationResult]):
    """Imprime relatório de validação."""
    valid = [r for r in results if r.is_valid]
    invalid = [r for r in results if not r.is_valid]

    print("\n" + "=" * 60)
    print("VALIDAÇÃO DE ARQUIVOS 3D")
    print("=" * 60)

    print(f"\nTotal: {len(results)} arquivos")
    print(f"  Válidos: {len(valid)}")
    print(f"  Inválidos: {len(invalid)}")

    if invalid:
        print("\n--- ARQUIVOS INVÁLIDOS ---")
        for r in invalid:
            print(f"  {r}")

    if valid:
        print("\n--- ARQUIVOS VÁLIDOS ---")
        for r in valid:
            print(f"  {r}")


# =============================================================================
# Main
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Valida arquivos 3D verificando formato e integridade"
    )
    parser.add_argument('file', nargs='?', help="Arquivo para validar")
    parser.add_argument('--check-dir', help="Validar todos arquivos em diretório")
    parser.add_argument('--recursive', action='store_true', help="Busca recursiva em diretórios")
    parser.add_argument('--strict', action='store_true', default=True, help="Extensão deve corresponder ao formato")
    parser.add_argument('--format', help="Força formato específico")
    parser.add_argument('--quiet', action='store_true', help="Saída mínima")

    args = parser.parse_args()

    validator = FileValidator(strict=args.strict)

    if args.check_dir:
        results = validate_directory(args.check_dir, recursive=args.recursive)
        print_validation_report(results)

        # Exit code baseado no resultado
        invalid = [r for r in results if not r.is_valid]
        sys.exit(0 if len(invalid) == 0 else 1)

    elif args.file:
        result = validator.validate(args.file)

        if args.quiet:
            if result.is_valid:
                print(result.filepath)
                sys.exit(0)
            else:
                sys.exit(1)

        print(result)
        sys.exit(0 if result.is_valid else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
