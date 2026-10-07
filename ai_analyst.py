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

--- INSTRUCCIONES DE ANÁLISIS CUANTITATIVO, ANOMALÍAS PROFUNDAS Y MODELADO HISTÓRICO ---
1. ANOMALÍA DE 3 VÍAS / REGLA 1X2 (DEPORTES Y COMPETICIONES):
   - En fútbol o deportes oficiales a tiempo reglamentario, existen 3 desenlaces: Gana equipo A, Gana equipo B, o EMPATE.
   - En preguntas tipo 'Will Team X win?', un EMPATE resuelve automáticamente como NO.
   - Los aficionados minoristas suelen inflar el YES al 70-80% por pasión, ignorando que el empate (25-30%) más la derrota suman un 45-55% real de probabilidad para el NO.
   - Si detectas esta sobrevaloración, el 'BUY_NO' ofrece una ventaja matemática descomunal.
2. SESGO DEL NO-FAVORITO (Longshot Bias):
   - El público minorista suele inflar cuotas de eventos altamente improbables (pagar 15% o 25% por algo que solo ocurre el 1-2% de las veces en la historia).
   - El 'BUY_NO' a $0.75 - $0.90 en estos casos es dinero seguro con esperanza matemática muy positiva.
3. CLÁUSULAS TEMPORALES Y PLAZOS ESTRICTOS:
   - Si la fecha de resolución está cerca y los trámites legales, legislativos o fácticos necesarios no pueden materialmente completarse a tiempo, el 'BUY_NO' es una certeza matemática.
4. TASA BASE HISTÓRICA (Base Rate):
   - Evalúa tasas base reales (elecciones presidenciales, decisiones de la Fed, victorias electorales).
5. ESPERANZA MATEMÁTICA Y VENTAJA (Edge):
   - Compara la probabilidad implícita del precio actual con tu probabilidad real estimada (Bayesiana). Solo emite orden de compra si la ventaja matemática (Edge) es superior al +10% y el ratio riesgo/beneficio es claramente asimétrico.
6. IMPACTO DE TUITS, REDES Y DECLARACIONES EN VIVO:
   - Analiza rigurosamente los tuits en X/Twitter, declaraciones y noticias recientes proporcionadas en el contexto. Si hay noticias no asimiladas por el precio de Polymarket, explótalo de inmediato.
7. Si el mercado está en precio justo o hay ambigüedad sin ventaja estadística demostrable, emite PASS.

Responde ÚNICAMENTE con esta estructura JSON:
{{
    "decision": "BUY_YES" | "BUY_NO" | "PASS",
    "conviction": <número entero del 1 al 10>,
    "estimated_real_prob": <probabilidad estadística real calculada entre 0.01 y 0.99>,
    "edge_pct": <porcentaje de ventaja matemática calculada, ej. 18.5>,
    "anomaly_type": "<nombre de la anomalía identificada: '3-Way / 1X2 Sports Trap' | 'Longshot Bias' | 'Time Expiration Impossibility' | 'Information Lag' | 'Base Rate Mispricing'>",
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
        context_news: str,
        super_investor_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analiza un activo de Alpaca (Cripto como BTC, ETH, SOL o Acción de Wall Street)
        combinando datos técnicos, respaldo de Super Inversores (Pelosi, Buffett, Whales) y noticias.
        """
        if not self.is_available():
            return {
                "decision": "HOLD",
                "conviction": 0,
                "rationale": "No hay API Key configurada para el analista de IA."
            }

        sys_inst = (
            "Eres un gestor cuantitativo senior de fondos de cobertura y analista técnico de precisión. "
            "Tu misión es evaluar activos en Alpaca (criptomonedas y acciones) combinando el rastreo de Super Inversores "
            "(Nancy Pelosi, Warren Buffett, Druckenmiller, Compras de Insiders), patrones chartistas rigurosos en el gráfico, "
            "tuits/noticias de última hora y rentabilidad matemática estricta (ratio riesgo/beneficio mínimo de 2:1). "
            "Responde SIEMPRE con un JSON válido estricto sin ningún texto fuera del bloque JSON."
        )

        super_investor_text = ""
        if super_investor_data:
            inv_names = ", ".join(super_investor_data.get("investors", []))
            inv_styles = ", ".join(super_investor_data.get("styles", []))
            inv_news = "\n".join([f"- {n}" for n in super_investor_data.get("latest_news", [])])
            super_investor_text = (
                f"=== RESPALDO DE SUPER INVERSORES / WHALES INSTITUCIONALES ===\n"
                f"• Inversores relevantes: {inv_names}\n"
                f"• Tesis / Estilo: {inv_styles}\n"
                f"• Titulares de compras recientes detectadas:\n{inv_news or 'Posición central histórica de alta convicción.'}\n"
            )

        prompt = f"""
--- ACTIVO FINANCIERO A ANALIZAR ---
Símbolo: {symbol}
Precio Actual: {current_price} USD
Métricas Técnicas y Patrones de Precio: {json.dumps(technical_data, indent=2)}

{super_investor_text}
--- INVESTIGACIÓN EN VIVO (NOTICIAS, TUITS EN X, CATALIZADORES Y REDES) ---
{context_news}

--- INSTRUCCIONES DE ANÁLISIS DE GRÁFICA, SUPER INVERSORES Y CONVERGENCIA ---
1. ANÁLISIS DE LA GRÁFICA Y VELAS:
   - Analiza la acción del precio: estructura de velas recientes (mechas de rechazo, velas envolventes, consolidación), soportes/resistencias clave y volumen.
   - Determina la tendencia predominante y si existe un patrón chartista claro (ej. ruptura de resistencia, doble suelo, retroceso a media móvil EMA9/EMA21, rebote en sobreventa RSI).
2. CONVERGENCIA CON SUPER INVERSORES (SMART MONEY):
   - Si este activo cuenta con respaldo de Super Inversores (Nancy Pelosi, Warren Buffett, Whales o Insiders), evalúa si el gráfico actual ofrece un punto de entrada óptimo para sumarse a su movimiento con ventaja.
   - La combinación de acumulación por un Super Inversor + confirmación técnica en el gráfico es la configuración de mayor probabilidad de éxito.
3. PREDICCIÓN DE MOVIMIENTO FUTURO:
   - Predice explícitamente qué va a hacer la gráfica en las próximas horas/sesiones (si romperá al alza, corregirá o seguirá lateral).
   - Calcula el VALOR ESPERADO DE SUBIDA (precio objetivo donde el precio encontrará resistencia o culminará el impulso).
4. RIESGO Y CONTROL DE STOP LOSS:
   - Determina el nivel de Stop Loss técnico donde la hipótesis alcista queda invalidada.
   - Exige una relación Riesgo/Beneficio (R:R) de al menos 1.8 a 1 (lo ideal >= 2.0).
   - Si no hay una ventaja estadística clara, si el activo está en rango sucio o la relación riesgo/beneficio es desfavorable, emite HOLD.
5. TOMA DE ACCIÓN:
   - Solo emite BUY si predices subida con convicción >= 7/10 y R:R >= 1.8. En caso contrario emite HOLD.

Responde ÚNICAMENTE con esta estructura JSON:
{{
    "decision": "BUY" | "HOLD" | "SELL",
    "conviction": <número entero 1 al 10>,
    "chart_prediction": "<predicción clara de qué va a hacer la gráfica en el corto plazo>",
    "predicted_target_price": <precio esperado de subida exacto en USD, ej. 362.50>,
    "predicted_stop_loss_price": <precio exacto de stop loss técnico en USD, ej. 348.10>,
    "target_take_profit_pct": <porcentaje esperado de subida ej. 5.5>,
    "target_stop_loss_pct": <porcentaje de stop loss ej. 2.8>,
    "risk_reward_ratio": <número decimal ej. 2.2>,
    "pattern_detected": "<nombre del patrón técnico o figura chartista identificada>",
    "super_investor_alignment": "<evaluación concisa de cómo confluye el Super Inversor con el gráfico>",
    "profitability_assessment": "<evaluación cuantitativa de por qué esta operación es matemáticamente rentable>",
    "rationale": "<análisis estratégico completo en español integrando velas, predicción, Super Inversores, tuits y noticias>"
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
