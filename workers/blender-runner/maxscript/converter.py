#!/usr/bin/env python3
"""
Spot Render - MAXScript to Blender Converter

Converte scripts MAXScript (.ms) do 3ds Max para Python do Blender.
Analisa a lógica do MAXScript e gera código equivalente para Blender.

Estrutura:
1. Parser para MAXScript
2. Analisador de lógica (layers, cameras, render)
3. Gerador de script Blender Python

Uso:
    python -m maxscript.converter input.ms output_blender_script.py
"""

import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class MaxscriptFunction:
    """Representa uma função MAXScript."""
    name: str
    params: List[str]
    body: str
    start_line: int
    end_line: int


@dataclass
class LayerInfo:
    """Informações de um layer."""
    name: str
    visible: bool = True
    parent: Optional[str] = None
    objects: List[str] = field(default_factory=list)


@dataclass
class CameraInfo:
    """Informações de uma câmera."""
    name: str
    type: str = "Perspective"  # Perspective ou Orthographic
    location: tuple = (0, 0, 0)
    rotation: tuple = (0, 0, 0)
    fov: float = 50.0


@dataclass
class RenderItem:
    """Item de renderização."""
    short_name: str
    camera_name: str
    layer_name: str
    resolution: tuple  # (width, height)
    output_path: str
    render_type: str  # color, shadow, static, refraction
    is_preview: bool = False


@dataclass
class SceneConfig:
    """Configuração da cena extraída do MAXScript."""
    project_name: str = "SpotRender"
    layers: Dict[str, LayerInfo] = field(default_factory=dict)
    cameras: Dict[str, CameraInfo] = field(default_factory=dict)
    render_items: List[RenderItem] = field(default_factory=list)
    base_output_dir: str = "/storage/output"


# =============================================================================
# MAXScript Parser
# =============================================================================

class MaxscriptParser:
    """Parser para arquivos MAXScript."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.content = ""
        self.lines: List[str] = []
        self.functions: Dict[str, MaxscriptFunction] = {}
        self.variables: Dict[str, Any] = {}
        self.scene_config = SceneConfig()

    def parse(self) -> SceneConfig:
        """Faz o parsing completo do arquivo."""
        self._read_file()
        self._extract_functions()
        self._analyze_logic()
        return self.scene_config

    def _read_file(self):
        """Lê o arquivo MAXScript."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            # Remove ^M (carriage return do Windows)
            self.content = f.read().replace('\r', '')
        self.lines = self.content.split('\n')

    def _extract_functions(self):
        """Extrai todas as funções do MAXScript."""
        current_function: Optional[MaxscriptFunction] = None
        current_body: List[str] = []
        brace_count = 0

        for i, line in enumerate(self.lines, 1):
            # Detecta início de função
            fn_match = re.match(r'fn\s+(\w+)\s*(.*?)\s*=\s*\(', line)
            if fn_match and brace_count == 0:
                if current_function:
                    current_function.body = '\n'.join(current_body)
                    current_function.end_line = i - 1
                    self.functions[current_function.name] = current_function

                func_name = fn_match.group(1)
                func_params = fn_match.group(2).strip()
                current_function = MaxscriptFunction(
                    name=func_name,
                    params=self._parse_params(func_params),
                    body="",
                    start_line=i,
                    end_line=0
                )
                current_body = []
                brace_count = 1
                continue

            # Conta braces
            if current_function:
                brace_count += line.count('(') - line.count(')')
                current_body.append(line)

                if brace_count <= 0:
                    current_function.body = '\n'.join(current_body)
                    current_function.end_line = i
                    self.functions[current_function.name] = current_function
                    current_function = None
                    brace_count = 0

        # Última função
        if current_function:
            current_function.body = '\n'.join(current_body)
            current_function.end_line = len(self.lines)
            self.functions[current_function.name] = current_function

    def _parse_params(self, params_str: str) -> List[str]:
        """Extrai parâmetros de uma função."""
        params = []
        for p in params_str.split():
            p = p.strip().replace('=', '').replace(',', '')
            if p:
                params.append(p)
        return params

    def _analyze_logic(self):
        """Analisa a lógica do MAXScript."""
        # Analisa create_batch_render
        if 'create_batch_render' in self.functions:
            self._analyze_create_batch_render()

        # Analisa create_scene
        if 'create_scene' in self.functions:
            self._analyze_create_scene()

        # Analisa extract_variables
        if 'extract_variables' in self.functions:
            self._analyze_extract_variables()

    def _analyze_create_batch_render(self):
        """Analisa a função create_batch_render."""
        fn = self.functions['create_batch_render']
        body = fn.body

        # Extrai lógica de output
        if 'outputFilename' in body or 'outputbatch' in body:
            self.scene_config.base_output_dir = "/storage/output"

    def _analyze_create_scene(self):
        """Analisa a função create_scene."""
        fn = self.functions['create_scene']
        body = fn.body

        # Extrai nomes de layers do padrão SPOTLAR_*
        layer_matches = re.findall(r'"(SPOTLAR_[^"]+)"', body)
        for layer_name in set(layer_matches):
            if layer_name not in self.scene_config.layers:
                self.scene_config.layers[layer_name] = LayerInfo(name=layer_name)

    def _analyze_extract_variables(self):
        """Analisa a função extract_variables."""
        fn = self.functions['extract_variables']
        body = fn.body

        # Identifica variáveis extraídas
        if 'resolution' in body:
            # Padrão de resolução
            res_match = re.search(r'(\d+)x(\d+)', body)
            if res_match:
                pass  # Resolução vem da planilha

    def get_function(self, name: str) -> Optional[MaxscriptFunction]:
        """Retorna uma função pelo nome."""
        return self.functions.get(name)


# =============================================================================
# Renderlist Parser (Excel)
# =============================================================================

class RenderlistParser:
    """Parser para renderlists Excel."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.items: List[Dict] = []

    def parse(self) -> List[Dict]:
        """Faz parsing da renderlist Excel."""
        import zipfile
        import xml.etree.ElementTree as ET

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

                for row in rows[1:]:  # Pula header
                    cells = row.findall('ns:c', ns)
                    row_data = {}
                    for cell in cells:
                        v = cell.find('ns:v', ns)
                        t = cell.get('t', '')
                        ref = cell.get('r', '')
                        col = re.match(r'([A-Z]+)', ref)
                        if col and v is not None:
                            col_name = col.group(1)
                            if t == 's':
                                idx = int(v.text)
                                row_data[col_name] = strings[idx] if idx < len(strings) else ''
                            else:
                                row_data[col_name] = v.text
                            row_data[col_name] = v.text if v is not None else ''

                    if row_data:
                        self.items.append(row_data)

        return self.items

    def get_render_items(self) -> List[RenderItem]:
        """Converte para RenderItems."""
        items = []
        for row in self.items:
            # Extrai code
            code = row.get('A', '')
            if not code:
                continue

            # Verifica se é renderable
            is_renderable = row.get('G', '0') == '1'

            # Extrai category
            category = row.get('B', '')

            # Se começa com CATEGORY:, é um header
            if category.startswith('CATEGORY:'):
                # Extrai short_name e layer do category
                cat_parts = category.replace('CATEGORY:', '').split(';')
                if len(cat_parts) >= 2:
                    subcat = cat_parts[1].replace('SUBCATEGORY:', '')
                    items.append(RenderItem(
                        short_name=subcat,
                        camera_name=f"Camera_{code}",
                        layer_name=f"Layer_{code}",
                        resolution=(1920, 1080),
                        output_path=f"/storage/output/{code}",
                        render_type="color",
                        is_preview=False
                    ))

        return items


# =============================================================================
# Blender Script Generator
# =============================================================================

class BlenderScriptGenerator:
    """Gera scripts Python para Blender."""

    def __init__(self, scene_config: SceneConfig):
        self.scene_config = scene_config

    def generate(self) -> str:
        """Gera o script Blender completo."""
        lines = [
            "#!/usr/bin/env python3",
            "\"\"\"",
            "Spot Render - Blender Scene Generator",
            "Script gerado automaticamente para renderização.",
            "\"\"\"",
            "",
            "import bpy",
            "import math",
            "import os",
            "from typing import List, Dict",
            "",
            "",
            "# Configurações",
            f"PROJECT_NAME = \"{self.scene_config.project_name}\"",
            f"OUTPUT_BASE = \"{self.scene_config.base_output_dir}\"",
            "",
            "",
            "def clear_scene():",
            '    \"\"\"Limpa todos os objetos da cena.\"\"\"',
            "    # Remove todos os objetos",
            "    bpy.ops.object.select_all(action='SELECT')",
            "    bpy.ops.object.delete(use_global=False)",
            "",
            "    # Limpa dados não utilizados",
            "    for block in bpy.data.meshes:",
            "        if block.users == 0:",
            "            bpy.data.meshes.remove(block)",
            "    for block in bpy.data.materials:",
            "        if block.users == 0:",
            "            bpy.data.materials.remove(block)",
            "    for block in bpy.data.cameras:",
            "        if block.users == 0:",
            "            bpy.data.cameras.remove(block)",
            "    for block in bpy.data.images:",
            "        if block.users == 0:",
            "            bpy.data.images.remove(block)",
            "",
        ]

        # Adiciona geração de layers
        lines.extend(self._generate_layers())

        # Adiciona geração de cameras
        lines.extend(self._generate_cameras())

        # Adiciona renderização
        lines.extend(self._generate_render_setup())

        return '\n'.join(lines)

    def _generate_layers(self) -> List[str]:
        """Gera código para criar layers."""
        lines = [
            "",
            "def create_layers() -> Dict[str, bpy.types.Object]:",
            '    """Cria layers para o projeto.\"\"\"',
            "    layers = {}",
        ]

        for layer_name, layer_info in self.scene_config.layers.items():
            safe_name = layer_name.replace('SPOTLAR_', '').lower()
            lines.append(f"    # {layer_name}")
            lines.append(f"    layers['{layer_name}'] = bpy.data.objects.new('{safe_name}', None)")
            lines.append(f"    bpy.context.collection.objects.link(layers['{layer_name}'])")

            if not layer_info.visible:
                lines.append(f"    layers['{layer_name}'].hide_viewport = True")
                lines.append(f"    layers['{layer_name}'].hide_render = True")

        lines.append("    return layers")
        return lines

    def _generate_cameras(self) -> List[str]:
        """Gera código para criar câmeras."""
        lines = [
            "",
            "def create_cameras() -> Dict[str, bpy.types.Object]:",
            '    """Cria câmeras para o projeto.\"\"\"',
            "    cameras = {}",
        ]

        if not self.scene_config.cameras:
            # Câmera padrão
            lines.extend([
                "    # Câmera padrão",
                "    bpy.ops.object.camera_add(location=(0, -10, 5))",
                "    camera = bpy.context.active_object",
                "    camera.name = 'Camera_Main'",
                "    camera.rotation_euler = (math.radians(75), 0, 0)",
                "    bpy.context.scene.camera = camera",
                "    cameras['Main'] = camera",
            ])
        else:
            for cam_name, cam_info in self.scene_config.cameras.items():
                lines.append(f"    # {cam_name}")
                lines.append(f"    bpy.ops.object.camera_add(location={cam_info.location})")
                lines.append(f"    camera = bpy.context.active_object")
                lines.append(f"    camera.name = '{cam_name}'")
                if cam_info.fov:
                    lines.append(f"    camera.data.lens = {cam_info.fov}")
                lines.append(f"    cameras['{cam_name}'] = camera")

        lines.append("    return cameras")
        return lines

    def _generate_render_setup(self) -> List[str]:
        """Gera código para configurar renderização."""
        lines = [
            "",
            "def setup_render_settings(resolution_x=1920, resolution_y=1080, engine='CYCLES'):",
            '    """Configura settings de renderização.\"\"\"',
            "    scene = bpy.context.scene",
            "    scene.render.engine = engine",
            "    scene.render.resolution_x = resolution_x",
            "    scene.render.resolution_y = resolution_y",
            "    scene.render.resolution_percentage = 100",
            "    scene.render.film_transparent = False",
            "    scene.cycles.device = 'CPU'",
            "    scene.cycles.samples = 128",
            "    scene.cycles.use_denoising = True",
            "    return scene",
            "",
            "",
            "def render_scene(camera_name, output_path, layers=None):",
            '    """Renderiza a cena com a câmera especificada.\"\"\"',
            "    scene = bpy.context.scene",
            "    ",
            "    # Seleciona câmera",
            "    if camera_name in bpy.data.objects:",
            "        scene.camera = bpy.data.objects[camera_name]",
            "    ",
            "    # Configura layers",
            "    if layers:",
            "        for layer_name, layer_obj in layers.items():",
            "            layer_obj.hide_render = layer_name not in layers",
            "    ",
            "    # Configura output",
            "    scene.render.filepath = output_path",
            "    scene.render.image_settings.file_format = 'PNG'",
            "    scene.render.use_overwrite = True",
            "    ",
            "    # Renderiza",
            "    bpy.ops.render.render(write_still=True)",
            "",
        ]
        return lines


# =============================================================================
# Main
# =============================================================================

def main():
    if len(sys.argv) < 3:
        print("Uso: converter.py <arquivo.ms> <script_saida.py>")
        print("     converter.py <arquivo.ms> <planilha.xlsx> <script_saida.py>")
        sys.exit(1)

    input_file = sys.argv[-2]
    output_file = sys.argv[-1]

    # Parser MAXScript
    print(f"Analisando: {input_file}")
    parser = MaxscriptParser(input_file)
    scene_config = parser.parse()

    print(f"Funções encontradas: {list(parser.functions.keys())}")
    print(f"Layers encontrados: {list(scene_config.layers.keys())}")

    # Parser renderlist se fornecida
    if len(sys.argv) > 3:
        renderlist_file = sys.argv[-2]
        if renderlist_file.endswith('.xlsx'):
            print(f"Analisando renderlist: {renderlist_file}")
            rl_parser = RenderlistParser(renderlist_file)
            rl_parser.parse()
            render_items = rl_parser.get_render_items()
            print(f"Items de render: {len(render_items)}")

    # Gerar script Blender
    generator = BlenderScriptGenerator(scene_config)
    blender_script = generator.generate()

    # Salvar
    with open(output_file, 'w') as f:
        f.write(blender_script)

    print(f"Script gerado: {output_file}")


if __name__ == '__main__':
    main()
