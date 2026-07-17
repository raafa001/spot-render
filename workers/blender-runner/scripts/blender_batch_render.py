#!/usr/bin/env python3
"""
Spot Render - Blender Batch Render Script

Script Python para Blender que replica a lógica do MAXScript original.
Renderização em lote baseada em arquivo JSON, gerenciando Collections
(equivalente aos Layers do 3ds Max).

Funcionalidades:
- Ler arquivo JSON com configurações de renderização
- Gerenciar visibilidade de Collections (SPOTLAR_OFERTA_*, SPOTLAR_SUPORTE_*)
- Configurar câmeras, resolução e output
- Executar renderização PNG em background

Uso (Blender linha de comando):
    blender -b scene.blend --python blender_batch_render.py -- \
        --json render_config.json \
        --output /path/to/output \
        [--preview]

Uso (módulo Python):
    from blender_batch_render import BatchRenderer
    renderer = BatchRenderer()
    renderer.load_config("render_config.json")
    renderer.render_all()

Interface (dentro do Blender):
    Abra o painel Sidebar (N) > Spot Render
"""

import bpy
import json
import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class RenderItem:
    """Item de configuração de renderização."""
    short_name: str
    camera_name: str
    layer_name: str
    resolution: Tuple[int, int] = (1920, 1080)
    filename: str = ""
    render_type: str = "color"  # color, shadow, static, refraction
    render_bool: bool = True
    preview_bool: bool = False
    folder_to_use: str = ""
    dest: str = ""
    render_id: str = ""
    category: str = ""
    option_code: str = ""
    support: str = ""
    limiter: str = ""
    binding_order: str = ""


@dataclass
class SceneState:
    """Estado de cena capturado."""
    name: str
    layer_to_use: str
    modified: List[str] = field(default_factory=list)
    modified_scene: List[str] = field(default_factory=list)


# =============================================================================
# Batch Renderer Class
# =============================================================================

class BatchRenderer:
    """
    Renderer em lote para Blender - equivalente ao batchRenderMgr do 3ds Max.

    Gerencia:
    - Collections (equivalente aos Layers do 3ds Max)
    - Scene States (captura/restauro de estado)
    - Presets de renderização
    - Output organizado em pastas
    """

    def __init__(self):
        self.scene = bpy.context.scene
        self.render_items: List[RenderItem] = []
        self.collections_activated: List[str] = []
        self.modified_states: List[SceneState] = []
        self.output_base: str = "/storage/output"
        self.json_path: str = ""
        self.preview_mode: bool = False

        # Presets de renderização
        self.presets_dir = self._get_presets_dir()

    def _get_presets_dir(self) -> str:
        """Retorna diretório de presets (compatível com MAXScript)."""
        # Tenta detectar caminho similar ao 3ds Max
        blend_dir = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.getcwd()
        presets_dir = os.path.join(blend_dir, "render_presets")
        if not os.path.exists(presets_dir):
            os.makedirs(presets_dir, exist_ok=True)
        return presets_dir

    # -------------------------------------------------------------------------
    # JSON Parsing
    # -------------------------------------------------------------------------

    def load_config(self, json_path: str) -> bool:
        """
        Carrega configuração de um arquivo JSON.

        Args:
            json_path: Caminho para arquivo JSON de configuração

        Returns:
            True se carregado com sucesso
        """
        self.json_path = json_path
        if not os.path.exists(json_path):
            self._log_error(f"Arquivo JSON não encontrado: {json_path}")
            return False

        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.render_items = self._parse_json_items(data)
            self._log_info(f"Carregados {len(self.render_items)} itens de render")
            return True

        except json.JSONDecodeError as e:
            self._log_error(f"Erro ao parsear JSON: {e}")
            return False
        except Exception as e:
            self._log_error(f"Erro ao carregar configuração: {e}")
            return False

    def _parse_json_items(self, data) -> List[RenderItem]:
        """
        Converte dados JSON em lista de RenderItems.

        Espera formato JSON:
        {
            "items": [
                {
                    "short_name": "T1",
                    "camera_name": "Camera_01",
                    "layer_name": "SPOTLAR_OFERTA_T1, SPOTLAR_SUPORTE_T1",
                    "resolution": "1920x1080",
                    "filename": "T1_Camera01",
                    "render_type": "color",
                    "render_bool": true,
                    "preview_bool": false,
                    "folder_to_use": "T1",
                    "dest": "/storage/output"
                },
                ...
            ]
        }
        """
        items = []

        # Suporta both "items" array or direct array
        items_data = data.get("items", data) if isinstance(data, dict) else data

        if not isinstance(items_data, list):
            items_data = [items_data]

        for item_data in items_data:
            if not isinstance(item_data, dict):
                continue

            # Parse resolution
            res_str = item_data.get("resolution", "1920x1080")
            resolution = self._parse_resolution(res_str)

            # Parse layer_name (pode vir como string ou array)
            layer_name = item_data.get("layer_name", "")
            if isinstance(layer_name, list):
                layer_name = ", ".join(layer_name)

            # Parse output folder
            folder_to_use = item_data.get("folder_to_use", "")
            if not folder_to_use:
                # Tenta derivar do short_name ou filename
                folder_to_use = item_data.get("short_name", "")

            # Parse destination
            dest = item_data.get("dest", self.output_base)
            if not dest:
                dest = self.output_base

            item = RenderItem(
                short_name=str(item_data.get("short_name", "")),
                camera_name=str(item_data.get("camera_name", "")),
                layer_name=layer_name,
                resolution=resolution,
                filename=str(item_data.get("filename", "")),
                render_type=str(item_data.get("type", item_data.get("render_type", "color"))),
                render_bool=bool(item_data.get("render_bool", item_data.get("render", True))),
                preview_bool=bool(item_data.get("preview_bool", False)),
                folder_to_use=folder_to_use,
                dest=dest,
                render_id=str(item_data.get("render_id", "")),
                category=str(item_data.get("category", "")),
                option_code=str(item_data.get("option_code", "")),
                support=str(item_data.get("support", "")),
                limiter=str(item_data.get("limiter", "")),
                binding_order=str(item_data.get("binding_order", "")),
            )

            items.append(item)

        return items

    def _parse_resolution(self, res_str: str) -> Tuple[int, int]:
        """Parse string de resolução '1920x1080' ou '1920,1080'."""
        # Tenta formato "1920x1080"
        match = re.match(r'(\d+)[xX](\d+)', str(res_str))
        if match:
            return (int(match.group(1)), int(match.group(2)))

        # Tenta formato "1920,1080"
        match = re.match(r'(\d+),(\d+)', str(res_str))
        if match:
            return (int(match.group(1)), int(match.group(2)))

        # Default
        return (1920, 1080)

    # -------------------------------------------------------------------------
    # Collection Management (equivalent to MAXScript Layers)
    # -------------------------------------------------------------------------

    def get_collection_by_pattern(self, pattern: str) -> Optional[bpy.types.Collection]:
        """
        Busca Collection pelo padrão de nome (suporta wildcards parciais).

        Args:
            pattern: Padrão de nome (ex: "SPOTLAR_OFERTA_T1")

        Returns:
            Collection encontrada ou None
        """
        pattern_lower = pattern.lower()

        for collection in bpy.data.collections:
            if pattern_lower in collection.name.lower():
                return collection

        return None

    def get_collections_by_prefix(self, prefix: str) -> List[bpy.types.Collection]:
        """
        Retorna todas as Collections que começam com o prefixo.

        Args:
            prefix: Prefixo a buscar (ex: "SPOTLAR_OFERTA_")

        Returns:
            Lista de Collections
        """
        collections = []
        for collection in bpy.data.collections:
            if collection.name.startswith(prefix):
                collections.append(collection)
        return collections

    def hide_all_spotlar_collections(self):
        """Oculta todas as Collections SPOTLAR (equivalente ao MAXScript)."""
        for collection in bpy.data.collections:
            if collection.name.startswith("SPOTLAR"):
                collection.hide_render = True
                collection.hide_viewport = True

    def activate_collection(self, collection_name: str) -> bool:
        """
        Ativa uma Collection (torna visível no render).

        Args:
            collection_name: Nome da collection

        Returns:
            True se encontrou e ativou
        """
        collection = self.get_collection_by_pattern(collection_name)
        if collection:
            collection.hide_render = False
            collection.hide_viewport = False
            if collection_name not in self.collections_activated:
                self.collections_activated.append(collection_name)
            return True
        return False

    def process_layer_list(self, layer_name: str) -> List[str]:
        """
        Processa lista de layers do JSON (equivalente ao MAXScript).

        Formato de entrada: "layer1, (Sup) layer2, layer3_i"
        - Prefixo "(Sup)" indica que deve buscar SPOTLAR_SUPORTE_
        - Sufixo "_i" indica que é uma versão invertida

        Returns:
            Lista de nomes de layers normalizados
        """
        layer_list = []
        layers_splitted = [l.strip() for l in layer_name.split(",")]

        i = 0
        while i < len(layers_splitted):
            layer = layers_splitted[i]

            # Processa modificadores
            if layer == "(Sup)":
                # Próximo layer é suporte
                if i + 1 < len(layers_splitted):
                    next_layer = layers_splitted[i + 1]
                    if not self._is_sem_layer(next_layer):
                        sup_name = f"SPOTLAR_SUPORTE_{next_layer}"
                        layer_list.append(sup_name)
                        i += 2
                        continue
            else:
                # Layer normal ou com sufixo _i
                if self._is_inverted_layer(layer):
                    # Remove sufixo _i e adiciona como oferta
                    base_name = layer[:-2] if layer.endswith("_i") else layer
                    if not self._is_sem_layer(base_name):
                        oferta_name = f"SPOTLAR_OFERTA_{base_name}"
                        layer_list.append(oferta_name)
                        i += 1
                        continue
                else:
                    # Layer normal
                    if not self._is_sem_layer(layer):
                        oferta_name = f"SPOTLAR_OFERTA_{layer}"
                        layer_list.append(oferta_name)
                        i += 1
                        continue

            i += 1

        return layer_list

    def _is_sem_layer(self, layer_name: str) -> bool:
        """Verifica se layer começa com 'Sem' (equivalente MAXScript)."""
        return layer_name.upper().startswith("SEM")

    def _is_inverted_layer(self, layer_name: str) -> bool:
        """Verifica se layer tem sufixo _i (invertido)."""
        return layer_name.endswith("_i")

    def validate_layers(self, expected_layers: List[str]) -> bool:
        """
        Valida se todos os layers esperados foram encontrados.

        Args:
            expected_layers: Lista de layers que devem existir

        Returns:
            True se todos encontrados
        """
        all_found = True
        for layer_name in expected_layers:
            collection = self.get_collection_by_pattern(layer_name)
            if not collection:
                self._log_error(f"Layer não encontrada: {layer_name}")
                all_found = False
        return all_found

    # -------------------------------------------------------------------------
    # Scene State Management (equivalent to 3ds Max sceneStateMgr)
    # -------------------------------------------------------------------------

    def capture_scene_state(self, state_name: str) -> SceneState:
        """
        Captura estado atual da cena (equivalente ao sceneStateMgr.Capture).

        Returns:
            SceneState criado
        """
        state = SceneState(
            name=state_name,
            layer_to_use=state_name,
            modified=list(self.modified_states),
            modified_scene=[s.name for s in self.modified_states]
        )
        return state

    def find_scene_state(self, state_name: str) -> Optional[SceneState]:
        """Busca estado pelo nome."""
        for state in self.modified_states:
            if state.name == state_name:
                return state
        return None

    # -------------------------------------------------------------------------
    # Render Settings
    # -------------------------------------------------------------------------

    def setup_render(
        self,
        resolution: Tuple[int, int],
        render_type: str = "color",
        preview: bool = False
    ):
        """
        Configura parâmetros de renderização.

        Args:
            resolution: Tupla (width, height)
            render_type: Tipo de render (color, shadow, static, refraction)
            preview: Se True, usa resolução pela metade
        """
        scene = self.scene

        # Resolução
        if preview:
            scene.render.resolution_x = resolution[0] // 2
            scene.render.resolution_y = resolution[1] // 2
        else:
            scene.render.resolution_x = resolution[0]
            scene.render.resolution_y = resolution[1]

        scene.render.resolution_percentage = 100

        # Formato PNG
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.color_depth = '16'
        scene.render.use_overwrite = True
        scene.render.use_use_placeholders = False

        # Engine de render
        if render_type == "refraction":
            # Refraction precisa de mais samples
            scene.render.engine = 'CYCLES'
            scene.cycles.samples = 256
            scene.cycles.use_denoising = True
        elif render_type in ("shadow", "static"):
            scene.render.engine = 'CYCLES'
            scene.cycles.samples = 128
            scene.cycles.use_denoising = True
        else:
            # Color normal
            scene.render.engine = 'BLENDER_EE'
            scene.eevee.use_gtao = True
            scene.eevee.use_shadows = True

        # Audio (desabilita para não travar)
        scene.render.use_audio = False

    def set_camera(self, camera_name: str) -> bool:
        """
        Define câmera ativa pela nome.

        Args:
            camera_name: Nome da câmera

        Returns:
            True se câmera encontrada e definida
        """
        camera = self.get_collection_by_pattern(camera_name)

        # Se não encontrou como collection, tenta como Object
        if not camera:
            camera = bpy.data.objects.get(camera_name)

        if camera:
            if hasattr(camera, 'data') and camera.type == 'CAMERA':
                # É uma câmera
                self.scene.camera = camera
            else:
                # Tenta encontrar câmera dentro de uma collection
                for obj in bpy.data.objects:
                    if obj.type == 'CAMERA' and camera_name.lower() in obj.name.lower():
                        self.scene.camera = obj
                        return True
                return False
            return True

        self._log_error(f"Câmera não encontrada: {camera_name}")
        return False

    def set_output_path(self, output_path: str):
        """Define caminho de output para renderização."""
        self.scene.render.filepath = output_path

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render_single(
        self,
        item: RenderItem,
        create_batch: bool = True
    ) -> bool:
        """
        Renderiza um único item.

        Args:
            item: RenderItem com configurações
            create_batch: Se True, cria batch (similar ao MAXScript)

        Returns:
            True se renderizado com sucesso
        """
        # 1. Processar layers
        layer_list = self.process_layer_list(item.layer_name)

        if not layer_list:
            self._log_error(f"Nenhum layer para renderizar: {item.short_name}")
            return False

        # 2. Validar layers
        if not self.validate_layers(layer_list):
            self._log_warning(f"Alguns layers não foram encontrados para {item.short_name}")

        # 3. Ocultar todos os SPOTLAR primeiro
        self.hide_all_spotlar_collections()

        # 4. Ativar layers necessários
        for layer_name in layer_list:
            self.activate_collection(layer_name)

        # 5. Configurar câmera
        if item.camera_name:
            self.set_camera(item.camera_name)

        # 6. Configurar render
        self.setup_render(
            resolution=item.resolution,
            render_type=item.render_type,
            preview=item.preview_bool
        )

        # 7. Preparar output
        output_dir = os.path.join(item.dest, item.folder_to_use)
        os.makedirs(output_dir, exist_ok=True)

        output_file = os.path.join(output_dir, f"{item.filename}.png")
        self.set_output_path(output_file)

        # 8. Renderizar
        self._log_info(f"Renderizando: {item.filename}")
        self._log_info(f"  Camera: {item.camera_name}")
        self._log_info(f"  Layers: {', '.join(layer_list)}")
        self._log_info(f"  Resolution: {item.resolution[0]}x{item.resolution[1]}")
        self._log_info(f"  Output: {output_file}")

        try:
            bpy.ops.render.render(write_still=True)
            self._log_info(f"  OK: {output_file}")
            return True
        except Exception as e:
            self._log_error(f"Erro na renderização: {e}")
            return False

    def render_all(self, output_base: Optional[str] = None) -> Dict[str, bool]:
        """
        Renderiza todos os itens do JSON.

        Args:
            output_base: Diretório base de output (sobrescreve JSON)

        Returns:
            Dict com filename -> success
        """
        results = {}

        if output_base:
            self.output_base = output_base

        # Atualiza dest de todos os itens
        for item in self.render_items:
            if output_base:
                item.dest = output_base

        # Limpa scene states
        self.modified_states.clear()

        # Renderiza cada item
        for item in self.render_items:
            if not item.render_bool:
                self._log_info(f"Pulando (render_bool=False): {item.filename}")
                results[item.filename] = True
                continue

            success = self.render_single(item)
            results[item.filename] = success

        # Sumário
        success_count = sum(1 for v in results.values() if v)
        self._log_info(f"\n{'='*50}")
        self._log_info(f"Renderização concluída: {success_count}/{len(results)} sucessos")
        self._log_info(f"{'='*50}")

        return results

    # -------------------------------------------------------------------------
    # Logging Helpers
    # -------------------------------------------------------------------------

    def _log_info(self, msg: str):
        print(f"[INFO] {msg}")

    def _log_warning(self, msg: str):
        print(f"[WARN] {msg}")

    def _log_error(self, msg: str):
        print(f"[ERROR] {msg}", file=sys.stderr)


# =============================================================================
# Blender UI Panel
# =============================================================================

class SPOTRENDER_PT_panel:
    """Painel Spot Render na Sidebar do Blender."""

    bl_label = "Spot Render"
    bl_idname = "SPOTRENDER_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Spot Render"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        sr_props = scene.spot_render_properties

        # Seção: Configuração JSON
        box = layout.box()
        box.label(text="Configuração:", icon='FILE')
        box.prop(sr_props, "json_path", text="JSON")
        box.prop(sr_props, "output_path", text="Output")

        # Seção: Opções
        box = layout.box()
        box.label(text="Opções:", icon='SETTINGS')
        box.prop(sr_props, "preview_mode")

        # Seção: Ações
        box = layout.box()
        box.label(text="Ações:", icon='PLAY')
        row = box.row()
        row.operator("spotrender.load_json", text="Carregar JSON", icon='FILE')
        row = box.row()
        row.operator("spotrender.render_all", text="Renderizar Tudo", icon='RENDER_ANIMATION')
        row = box.row()
        row.operator("spotrender.generate_sup_layers", text="Gerar Suportes", icon='ADD')


class SPOTRENDER_OT_load_json(bpy.types.Operator):
    """Carrega configuração do arquivo JSON."""
    bl_idname = "spotrender.load_json"
    bl_label = "Carregar JSON"

    def execute(self, context):
        scene = context.scene
        sr_props = scene.spot_render_properties

        if not sr_props.json_path:
            self.report({'ERROR'}, "Selecione um arquivo JSON")
            return {'CANCELLED'}

        renderer = BatchRenderer()
        if renderer.load_config(sr_props.json_path):
            # Atualiza output base
            if renderer.render_items:
                sr_props.output_path = renderer.render_items[0].dest
            self.report({'INFO'}, f"Carregados {len(renderer.render_items)} itens")
        else:
            self.report({'ERROR'}, "Erro ao carregar JSON")

        return {'FINISHED'}


class SPOTRENDER_OT_render_all(bpy.types.Operator):
    """Renderiza todos os itens."""
    bl_idname = "spotrender.render_all"
    bl_label = "Renderizar Tudo"

    def execute(self, context):
        scene = context.scene
        sr_props = scene.spot_render_properties

        if not sr_props.json_path:
            self.report({'ERROR'}, "Carregue um JSON primeiro")
            return {'CANCELLED'}

        renderer = BatchRenderer()
        renderer.load_config(sr_props.json_path)

        if sr_props.output_path:
            results = renderer.render_all(sr_props.output_path)
        else:
            results = renderer.render_all()

        success = sum(1 for v in results.values() if v)
        self.report({'INFO'}, f"Concluído: {success}/{len(results)} renderizados")

        return {'FINISHED'}


class SPOTRENDER_OT_generate_sup_layers(bpy.types.Operator):
    """Gera layers de suporte (equivalente MAXScript generate_sup_layers)."""
    bl_idname = "spotrender.generate_sup_layers"
    bl_label = "Gerar Suportes"

    def execute(self, context):
        # Implementar lógica de gerar suporte se necessário
        self.report({'INFO'}, "Funcionalidade de gerar suporte")
        return {'FINISHED'}


class SpotRenderProperties(bpy.types.PropertyGroup):
    """Propriedades do Spot Render."""
    json_path: bpy.props.StringProperty(
        name="JSON Path",
        description="Caminho para arquivo JSON de configuração",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    output_path: bpy.props.StringProperty(
        name="Output Path",
        description="Diretório base de output",
        default="/storage/output",
        maxlen=1024,
        subtype='DIR_PATH'
    )
    preview_mode: bpy.props.BoolProperty(
        name="Preview Mode",
        description="Usar resolução pela metade",
        default=False
    )


def register_properties():
    """Registra propriedades no Blender."""
    bpy.utils.register_class(SpotRenderProperties)
    bpy.types.Scene.spot_render_properties = bpy.props.PointerProperty(
        type=SpotRenderProperties
    )


def unregister_properties():
    """Remove propriedades do Blender."""
    del bpy.types.Scene.spot_render_properties
    bpy.utils.unregister_class(SpotRenderProperties)


# =============================================================================
# Main Entry Point (Command Line)
# =============================================================================

def main():
    """Ponto de entrada principal para execução via linha de comando."""

    # Parse argumentos
    args = [a for a in sys.argv if a.startswith('--')]
    kwargs = {}

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == '--json' and i + 1 < len(args):
            kwargs['json_path'] = args[i + 1]
            i += 2
        elif arg == '--output' and i + 1 < len(args):
            kwargs['output_path'] = args[i + 1]
            i += 2
        elif arg == '--preview':
            kwargs['preview'] = True
            i += 1
        elif arg == '--':
            i += 1
        else:
            i += 1

    json_path = kwargs.get('json_path', '')
    output_path = kwargs.get('output_path', '/storage/output')
    preview = kwargs.get('preview', False)

    if not json_path:
        print("Uso: blender -b scene.blend --python blender_batch_render.py -- \\")
        print("         --json render_config.json \\")
        print("         --output /path/to/output \\")
        print("         [--preview]")
        sys.exit(1)

    # Criar renderer e executar
    renderer = BatchRenderer()

    if not renderer.load_config(json_path):
        print(f"ERRO: Falha ao carregar {json_path}")
        sys.exit(1)

    # Sobrescreve output se fornecido
    if output_path:
        for item in renderer.render_items:
            item.dest = output_path

    # Renderiza todos
    results = renderer.render_all()

    # Exit code baseado no sucesso
    success_count = sum(1 for v in results.values() if v)
    if success_count == len(results):
        sys.exit(0)
    elif success_count > 0:
        sys.exit(2)  # Parcial
    else:
        sys.exit(1)  # Totalmente falhou


if __name__ == '__main__':
    main()
