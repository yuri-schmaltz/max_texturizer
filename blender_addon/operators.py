import bpy
import urllib.request
import urllib.parse
import json
import uuid
import os
import zipfile
import tempfile

def get_preferences():
    return bpy.context.preferences.addons[__package__.split('.')[0]].preferences

def show_message_box(message="", title="Max Texturizer", icon='INFO'):
    def draw(self, context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title=title, icon=icon)

def build_multipart_body(fields, files):
    """
    Builds a multipart/form-data request body in pure Python.
    Avoids requiring 'requests' or 'urllib3' in Blender.
    """
    boundary = '----MaxTexturizerBoundary' + str(uuid.uuid4()).replace('-', '')
    parts = []
    
    # Text fields
    for key, val in fields.items():
        if val is None:
            continue
        parts.append(f'--{boundary}')
        parts.append(f'Content-Disposition: form-data; name="{key}"')
        parts.append('')
        parts.append(str(val))
        
    # File fields
    for key, file_info in files.items():
        filename, file_bytes = file_info
        parts.append(f'--{boundary}')
        parts.append(f'Content-Disposition: form-data; name="{key}"; filename="{filename}"')
        parts.append('Content-Type: application/octet-stream')
        parts.append('')
        parts.append(file_bytes)
        
    parts.append(f'--{boundary}--')
    parts.append('')
    
    # Assemble as bytes
    body_bytes = b''
    for part in parts:
        if isinstance(part, str):
            body_bytes += part.encode('utf-8') + b'\r\n'
        else:
            body_bytes += part + b'\r\n'
            
    return body_bytes, f'multipart/form-data; boundary={boundary}'


class OBJECT_OT_MaxTexturizerCheckConnection(bpy.types.Operator):
    bl_idname = "object.max_texturizer_check_connection"
    bl_label = "Verificar Conexão"
    bl_description = "Verifica se o servidor FastAPI local está ativo"

    def execute(self, context):
        prefs = get_preferences()
        url = f"{prefs.server_url.rstrip('/')}/health"
        
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                status = data.get("status", "unknown")
                device = data.get("device", "unknown")
                is_mock = data.get("is_mock", True)
                mode_str = "MODO REAL (Hunyuan3D)" if not is_mock else "MODO MOCK (Procedural)"
                
                show_message_box(
                    message=f"Conectado! Status: {status} | Dispositivo: {device} | {mode_str}",
                    title="Conexão OK",
                    icon='CHECKMARK'
                )
        except Exception as e:
            show_message_box(
                message=f"Erro de conexão com {url}: {e}",
                title="Erro de Conexão",
                icon='ERROR'
            )
            
        return {'FINISHED'}


class OBJECT_OT_MaxTexturizerPreview(bpy.types.Operator):
    bl_idname = "object.max_texturizer_preview"
    bl_label = "Visualizar Imagem de Referência"
    bl_description = "Gera a imagem de referência a partir do prompt para visualização prévia"

    def execute(self, context):
        scene = context.scene
        prompt = scene.max_texturizer_prompt
        
        if not prompt.strip():
            show_message_box("Por favor, insira um prompt de texto primeiro.", "Prompt Vazio", 'WARNING')
            return {'CANCELLED'}
            
        prefs = get_preferences()
        query_params = urllib.parse.urlencode({
            "prompt": prompt,
            "force_mock": prefs.force_mock
        })
        url = f"{prefs.server_url.rstrip('/')}/generate-ref-image?{query_params}"
        
        self.report({'INFO'}, "Gerando imagem de referência no servidor...")
        
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=25) as response:
                img_data = response.read()
                
                # Save to temp file
                temp_dir = tempfile.gettempdir()
                img_path = os.path.join(temp_dir, "max_texturizer_preview.png")
                with open(img_path, "wb") as f:
                    f.write(img_data)
                
                # Load or reload image in Blender
                img_name = "MaxTexturizer_Preview"
                if img_name in bpy.data.images:
                    bpy.data.images[img_name].filepath = img_path
                    bpy.data.images[img_name].reload()
                    img = bpy.data.images[img_name]
                else:
                    img = bpy.data.images.load(img_path)
                    img.name = img_name
                    
                # Open image in any open Image Editor to show preview
                found_editor = False
                for area in context.screen.areas:
                    if area.type == 'IMAGE_EDITOR':
                        for space in area.spaces:
                            if space.type == 'IMAGE_EDITOR':
                                space.image = img
                                found_editor = True
                                break
                                
                if found_editor:
                    self.report({'INFO'}, "Imagem de referência carregada no Editor de Imagens!")
                else:
                    show_message_box(
                        message="Imagem gerada! Abra uma janela do Editor de Imagens e selecione 'MaxTexturizer_Preview'.",
                        title="Imagem Pronta",
                        icon='IMAGE_DATA'
                    )
                    
        except Exception as e:
            show_message_box(f"Erro ao gerar imagem de referência: {e}", "Falha no Preview", 'ERROR')
            
        return {'FINISHED'}


class OBJECT_OT_MaxTexturizerGenerate(bpy.types.Operator):
    bl_idname = "object.max_texturizer_generate"
    bl_label = "Gerar Textura"
    bl_description = "Exporta o objeto ativo, envia para texturizar e atualiza o modelo/materiais"

    def execute(self, context):
        active_obj = context.active_object
        
        if not active_obj or active_obj.type != 'MESH':
            show_message_box("Por favor, selecione um objeto do tipo Malha (Mesh) ativo.", "Seleção Inválida", 'WARNING')
            return {'CANCELLED'}
            
        scene = context.scene
        prompt = scene.max_texturizer_prompt
        
        if not prompt.strip():
            show_message_box("Insira um prompt de texto para guiar a texturização.", "Prompt Vazio", 'WARNING')
            return {'CANCELLED'}

        prefs = get_preferences()
        
        # Save positions to restore later
        original_loc = active_obj.location.copy()
        original_rot = active_obj.rotation_euler.copy()
        original_scale = active_obj.scale.copy()
        original_name = active_obj.name
        
        # 1. Export active mesh to temporary GLB file
        temp_dir = tempfile.gettempdir()
        export_path = os.path.join(temp_dir, f"export_{uuid.uuid4().hex[:8]}.glb")
        
        self.report({'INFO'}, f"Exportando malha para {export_path}...")
        
        # Temporarily isolate selection
        bpy.ops.object.select_all(action='DESELECT')
        active_obj.select_set(True)
        context.view_layer.objects.active = active_obj
        
        # Call GLTF exporter
        try:
            bpy.ops.export_scene.gltf(
                filepath=export_path,
                export_format='GLB',
                use_selection=True,
                export_apply=True  # Apply modifiers
            )
        except Exception as e:
            # Restore selection
            active_obj.select_set(True)
            show_message_box(f"Falha ao exportar a malha do Blender: {e}", "Erro no Export", 'ERROR')
            return {'CANCELLED'}

        # Read exported file bytes
        try:
            with open(export_path, "rb") as f:
                glb_bytes = f.read()
        except Exception as e:
            show_message_box(f"Falha ao ler malha temporária: {e}", "Erro de Leitura", 'ERROR')
            return {'CANCELLED'}
        finally:
            if os.path.exists(export_path):
                os.remove(export_path)

        # 2. Call FastAPI backend
        url = f"{prefs.server_url.rstrip('/')}/texture"
        self.report({'INFO'}, "Enviando arquivo para o servidor de texturização...")
        
        fields = {
            "prompt": prompt,
            "resolution": scene.max_texturizer_resolution,
            "steps": scene.max_texturizer_steps,
            "guidance_scale": scene.max_texturizer_guidance,
            "negative_prompt": scene.max_texturizer_neg_prompt,
            "force_mock": prefs.force_mock
        }
        
        files = {
            "file": (f"{original_name}.glb", glb_bytes)
        }
        
        body, content_type = build_multipart_body(fields, files)
        
        try:
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", content_type)
            
            with urllib.request.urlopen(req, timeout=180) as response:
                zip_bytes = response.read()
                
                # Unzip the returned archive
                unzip_dir = os.path.join(temp_dir, f"unzip_{uuid.uuid4().hex[:8]}")
                os.makedirs(unzip_dir, exist_ok=True)
                
                zip_path = os.path.join(unzip_dir, "result.zip")
                with open(zip_path, "wb") as f:
                    f.write(zip_bytes)
                    
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(unzip_dir)
                
                mesh_glb_path = os.path.join(unzip_dir, "mesh.glb")
                albedo_path = os.path.join(unzip_dir, "albedo.png")
                roughness_path = os.path.join(unzip_dir, "roughness.png")
                normal_path = os.path.join(unzip_dir, "normal.png")
                
                if scene.max_texturizer_mode == 'IMPORT_GLB':
                    # --- OPTION A: Import textured GLB and replace ---
                    if not os.path.exists(mesh_glb_path):
                        raise FileNotFoundError("Servidor não retornou a malha 'mesh.glb' no arquivo ZIP.")
                        
                    # Deselect all
                    bpy.ops.object.select_all(action='DESELECT')
                    
                    # Import GLB
                    bpy.ops.import_scene.gltf(filepath=mesh_glb_path)
                    
                    # Find imported object
                    imported_objs = [obj for obj in context.selected_objects]
                    if imported_objs:
                        new_obj = imported_objs[0]
                        new_obj.name = f"{original_name}_Texturizado"
                        
                        # Apply original transformations
                        new_obj.location = original_loc
                        new_obj.rotation_euler = original_rot
                        new_obj.scale = original_scale
                        
                        # Hide original object
                        active_obj.hide_viewport = True
                        active_obj.hide_render = True
                        
                        # Make new active
                        context.view_layer.objects.active = new_obj
                        self.report({'INFO'}, "Novo objeto importado e posicionado com sucesso!")
                    else:
                        raise RuntimeError("Não foi possível localizar o objeto importado.")
                        
                else:
                    # --- OPTION B: Apply textures to original UV coordinates ---
                    # Check files
                    if not (os.path.exists(albedo_path) and os.path.exists(roughness_path) and os.path.exists(normal_path)):
                        raise FileNotFoundError("Arquivos de texturas (albedo/roughness/normal) ausentes no ZIP.")
                        
                    # Load textures in Blender
                    img_albedo = bpy.data.images.load(albedo_path)
                    img_albedo.name = f"Tex_Albedo_{original_name}"
                    try:
                        img_albedo.pack()
                    except Exception as e:
                        self.report({'WARNING'}, f"Não foi possível empacotar Albedo: {e}")
                    
                    img_roughness = bpy.data.images.load(roughness_path)
                    img_roughness.name = f"Tex_Roughness_{original_name}"
                    try:
                        img_roughness.pack()
                    except Exception as e:
                        self.report({'WARNING'}, f"Não foi possível empacotar Roughness: {e}")
                    
                    img_normal = bpy.data.images.load(normal_path)
                    img_normal.name = f"Tex_Normal_{original_name}"
                    try:
                        img_normal.pack()
                    except Exception as e:
                        self.report({'WARNING'}, f"Não foi possível empacotar Normal: {e}")
                    
                    # Setup material
                    mat_name = f"Mat_{original_name}_AI"
                    if mat_name in bpy.data.materials:
                        mat = bpy.data.materials[mat_name]
                    else:
                        mat = bpy.data.materials.new(name=mat_name)
                        
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links
                    nodes.clear()
                    
                    # Create shader nodes
                    node_output = nodes.new(type='ShaderNodeOutputMaterial')
                    node_output.location = (400, 0)
                    
                    node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                    node_principled.location = (0, 0)
                    links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
                    
                    # Albedo/Base Color Link
                    tex_albedo = nodes.new(type='ShaderNodeTexImage')
                    tex_albedo.image = img_albedo
                    tex_albedo.location = (-400, 200)
                    links.new(tex_albedo.outputs['Color'], node_principled.inputs['Base Color'])
                    
                    # Roughness Link
                    tex_rough = nodes.new(type='ShaderNodeTexImage')
                    tex_rough.image = img_roughness
                    img_roughness.colorspace_settings.name = 'Non-Color'
                    tex_rough.location = (-400, -50)
                    links.new(tex_rough.outputs['Color'], node_principled.inputs['Roughness'])
                    
                    # Normal Map Link
                    tex_normal = nodes.new(type='ShaderNodeTexImage')
                    tex_normal.image = img_normal
                    img_normal.colorspace_settings.name = 'Non-Color'
                    tex_normal.location = (-400, -300)
                    
                    node_normal_map = nodes.new(type='ShaderNodeNormalMap')
                    node_normal_map.location = (-150, -300)
                    links.new(tex_normal.outputs['Color'], node_normal_map.inputs['Color'])
                    links.new(node_normal_map.outputs['Normal'], node_principled.inputs['Normal'])
                    
                    # Assign material
                    if active_obj.data.materials:
                        active_obj.data.materials[0] = mat
                    else:
                        active_obj.data.materials.append(mat)
                        
                    # Force update viewport
                    active_obj.select_set(True)
                    self.report({'INFO'}, "Texturas aplicadas com sucesso nas UVs originais!")
                    
                # Pack all images that were loaded from the temporary unzip directory
                # (This applies to both IMPORT_GLB and APPLY_MATERIAL modes)
                for img in bpy.data.images:
                    if img.filepath and img.filepath.startswith(unzip_dir):
                        try:
                            img.pack()
                        except Exception as e:
                            print(f"Erro ao empacotar imagem temporária {img.name}: {e}")
                            
                # Clean up temporary unzip directory
                import shutil
                shutil.rmtree(unzip_dir)
                
        except Exception as e:
            # Restore selection
            active_obj.select_set(True)
            show_message_box(f"Falha na texturização automática: {e}", "Erro no Processamento", 'ERROR')
            
        return {'FINISHED'}


class OBJECT_OT_MaxTexturizerOrchestrate(bpy.types.Operator):
    bl_idname = "object.max_texturizer_orchestrate"
    bl_label = "Orquestrar Materiais com LLM"
    bl_description = "Envia os slots de materiais e o prompt ao LLM local para estruturar e configurar os shaders procedimentais"

    def execute(self, context):
        active_obj = context.active_object
        
        if not active_obj or active_obj.type != 'MESH':
            show_message_box("Selecione um objeto de malha (Mesh) ativo.", "Seleção Inválida", 'WARNING')
            return {'CANCELLED'}
            
        slots = [slot.name for slot in active_obj.material_slots]
        if not slots:
            show_message_box("O objeto selecionado não possui slots de material.", "Sem Slots", 'WARNING')
            return {'CANCELLED'}
            
        scene = context.scene
        prompt = scene.max_texturizer_prompt
        
        if not prompt.strip():
            show_message_box("Digite um prompt para guiar a orquestração do LLM.", "Prompt Vazio", 'WARNING')
            return {'CANCELLED'}

        prefs = get_preferences()
        
        # 1. POST request to /orchestrate
        url = f"{prefs.server_url.rstrip('/')}/orchestrate"
        self.report({'INFO'}, "Enviando dados de slots para orquestração...")
        
        payload = {
            "prompt": prompt,
            "slots": slots,
            "model_url": prefs.llm_url,
            "model_name": prefs.llm_model
        }
        
        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, method="POST")
            req.add_header("Content-Type", "application/json")
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                materials_data = result.get("materials", [])
                
                # Apply each material config
                for mat_info in materials_data:
                    slot_name = mat_info.get("slot_name")
                    pbr = mat_info.get("pbr", {})
                    effects = mat_info.get("procedural_effects", {})
                    
                    # Find slot index
                    slot_index = -1
                    for idx, s in enumerate(active_obj.material_slots):
                        if s.name == slot_name:
                            slot_index = idx
                            break
                            
                    if slot_index == -1:
                        continue
                        
                    # Find or create material
                    mat = active_obj.material_slots[slot_index].material
                    if not mat:
                        mat = bpy.data.materials.new(name=f"Mat_{slot_name}")
                        active_obj.material_slots[slot_index].material = mat
                        
                    # Configure node tree
                    mat.use_nodes = True
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links
                    nodes.clear()
                    
                    # 1. Output and BSDF
                    node_output = nodes.new(type='ShaderNodeOutputMaterial')
                    node_output.location = (600, 0)
                    
                    node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                    node_principled.location = (200, 0)
                    links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
                    
                    # 2. Set PBR properties
                    hex_color = pbr.get("base_color", "#88888b")
                    metallic = pbr.get("metallic", 0.0)
                    roughness = pbr.get("roughness", 0.5)
                    
                    # Hex to RGBA (Blender sRGB Gamma Correction)
                    hex_clean = hex_color.lstrip('#')
                    r = int(hex_clean[0:2], 16) / 255.0
                    g = int(hex_clean[2:4], 16) / 255.0
                    b = int(hex_clean[4:6], 16) / 255.0
                    rgba = (r**2.2, g**2.2, b**2.2, 1.0)
                    
                    node_principled.inputs['Base Color'].default_value = rgba
                    node_principled.inputs['Metallic'].default_value = metallic
                    node_principled.inputs['Roughness'].default_value = roughness
                    
                    # 3. Apply procedural effects
                    
                    # Helper for Blender version-independent Mix nodes
                    def create_mix_node(nodes, name="Mix"):
                        try:
                            mix = nodes.new(type='ShaderNodeMix')
                            mix.data_type = 'RGBA'
                            mix.blend_type = 'MIX'
                        except Exception:
                            mix = nodes.new(type='ShaderNodeMixRGB')
                            mix.blend_type = 'MIX'
                        mix.name = name
                        return mix
                    
                    # Check for Fluent Node Groups or use Native
                    edge_wear = effects.get("fluent_edge_wear", {})
                    scratches = effects.get("fluent_scratches", {})
                    dirt = effects.get("fluent_dirt", {})
                    
                    # -- A. EDGE WEAR --
                    if edge_wear.get("enabled"):
                        level = edge_wear.get("wear_level", 0.5)
                        
                        # Check if Fluent Materializer node group is in file
                        fluent_group = None
                        for ng in bpy.data.node_groups:
                            if "edge_wear" in ng.name.lower() or "fluent_edge" in ng.name.lower():
                                fluent_group = ng
                                break
                                
                        if fluent_group:
                            # Fluent Group exists! Add Node Group
                            group_node = nodes.new(type='ShaderNodeGroup')
                            group_node.node_tree = fluent_group
                            group_node.location = (-150, 150)
                            # Set inputs if matched
                            for inp in group_node.inputs:
                                if "wear" in inp.name.lower() or "level" in inp.name.lower() or "amount" in inp.name.lower():
                                    inp.default_value = level
                                    
                            # Create a mix color node to blend base color with a wear color (gray metal)
                            mix_color = create_mix_node(nodes, "WearMix")
                            mix_color.location = (-50, 0)
                            if hasattr(mix_color, 'inputs') and 'A' in mix_color.inputs: # ShaderNodeMix
                                mix_color.inputs['A'].default_value = rgba
                                mix_color.inputs['B'].default_value = (0.7, 0.7, 0.7, 1.0) # steel wear color
                                links.new(group_node.outputs[0], mix_color.inputs['Factor'])
                                links.new(mix_color.outputs['Result'], node_principled.inputs['Base Color'])
                            else: # ShaderNodeMixRGB
                                mix_color.inputs[1].default_value = rgba
                                mix_color.inputs[2].default_value = (0.7, 0.7, 0.7, 1.0)
                                links.new(group_node.outputs[0], mix_color.inputs[0])
                                links.new(mix_color.outputs[0], node_principled.inputs['Base Color'])
                        else:
                            # Native Fallback: Pointiness + Noise
                            geom = nodes.new(type='ShaderNodeNewGeometry')
                            geom.location = (-700, 300)
                            
                            ramp = nodes.new(type='ShaderNodeValToRGB')
                            ramp.location = (-500, 300)
                            ramp.color_ramp.elements[0].position = 0.45
                            ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
                            ramp.color_ramp.elements[1].position = 0.55
                            ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
                            
                            links.new(geom.outputs['Pointiness'], ramp.inputs['Fac'])
                            
                            noise = nodes.new(type='ShaderNodeTexNoise')
                            noise.location = (-700, 100)
                            noise.inputs['Scale'].default_value = 15.0
                            
                            mix_mask = create_mix_node(nodes, "MaskMix")
                            mix_mask.location = (-300, 200)
                            
                            if hasattr(mix_mask, 'inputs') and 'A' in mix_mask.inputs:
                                links.new(ramp.outputs['Color'], mix_mask.inputs['A'])
                                links.new(noise.outputs['Color'], mix_mask.inputs['B'])
                                mix_mask.inputs['Factor'].default_value = 0.3
                                
                                mix_color = create_mix_node(nodes, "WearMixColor")
                                mix_color.location = (-50, 50)
                                mix_color.inputs['A'].default_value = rgba
                                mix_color.inputs['B'].default_value = (0.7, 0.7, 0.7, 1.0)
                                links.new(mix_mask.outputs['Result'], mix_color.inputs['Factor'])
                                links.new(mix_color.outputs['Result'], node_principled.inputs['Base Color'])
                            else:
                                links.new(ramp.outputs['Color'], mix_mask.inputs[1])
                                links.new(noise.outputs['Color'], mix_mask.inputs[2])
                                mix_mask.inputs[0].default_value = 0.3
                                
                                mix_color = create_mix_node(nodes, "WearMixColor")
                                mix_color.location = (-50, 50)
                                mix_color.inputs[1].default_value = rgba
                                mix_color.inputs[2].default_value = (0.7, 0.7, 0.7, 1.0)
                                links.new(mix_mask.outputs[0], mix_color.inputs[0])
                                links.new(mix_color.outputs[0], node_principled.inputs['Base Color'])
                                
                    # -- B. SCRATCHES (Native Voronoi) --
                    if scratches.get("enabled"):
                        density = scratches.get("density", 0.5)
                        
                        voronoi = nodes.new(type='ShaderNodeTexVoronoi')
                        voronoi.location = (-400, -200)
                        voronoi.inputs['Scale'].default_value = 100.0 * density
                        
                        v_ramp = nodes.new(type='ShaderNodeValToRGB')
                        v_ramp.location = (-200, -200)
                        v_ramp.color_ramp.elements[0].position = 0.0
                        v_ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
                        v_ramp.color_ramp.elements[1].position = 0.05
                        v_ramp.color_ramp.elements[1].color = (0, 0, 0, 1)
                        
                        links.new(voronoi.outputs['Distance'], v_ramp.inputs['Fac'])
                        
                        bump = nodes.new(type='ShaderNodeBump')
                        bump.location = (0, -200)
                        bump.inputs['Strength'].default_value = 0.3
                        bump.inputs['Distance'].default_value = 0.05
                        
                        links.new(v_ramp.outputs['Color'], bump.inputs['Height'])
                        links.new(bump.outputs['Normal'], node_principled.inputs['Normal'])

                    # -- C. DIRT (Ambient Occlusion) --
                    if dirt.get("enabled"):
                        level = dirt.get("dirt_level", 0.5)
                        
                        ao = nodes.new(type='ShaderNodeAmbientOcclusion')
                        ao.location = (-500, -400)
                        ao.inputs['Distance'].default_value = 2.0 * level
                        
                        ao_ramp = nodes.new(type='ShaderNodeValToRGB')
                        ao_ramp.location = (-300, -400)
                        ao_ramp.color_ramp.elements[0].position = 0.1
                        ao_ramp.color_ramp.elements[0].color = (0.2, 0.15, 0.1, 1.0) # dark dirt brown
                        ao_ramp.color_ramp.elements[1].position = 0.8
                        ao_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
                        
                        links.new(ao.outputs['Color'], ao_ramp.inputs['Fac'])
                        
                        mix_dirt = create_mix_node(nodes, "DirtMultiply")
                        mix_dirt.location = (50, -400)
                        mix_dirt.blend_type = 'MULTIPLY'
                        
                        if hasattr(mix_dirt, 'inputs') and 'A' in mix_dirt.inputs:
                            base_link = None
                            for l in links:
                                if l.to_node == node_principled and l.to_socket.name == 'Base Color':
                                    base_link = l
                                    break
                            
                            if base_link:
                                links.new(base_link.from_socket, mix_dirt.inputs['A'])
                                links.remove(base_link)
                            else:
                                mix_dirt.inputs['A'].default_value = node_principled.inputs['Base Color'].default_value
                                
                            links.new(ao_ramp.outputs['Color'], mix_dirt.inputs['B'])
                            mix_dirt.inputs['Factor'].default_value = 0.8
                            links.new(mix_dirt.outputs['Result'], node_principled.inputs['Base Color'])
                        else:
                            base_link = None
                            for l in links:
                                if l.to_node == node_principled and l.to_socket.name == 'Base Color':
                                    base_link = l
                                    break
                            
                            if base_link:
                                links.new(base_link.from_socket, mix_dirt.inputs[1])
                                links.remove(base_link)
                            else:
                                mix_dirt.inputs[1].default_value = node_principled.inputs['Base Color'].default_value
                                
                            links.new(ao_ramp.outputs['Color'], mix_dirt.inputs[2])
                            mix_dirt.inputs[0].default_value = 0.8
                            links.new(mix_dirt.outputs[0], node_principled.inputs['Base Color'])
                            
                # Finished slots orchestration loop
                show_message_box(
                    message="Orquestração concluída! Materiais PBR e shaders procedimentais configurados com sucesso.",
                    title="Orquestração Concluída",
                    icon='CHECKMARK'
                )
                
        except Exception as e:
            show_message_box(f"Falha ao orquestrar materiais: {e}", "Erro na Orquestração", 'ERROR')
            
        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerCheckConnection)
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerPreview)
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerGenerate)
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerOrchestrate)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerCheckConnection)
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerPreview)
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerGenerate)
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerOrchestrate)
