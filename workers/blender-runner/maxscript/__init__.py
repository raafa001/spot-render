"""
Spot Render - MAXScript Processing Module

Converte scripts MAXScript do 3ds Max para renderização no Blender.
 suporta:
- MAXScript (.ms) - análise de lógica
- Renderlists Excel (.xlsx) - configuração de render
- Geração de scripts Blender Python

Uso:
    from maxscript.processor import process
    from maxscript.converter import MaxscriptParser

    # Ou via linha de comando:
    python -m maxscript.processor main.ms renderlist.xlsx output/
"""

from .converter import MaxscriptParser, RenderlistParser, BlenderScriptGenerator
from .processor import process, RenderlistReader, analyze_maxscript

__all__ = [
    'MaxscriptParser',
    'RenderlistParser',
    'BlenderScriptGenerator',
    'process',
    'RenderlistReader',
    'analyze_maxscript',
]
