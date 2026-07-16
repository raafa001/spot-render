"""
Spot Render - File Format Converters

Converte arquivos Maya (.ms, .ma), 3ds Max (.max) e outros formatos 3D
para Blender (.blend) antes da renderização.

Uso:
    from converters import convert_file

    result = convert_file("input.ms", "output.blend")
    if result:
        print(f"Convertido para: {result}")
"""

from .convert import convert_to_blend, FORMAT_MAP

__all__ = ['convert_to_blend', 'FORMAT_MAP']
