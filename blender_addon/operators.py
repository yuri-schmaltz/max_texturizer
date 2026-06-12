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


def register():
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerCheckConnection)
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerPreview)
    bpy.utils.register_class(OBJECT_OT_MaxTexturizerGenerate)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerCheckConnection)
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerPreview)
    bpy.utils.unregister_class(OBJECT_OT_MaxTexturizerGenerate)
