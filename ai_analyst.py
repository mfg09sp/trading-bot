"""
Módulo de Inteligencia Artificial para Análisis y Toma de Decisiones.
Integra los modelos de Google Gemini (Gemini 3.8 Flash, 3.5 Flash, 3.1 Flash Lite)
y OpenAI para evaluar noticias, tuits, probabilidades de Polymarket y activos de Alpaca en tiempo real.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

logger = logging.getLogger("AIAnalyst")


class AIAnalyst:
    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        preferred_model: str = "gemini-3.5-flash"
    ):
        self.gemini_api_key = (gemini_api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.openai_api_key = (openai_api_key or os.getenv("OPENAI_API_KEY", "")).strip()
        self.preferred_model = preferred_model

        # Modelos de Gemini ordenados por estabilidad y velocidad de respuesta
        self.gemini_models = [
            preferred_model,
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.8-flash",
            "gemini-flash-latest"
        ]
        # Eliminar duplicados manteniendo orden
        self.gemini_models = list(dict.fromkeys(self.gemini_models))

        self.openai_client = None
        if self.openai_api_key:
            try:
                from openai import OpenAI
                self.openai_client = OpenAI(api_key=self.openai_api_key)
            except Exception as e:
                logger.error(f"Error inicializando cliente OpenAI: {e}")

        logger.info(f"AIAnalyst listo. Gemini Key: {'Configurada' if self.gemini_api_key else 'No'}, OpenAI: {'Configurada' if self.openai_client else 'No'}")

    def is_available(self) -> bool:
        """Devuelve True si al menos una API Key de IA está configurada."""
        return bool(self.gemini_api_key or self.openai_client)

    def _call_gemini_rest(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """Realiza una consulta a la API de Google Gemini en modo JSON estructurado."""
        if not self.gemini_api_key:
            raise ValueError("No hay GEMINI_API_KEY configurada")

        last_error = None
        for model in self.gemini_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_api_key}"
            
            payload: Dict[str, Any] = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            }

            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        candidates = data.get("candidates", [])
                        if not candidates:
                            continue
                        
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if not parts:
                            continue
                        
                        raw_text = parts[0].get("text", "").strip()
                        parsed = json.loads(raw_text)
                        parsed["model_used"] = model
                        parsed["provider"] = "google_gemini"
                        return parsed
            except urllib.error.HTTPError as he:
                error_body = he.read().decode("utf-8") if he.fp else str(he)
                logger.warning(f"Error HTTP {he.code} con modelo {model}: {error_body[:120]}")
                last_error = f"HTTP {he.code}: {error_body[:120]}"
            except Exception as e:
                logger.warning(f"Fallo consultando modelo Gemini {model}: {e}")
                last_error = str(e)

        raise RuntimeError(f"Todos los modelos de Gemini fallaron. Último error: {last_error}")

    def _call_openai_fallback(self, prompt: str, system_instruction: str = "") -> Dict[str, Any]:
        """Fallback a OpenAI en caso de ser necesario."""
        if not self.openai_client:
            raise ValueError("No hay cliente OpenAI configurado")

        models = ["gpt-4o", "gpt-4o-mini"]
        for m in models:
            try:
                res = self.openai_client.chat.completions.create(
                    model=m,
                    messages=[
                        {"role": "system", "content": system_instruction or "Responde siempre en formato JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
                parsed = json.loads(res.choices[0].message.content)
                parsed["model_used"] = m
                parsed["provider"] = "openai"
                return parsed
            except Exception as e:
                logger.warning(f"Fallo en fallback OpenAI {m}: {e}")
        raise RuntimeError("Fallback OpenAI no disponible")

    def analyze_market_opportunity(
        self,
        market_question: str,
        current_prices: Dict[str, float],
        context_news: str,
        contract_rules: str = ""
    ) -> Dict[str, Any]:
        """
        Envía los datos de Polymarket a la IA para obtener un veredicto cuantitativo:
        BUY_YES, BUY_NO o PASS, convicción (1-10) y probabilidad real estimada.
        """
        if not self.is_available():
            return {
                "decision": "PASS",
                "conviction": 0,
                "rationale": "No hay API Key configurada para el analista de IA."
            }

        sys_inst = (
            "Eres un analista cuantitativo jefe (Quant & Bayesian Forecaster) de un fondo de arbitraje predictivo en Polymarket. "
            "Tu misión es descubrir ineficiencias de precios, sesgos cognitivos del público y errores de bulto en las cuotas "
            "comparando probabilidades implícitas del mercado contra tasas base históricas (Base Rates), datos duros y modelos probabilísticos. "
            "Responde SIEMPRE con un JSON válido estricto sin ningún texto fuera del bloque JSON."
        )

        prompt = f"""
--- MERCADO PREDICTIVO (POLYMARKET) ---
Pregunta: {market_question}
Probabilidades actuales del mercado (Precios de 0.00 a 1.00 USD): {json.dumps(current_prices)}
Reglas exactas de resolución oficial: {contract_rules or "Resolución oficial estándar"}

--- CONTEXTO Y CATALIZADORES INFORMATIVOS (NOTICIAS, DATOS, DECLARACIONES) ---
{context_news}

--- INSTRUCCIONES DE ANÁLISIS CUANTITATIVO Y MODELADO HISTÓRICO ---
1. TASA BASE HISTÓRICA (Base Rate): Evalúa cómo se resuelven históricamente eventos del mismo tipo (elecciones intermedias, decisiones de la Fed, lanzamientos espaciales, aprobaciones regulatorias). No te dejes llevar por el sensacionalismo o la histeria mediática.
2. SESGO DEL NO-FAVORITO (Longshot Bias): El público minorista suele inflar cuotas de eventos altamente improbables (ej. pagar 15% o 25% por algo que solo ocurre el 2% de las veces). Si detectas esta sobrevaloración, el 'BUY_NO' ofrece una asimetría matemática demoledora.
3. ESPERANZA MATEMÁTICA Y VENTAJA (Edge): Compara la probabilidad implícita del precio actual con tu probabilidad real estimada (Bayesiana). Solo emite orden de compra si la ventaja matemática (Edge) es superior al +10% y el ratio riesgo/beneficio es claramente asimétrico.
4. IMPACTO DE TUITS, REDES Y DECLARACIONES EN VIVO: Analiza rigurosamente los tuits en X/Twitter, publicaciones en Truth Social, discursos y filtraciones recientes proporcionadas en el contexto en vivo. Si Elon Musk, Trump, candidatos o líderes clave han posteado algo determinante en las últimas horas, úsalo como catalizador de primer orden.
5. VERIFICACIÓN DE CLÁUSULAS: Revisa si los términos de la pregunta imponen restricciones estrictas (fechas, fuentes de verificación) que benefician indiscutiblemente a una de las opciones.
6. Si el mercado está en precio justo o hay ambigüedad sin ventaja estadística demostrable, emite PASS.

Responde ÚNICAMENTE con esta estructura JSON:
{{
    "decision": "BUY_YES" | "BUY_NO" | "PASS",
    "conviction": <número entero del 1 al 10>,
    "estimated_real_prob": <probabilidad estadística real calculada entre 0.01 y 0.99>,
    "edge_pct": <porcentaje de ventaja matemática calculada, ej. 18.5>,
    "rationale": "<tesis cuantitativa concisa explicando el modelo, datos históricos y por qué el mercado está mal tasado>"
}}
"""

        # Intento 1: Google Gemini (clave proporcionada por el usuario, sin coste y con enorme contexto)
        if self.gemini_api_key:
            try:
                return self._call_gemini_rest(prompt, system_instruction=sys_inst)
            except Exception as e:
                logger.error(f"Error consultando Gemini para Polymarket: {e}")

        # Intento 2: Fallback OpenAI
        if self.openai_client:
            try:
                return self._call_openai_fallback(prompt, system_instruction=sys_inst)
            except Exception as e:
                logger.error(f"Error en fallback OpenAI para Polymarket: {e}")

        return {
            "decision": "PASS",
            "conviction": 0,
            "rationale": "Error de conexión con los proveedores de IA."
        }

    def analyze_crypto_stock(
        self,
        symbol: str,
        current_price: float,
        technical_data: Dict[str, Any],
        context_news: str
    ) -> Dict[str, Any]:
        """
        Analiza un activo de Alpaca (Cripto como BTC, ETH, SOL o Acción de Wall Street)
        combinando datos técnicos y noticias macroeconómicas.
        """
        if not self.is_available():
            return {
                "decision": "HOLD",
                "conviction": 0,
                "rationale": "No hay API Key configurada para el analista de IA."
            }

        sys_inst = (
            "Eres un gestor cuantitativo senior de fondos de cobertura y analista técnico de precisión. "
            "Tu misión es evaluar activos en Alpaca (criptomonedas y acciones) combinando patrones chartistas rigurosos, "
            "tuits/noticias de última hora y rentabilidad matemática estricta (ratio riesgo/beneficio mínimo de 2:1). "
            "Responde SIEMPRE con un JSON válido estricto sin ningún texto fuera del bloque JSON."
        )

        prompt = f"""
--- ACTIVO FINANCIERO A ANALIZAR ---
Símbolo: {symbol}
Precio Actual: {current_price} USD
Métricas Técnicas y Patrones de Precio: {json.dumps(technical_data, indent=2)}

--- INVESTIGACIÓN EN VIVO (NOTICIAS, TUITS EN X, CATALIZADORES Y REDES) ---
{context_news}

--- INSTRUCCIONES DE ANÁLISIS DE PATRONES Y RENTABILIDAD ---
1. ANÁLISIS DE PATRONES TÉCNICOS:
   - Evalúa si el precio está testeando soportes/resistencias clave, haciendo un breakout (ruptura con volumen), rebote de sobreventa o cruce de medias móviles.
   - Detecta si hay figuras de reversión o continuación alcista.
2. CÁLCULO DE RENTABILIDAD Y RATIO RIESGO/BENEFICIO (R:R):
   - Una operación SOLO es rentable si el objetivo de ganancia proyectado es al menos el doble de la pérdida asumida (Ratio R:R >= 2.0).
   - Por ejemplo: Take Profit +3.0% / Stop Loss -1.2% (Ratio 2.5:1).
   - Si la rentabilidad esperada no compensa el riesgo o el activo está lateral/estancado sin catalizador claro, emite HOLD.
3. IMPACTO DE TUITS Y NOTICIAS EN VIVO:
   - Cruza el patrón del gráfico con los titulares, tuits recientes de CEOs/líderes (Elon Musk, Jensen Huang, Sam Altman) o noticias macro.
4. Si el setup es claro y rentable, emite BUY con convicción >= 7/10.

Responde ÚNICAMENTE con esta estructura JSON:
{{
    "decision": "BUY" | "HOLD" | "SELL",
    "conviction": <número entero 1 al 10>,
    "target_take_profit_pct": <número ej. 3.0>,
    "target_stop_loss_pct": <número ej. 1.2>,
    "risk_reward_ratio": <número decimal ej. 2.5>,
    "pattern_detected": "<nombre del patrón técnico o estructura identificada>",
    "profitability_assessment": "<evaluación cuantitativa de por qué esta operación es matemáticamente rentable>",
    "rationale": "<análisis estratégico completo en español integrando gráfico, tuits y noticias>"
}}
"""

        # Intento 1: Google Gemini
        if self.gemini_api_key:
            try:
                return self._call_gemini_rest(prompt, system_instruction=sys_inst)
            except Exception as e:
                logger.error(f"Error consultando Gemini para {symbol}: {e}")

        # Intento 2: Fallback OpenAI
        if self.openai_client:
            try:
                return self._call_openai_fallback(prompt, system_instruction=sys_inst)
            except Exception as e:
                logger.error(f"Error en fallback OpenAI para {symbol}: {e}")

        return {
            "decision": "HOLD",
            "conviction": 0,
            "rationale": "Fallo al consultar el motor de IA."
        }
