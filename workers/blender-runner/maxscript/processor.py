#!/usr/bin/env python3
"""
Spot Render - MAXScript Processor

Processa arquivos MAXScript e renderlists para criar renderizações no Blender.
Faz a ponte entre o fluxo 3ds Max original e o Blender.

Fluxo:
1. Recebe arquivo .ms (MAXScript) e renderlist Excel
2. Converte/interpreta para lógica Blender
3. Cria cena no Blender via Python
4. Renderiza e salva output

Uso:
    python -m maxscript.processor input.ms renderlist.xlsx output_dir
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any

# Tentativas de import
try:
    import zipfile
    import xml.etree.ElementTree as ET
    HAS_EXCEL = True
except ImportError:
    HAS_EXCEL = False


# =============================================================================
# MAXScript Analyzer
# =============================================================================

def analyze_maxscript(filepath: str) -> Dict[str, Any]:
    """
    Analisa arquivo MAXScript e extrai configurações relevantes.

    Retorna:
        Dict com configurações extraídas
    """
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().replace('\r', '')

    config = {
        'has_batch_render': 'batchRenderMgr' in content,
        'has_scene_states': 'sceneStateMgr' in content,
        'has_layers': 'LayerManager' in content,
        'has_presets': '.rps' in content,
        'preset_types': extract_preset_types(content),
        'render_resolution': extract_resolution(content),
        'project_name': extract_project_name(filepath),
    }

    return config


def extract_preset_types(content: str) -> List[str]:
    """Extrai tipos de preset mencionados no script."""
    import re
    presets = set()

    # Procura padrões como "color_preview.rps", "shadow.rps", etc
    matches = re.findall(r'(\w+)\.rps', content)
    for m in matches:
        if 'preview' in m.lower():
            preset_type = m.replace('_preview', '').lower()
        else:
            preset_type = m.lower()
        presets.add(preset_type)

    return list(presets)


def extract_resolution(content: str) -> Optional[tuple]:
    """Extrai resolução do script sehardcoded."""
    import re
    match = re.search(r'(\d+)\s*x\s*(\d+)', content)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return None


def extract_project_name(filepath: str) -> str:
    """Extrai nome do projeto do nome do arquivo."""
    return Path(filepath).stem


# =============================================================================
# Renderlist Reader (Excel)
# =============================================================================

class RenderlistReader:
    """Lê renderlists em formato Excel (.xlsx)."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data: List[Dict] = []

    def read(self) -> List[Dict]:
        """Lê e parseia a renderlist."""
        if not HAS_EXCEL:
            raise ImportError("zipfile e xml.etree são necessários para ler Excel")

        with zipfile.ZipFile(self.filepath, 'r') as z:
            # Ler shared strings
            with z.open('xl/sharedStrings.xml') as f:
                strings_tree = ET.parse(f).getroot()
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                strings = []
                for si in strings_tree.findall('.//ns:si', ns):
                    text = ''.join(t.text or '' for t in si.findall('.//ns:t', ns))
                    strings.append(text)

            # Ler sheet1
            with z.open('xl/worksheets/sheet1.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

                rows = root.findall('.//ns:row', ns)

                # Header
                headers = {}
                if rows:
                    for cell in rows[0].findall('ns:c', ns):
                        v = cell.find('ns:v', ns)
                        ref = cell.get('r', '')
                        col_match = ref and __import__('re').match(r'([A-Z]+)', ref)
                        if col_match and v is not None:
                            headers[col_match.group(1)] = v.text

                # Data
                for row in rows[1:]:
                    cells = row.findall('ns:c', ns)
                    row_data = {}
                    for cell in cells:
                        v = cell.find('ns:v', ns)
                        t = cell.get('t', '')
                        ref = cell.get('r', '')
                        col_match = ref and __import__('re').match(r'([A-Z]+)', ref)
                        if col_match:
                            col = col_match.group(1)
                            if t == 's' and v is not None:
                                try:
                                    idx = int(v.text)
                                    row_data[col] = strings[idx] if idx < len(strings) else ''
                                except:
                                    row_data[col] = ''
                            elif v is not None:
                                row_data[col] = v.text
                            else:
                                row_data[col] = ''

                    if row_data:
                        self.data.append(row_data)

        return self.data

    def get_render_config(self) -> List[Dict]:
        """
        Converte renderlist em configurações de render.

        Retorna lista de dicts com:
            - code: código do item
            - name: nome amigável
            - category: categoria
            - is_renderable: se deve renderizar
        """
        config = []

        for row in self.data:
            # Pula linhas sem código
            code = row.get('A', '')
            if not code:
                continue

            category = row.get('B', '')

            # Se é header de categoria, extrai info
            if category.startswith('CATEGORY:'):
                parts = category.replace('CATEGORY:', '').split(';')
                if len(parts) >= 2:
                    cat_name = parts[0]
                    subcat = parts[1].replace('SUBCATEGORY:', '')
                else:
                    cat_name = parts[0]
                    subcat = parts[0]

                config.append({
                    'code': code,
                    'name': subcat,
                    'category': cat_name,
                    'short_name': subcat,
                    'is_renderable': row.get('G', '0') == '1',
                    'layer_name': f"SPOTLAR_{code}",
                })

        return config


# =============================================================================
# Blender Scene Generator
# =============================================================================

def generate_blender_scene_script(
    project_name: str,
    render_config: List[Dict],
    maxscript_config: Dict,
    output_base: str
) -> str:
    """
    Gera script Python para criar cena no Blender.

    Args:
        project_name: Nome do projeto
        render_config: Configurações de render da planilha
        maxscript_config: Configurações extraídas do MAXScript
        output_base: Diretório base de output

    Returns:
        Script Python para Blender
    """
    preset_types = maxscript_config.get('preset_types', ['color'])
    resolution = maxscript_config.get('render_resolution', (1920, 1080))

    script = f'''#!/usr/bin/env python3
"""
Spot Render - Blender Scene Generator
Gerado automaticamente para projeto: {project_name}
"""

import bpy
import math
import os
import sys

# Limpa cena atual
print("Limpando cena...")
bpy.ops.wm.read_factory_settings(use_empty=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj)

# Configurações
PROJECT_NAME = "{project_name}"
OUTPUT_BASE = "{output_base}"
RESOLUTION_X = {resolution[0] if resolution else 1920}
RESOLUTION_Y = {resolution[1] if resolution else 1080}

print(f"Projeto: {{PROJECT_NAME}}")
print(f"Output: {{OUTPUT_BASE}}")
print(f"Resolução: {{RESOLUTION_X}}x{{RESOLUTION_Y}}")

# Criar coleção principal
main_collection = bpy.data.collections.new(PROJECT_NAME)
bpy.context.scene.collection.children.link(main_collection)

# Processar render config
render_items = {json.dumps(render_config, indent=2, ensure_ascii=False)}

print(f"Render items: {{len(render_items)}}")

# Para cada item, criar estrutura de renderização
for item in render_items:
    code = item.get('code', '')
    name = item.get('name', 'Unnamed')
    category = item.get('category', '')
    layer_name = item.get('layer_name', f'Layer_{{code}}')
    is_renderable = item.get('is_renderable', False)

    print(f"Processando: {{code}} - {{name}}")

    # Criar layer/collection para o item
    item_collection = bpy.data.collections.new(f"{{PROJECT_NAME}}_{{code}}")
    main_collection.children.link(item_collection)

    # Criar câmera para o item
    cam_name = f"Camera_{{code}}"
    bpy.ops.object.camera_add(location=(0, -10, 5))
    camera = bpy.context.active_object
    camera.name = cam_name
    camera.rotation_euler = (math.radians(75), 0, 0)
    camera.data.lens = 50
    item_collection.objects.link(camera)

    # Criar luz básica se não existir
    if "MainLight" not in bpy.data.objects:
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 10))
        light = bpy.context.active_object
        light.name = "MainLight"
        light.data.energy = 2
        main_collection.objects.link(light)

print("Cena criada com sucesso!")
'''

    return script


# =============================================================================
# Main Processor
# =============================================================================

def process(
    maxscript_file: str,
    renderlist_file: Optional[str],
    output_dir: str,
    blender_path: str = "/opt/blender/blender"
) -> bool:
    """
    Processa MAXScript e renderlist, cria cena no Blender e renderiza.

    Args:
        maxscript_file: Arquivo .ms (MAXScript)
        renderlist_file: Arquivo .xlsx (renderlist) ou None
        output_dir: Diretório para outputs
        blender_path: Caminho do executável Blender

    Returns:
        True se processado com sucesso
    """
    print("=" * 60)
    print("Spot Render - MAXScript Processor")
    print("=" * 60)

    # 1. Analisa MAXScript
    print(f"\n[1] Analisando MAXScript: {maxscript_file}")
    maxscript_config = analyze_maxscript(maxscript_file)
    print(f"    - Batch render: {maxscript_config['has_batch_render']}")
    print(f"    - Scene states: {maxscript_config['has_scene_states']}")
    print(f"    - Presets: {maxscript_config['preset_types']}")

    # 2. Lê renderlist se disponível
    render_config = []
    if renderlist_file and os.path.exists(renderlist_file):
        print(f"\n[2] Lendo renderlist: {renderlist_file}")
        reader = RenderlistReader(renderlist_file)
        reader.read()
        render_config = reader.get_render_config()
        print(f"    - Itens encontrados: {len(render_config)}")

    # 3. Gera script Blender
    print(f"\n[3] Gerando script Blender...")
    blender_script = generate_blender_scene_script(
        project_name=maxscript_config['project_name'],
        render_config=render_config,
        maxscript_config=maxscript_config,
        output_base=output_dir
    )

    # Salva script temporário
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(blender_script)
        script_path = f.name

    print(f"    - Script: {script_path}")

    # 4. Executa Blender para criar cena
    print(f"\n[4] Criando cena no Blender...")
    result = subprocess.run(
        [blender_path, '--background', '--python', script_path],
        capture_output=True,
        text=True,
        timeout=300
    )

    if result.returncode != 0:
        print(f"    ERRO: {result.stderr[-500:]}")
        return False

    print("    Cena criada com sucesso!")

    # 5. Cleanup
    os.unlink(script_path)

    print("\n" + "=" * 60)
    print("Processamento concluído!")
    print("=" * 60)

    return True


def main():
    if len(sys.argv) < 2:
        print("""
Spot Render - MAXScript Processor

Processa arquivos MAXScript (.ms) e renderlists Excel para Blender.

Uso:
    python processor.py <maxscript.ms> [renderlist.xlsx] [output_dir]

Exemplo:
    python processor.py main.ms T1.xlsx /storage/output
""")
        sys.exit(1)

    maxscript_file = sys.argv[1]
    renderlist_file = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].endswith('.xlsx') else None
    output_dir = sys.argv[-1] if len(sys.argv) > 2 else '/storage/output'

    if not os.path.exists(maxscript_file):
        print(f"ERRO: Arquivo não encontrado: {maxscript_file}")
        sys.exit(1)

    success = process(maxscript_file, renderlist_file, output_dir)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
