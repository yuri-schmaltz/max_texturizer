import json
import urllib.request
import urllib.error
import logging
import re

logger = logging.getLogger("max-texturizer-backend")

class LLMOrchestrator:
    def __init__(self):
        pass

    def orchestrate(self, prompt: str, slots: list, model_url: str = "http://localhost:11434", model_name: str = "llama3") -> dict:
        """
        Orchestrates material assignment. Attempts to connect to a local LLM via Ollama.
        Falls back to rule-based keyword extraction if Ollama is offline or fails.
        """
        logger.info(f"Orchestrating materials for slots {slots} with prompt: '{prompt}'")
        
        # Clean URLs
        model_url = model_url.rstrip('/')
        
        try:
            # 1. Prepare system prompt and instructions
            system_prompt = (
                "You are an expert 3D shading assistant. Your job is to decompose a natural language description of an object "
                "into specific PBR material properties and procedural shader effects for a list of Blender material slots.\n\n"
                "You MUST respond ONLY with a raw JSON object matching this schema:\n"
                "{\n"
                "  \"materials\": [\n"
                "    {\n"
                "      \"slot_name\": \"string matching one of the slots exactly\",\n"
                "      \"pbr\": {\n"
                "        \"base_color\": \"#hexcolor\",\n"
                "        \"metallic\": float (0.0 to 1.0),\n"
                "        \"roughness\": float (0.0 to 1.0)\n"
                "      },\n"
                "      \"procedural_effects\": {\n"
                "        \"fluent_edge_wear\": { \"enabled\": boolean, \"wear_level\": float (0.0 to 1.0) },\n"
                "        \"fluent_scratches\": { \"enabled\": boolean, \"density\": float (0.0 to 1.0) },\n"
                "        \"fluent_dirt\": { \"enabled\": boolean, \"dirt_level\": float (0.0 to 1.0) }\n"
                "      }\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "Ensure every slot provided is mapped. Do not include markdown code block characters like ```json or any conversational text. Only return the raw JSON."
            )
            
            user_content = f"Material slots: {slots}\nUser Prompt: {prompt}"
            
            # Send to Ollama (OpenAI compatible endpoint /v1/chat/completions)
            api_url = f"{model_url}/v1/chat/completions"
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            }
            
            headers = {"Content-Type": "application/json"}
            data_bytes = json.dumps(payload).encode('utf-8')
            
            logger.info(f"Connecting to local LLM at {api_url}...")
            req = urllib.request.Request(api_url, data=data_bytes, headers=headers, method="POST")
            
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode())
                raw_content = res_data['choices'][0]['message']['content'].strip()
                
                # Parse to ensure it is valid JSON
                result = json.loads(raw_content)
                logger.info("Successfully received and parsed JSON from local LLM!")
                return result
                
        except Exception as e:
            logger.warning(f"Ollama/LM Studio connection failed or returned invalid JSON ({e}). Falling back to Semantic Parser...")
            return self._fallback_semantic_orchestrate(prompt, slots)

    def _fallback_semantic_orchestrate(self, prompt: str, slots: list) -> dict:
        """
        Rule-based keyword matching parser to simulate LLM orchestration.
        Guarantees 100% offline reliability.
        """
        logger.info("Running local Semantic Fallback Parser...")
        prompt_lower = prompt.lower()
        
        materials = []
        
        for slot in slots:
            slot_lower = slot.lower()
            
            # 1. Base PBR default values
            base_color = "#88888b" # default steel gray
            metallic = 0.0
            roughness = 0.5
            
            # Determine materials based on slot names or prompt keywords matching slot
            # Gold / Ouro
            if "gold" in slot_lower or "ouro" in slot_lower or ("gold" in prompt_lower and ("punho" in slot_lower or "hilt" in slot_lower or "guarda" in slot_lower)):
                base_color = "#cd9a21"
                metallic = 1.0
                roughness = 0.2
            # Iron / Metal / Steel / Ferro
            elif any(x in slot_lower for x in ["metal", "iron", "ferro", "steel", "blade", "lamina", "placa", "chassis"]):
                base_color = "#88888c"
                metallic = 1.0
                roughness = 0.3
            # Bronze / Copper / Cobre
            elif any(x in slot_lower for x in ["bronze", "copper", "cobre", "brass", "latão"]):
                base_color = "#b87333"
                metallic = 1.0
                roughness = 0.25
            # Wood / Madeira
            elif "wood" in slot_lower or "madeira" in slot_lower or "cabo" in slot_lower or "handle" in slot_lower:
                base_color = "#8a5a36" # warm wood brown
                metallic = 0.0
                roughness = 0.8
            # Leather / Couro
            elif "leather" in slot_lower or "couro" in slot_lower or "grip" in slot_lower:
                base_color = "#4a2e1b"
                metallic = 0.0
                roughness = 0.9
            # Plastic / Plástico
            elif "plastic" in slot_lower or "plastico" in slot_lower or "borracha" in slot_lower or "rubber" in slot_lower:
                base_color = "#333333"
                metallic = 0.0
                roughness = 0.4
            # Stone / Pedra
            elif "stone" in slot_lower or "pedra" in slot_lower or "rock" in slot_lower:
                base_color = "#777777"
                metallic = 0.0
                roughness = 0.9

            # Let's override color if prompt contains a specific color near slot descriptions
            # (simple regex heuristic)
            if "vermelh" in prompt_lower or "red" in prompt_lower:
                if any(x in slot_lower for x in ["cabo", "detalhe", "tinta", "paint", "body", "chassis"]):
                    base_color = "#cc2222"
            if "verde" in prompt_lower or "green" in prompt_lower:
                if any(x in slot_lower for x in ["cabo", "detalhe", "tinta", "paint", "body", "chassis"]):
                    base_color = "#22aa22"
            if "azul" in prompt_lower or "blue" in prompt_lower:
                if any(x in slot_lower for x in ["cabo", "detalhe", "tinta", "paint", "body", "chassis"]):
                    base_color = "#2222cc"

            # 2. Check for wear and tear keywords
            edge_wear_enabled = False
            wear_level = 0.0
            if any(x in prompt_lower for x in ["desgastado", "wear", "edge", "antigo", "old", "velho", "detonado"]):
                edge_wear_enabled = True
                wear_level = 0.75 if "muito" in prompt_lower else 0.5
            elif "rust" in prompt_lower or "ferrugem" in prompt_lower:
                edge_wear_enabled = True
                wear_level = 0.6
                
            scratches_enabled = False
            scratches_density = 0.0
            if any(x in prompt_lower for x in ["arranh", "scratch", "riscado", "riscos"]):
                scratches_enabled = True
                scratches_density = 0.7 if "muito" in prompt_lower else 0.45
                
            dirt_enabled = False
            dirt_level = 0.0
            if any(x in prompt_lower for x in ["sujo", "sujeira", "dirt", "poeira", "dust", "crevice"]):
                dirt_enabled = True
                dirt_level = 0.65 if "muito" in prompt_lower else 0.4
                
            materials.append({
                "slot_name": slot,
                "pbr": {
                    "base_color": base_color,
                    "metallic": float(metallic),
                    "roughness": float(roughness)
                },
                "procedural_effects": {
                    "fluent_edge_wear": { "enabled": edge_wear_enabled, "wear_level": float(wear_level) },
                    "fluent_scratches": { "enabled": scratches_enabled, "density": float(scratches_density) },
                    "fluent_dirt": { "enabled": dirt_enabled, "dirt_level": float(dirt_level) }
                }
            })
            
        return {"materials": materials}

# Global orchestrator instance
llm_orchestrator = LLMOrchestrator()
