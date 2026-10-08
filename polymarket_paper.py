"""
Motor de Simulación (Paper Trading) para Polymarket.
Gestiona el saldo virtual en USDC, registro de apuestas (contratos YES/NO),
actualización de precios en tiempo real, Take Profit, Stop Loss y cálculo de P&L.
Persiste todo en polymarket_ledger.json.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import config
from polymarket_service import PolymarketService

logger = logging.getLogger("PolymarketPaper")

LEDGER_FILE = os.path.join(os.path.dirname(__file__), "polymarket_ledger.json")


class PolymarketPaperEngine:
    def __init__(self, ledger_file: str = LEDGER_FILE):
        self.ledger_file = ledger_file
        self.data = self._load_ledger()

    def _load_ledger(self) -> Dict[str, Any]:
        """Carga el registro desde disco o inicializa con el saldo inicial."""
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error cargando {self.ledger_file}, reiniciando: {e}")

        initial_state = {
            "cash_usdc": config.POLYMARKET_STARTING_BALANCE_USDC,
            "active_positions": {},
            "closed_trades": [],
            "total_realized_pnl": 0.0,
            "win_count": 0,
            "loss_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self._save_ledger(initial_state)
        return initial_state

    def _save_ledger(self, data: Optional[Dict[str, Any]] = None) -> None:
        """Guarda el estado actual en disco de forma segura."""
        save_data = data or self.data
        try:
            with open(self.ledger_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error guardando {self.ledger_file}: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Calcula el estado actual de la cartera de simulación."""
        cash = float(self.data.get("cash_usdc", 0.0))
        positions = self.data.get("active_positions", {})
        
        invested = 0.0
        current_value = 0.0
        unrealized_pnl = 0.0

        for pos in positions.values():
            inv = float(pos.get("invested_usd", 0.0))
            val = float(pos.get("current_value", inv))
            invested += inv
            current_value += val
            unrealized_pnl += (val - inv)

        total_equity = cash + current_value
        realized_pnl = float(self.data.get("total_realized_pnl", 0.0))

        return {
            "cash_usdc": cash,
            "invested_usdc": invested,
            "current_value_usdc": current_value,
            "total_equity_usdc": total_equity,
            "unrealized_pnl_usdc": unrealized_pnl,
            "unrealized_pnl_pct": (unrealized_pnl / invested * 100.0) if invested > 0 else 0.0,
            "realized_pnl_usdc": realized_pnl,
            "active_positions_count": len(positions),
            "win_count": self.data.get("win_count", 0),
            "loss_count": self.data.get("loss_count", 0)
        }

    def can_open_position(self, amount_usd: float) -> bool:
        """Verifica si hay saldo suficiente y si no se supera el límite de apuestas activas."""
        if len(self.data.get("active_positions", {})) >= config.POLYMARKET_MAX_POSITIONS:
            return False
        if self.data.get("cash_usdc", 0.0) < amount_usd:
            return False
        return True

    def open_position(
        self,
        market: Dict[str, Any],
        outcome: str,
        amount_usd: float,
        catalyst: Optional[Dict[str, Any]] = None,
        force: bool = False,
        no_stop_loss: bool = False,
        hold_until_resolution: bool = False,
        target_exit_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Abre una posición simulada en Polymarket.
        Compra 'shares' del contrato seleccionado (Yes o No).
        """
        market_id = market["id"]
        if market_id in self.data["active_positions"] and not force:
            logger.info(f"Ya existe posición abierta para el mercado {market_id}")
            return None

        price = market["prices"].get(outcome, 0.0)
        if price <= 0.01 or price >= 0.99:
            logger.warning(f"Precio fuera de rango operativo ({price}) para {outcome}")
            return None

        if not force and not self.can_open_position(amount_usd):
            logger.warning(f"No se puede abrir posición: saldo o límite de posiciones alcanzado.")
            return None

        shares = amount_usd / price
        self.data["cash_usdc"] -= amount_usd

        pos = {
            "market_id": market_id,
            "question": market["question"],
            "event_title": market.get("event_title", market["question"]),
            "slug": market.get("slug", ""),
            "url": market.get("url", f"https://polymarket.com/market/{market.get('slug', '')}"),
            "outcome": outcome,
            "entry_price": price,
            "current_price": price,
            "shares": shares,
            "invested_usd": amount_usd,
            "current_value": amount_usd,
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "catalyst": catalyst or {},
            "no_stop_loss": no_stop_loss,
            "hold_until_resolution": hold_until_resolution,
            "target_exit_date": target_exit_date,
            "opened_at": datetime.now(timezone.utc).isoformat()
        }

        self.data["active_positions"][market_id] = pos
        self._save_ledger()
        logger.info(f"[PAPER POLYMARKET] Compradas {shares:.1f} acciones de '{outcome}' en '{market['question']}' a ${price:.3f} (${amount_usd:.2f} USDC)")
        return pos

    def update_and_evaluate_positions(self, polymarket_service: PolymarketService) -> List[Dict[str, Any]]:
        """
        Revisa todas las posiciones abiertas:
        1. Consulta precios actuales en Polymarket.
        2. Ejecuta Take Profit (+30%) o Stop Loss (-15%).
        3. Comprueba si el evento ya se resolvió ($1.00 o $0.00).
        Devuelve la lista de cierres ejecutados para notificar a Telegram.
        """
        self.data = self._load_ledger()
        closed_events = []
        positions = list(self.data.get("active_positions", {}).items())

        for market_id, pos in positions:
            outcome = pos["outcome"]
            entry_price = float(pos["entry_price"])
            shares = float(pos["shares"])
            invested = float(pos["invested_usd"])

            # Buscar mercado actualizado directamente por ID
            updated_m = polymarket_service.get_market_by_id(market_id)
            if not updated_m:
                continue

            current_price = updated_m["prices"].get(outcome, entry_price)
            pos["current_price"] = current_price
            current_value = shares * current_price
            pos["current_value"] = current_value
            pnl = current_value - invested
            pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0.0
            pos["unrealized_pnl"] = pnl
            pos["unrealized_pnl_pct"] = pnl_pct * 100.0

            should_close = False
            close_reason = ""

            no_stop_loss = pos.get("no_stop_loss", False)
            hold_until_resolution = pos.get("hold_until_resolution", False)
            target_exit_date = pos.get("target_exit_date")
            now_iso = datetime.now(timezone.utc).isoformat()

            # 1. Mercado resuelto o cerrado por Polymarket
            if updated_m.get("closed") or current_price >= 0.99 or current_price <= 0.01:
                should_close = True
                if current_price >= 0.95:
                    close_reason = "🏁 RESOLUCIÓN GANADA ($1.00)"
                else:
                    close_reason = "❌ RESOLUCIÓN PERDIDA ($0.00)"

            # 2. Retirada programada por fecha objetivo (ej. tras elecciones del 29 nov 2026)
            elif target_exit_date and now_iso >= target_exit_date:
                should_close = True
                close_reason = f"📅 RETIRADA PROGRAMADA TRAS ELECCIONES ({target_exit_date[:10]} - Cuota: ${current_price:.3f} / P&L: {pnl_pct*100:+.1f}%)"

            # 3. Retirada por objetivo específico de Take Profit en USD (ej. si la posición alcanza $6,000 USD o más)
            elif pos.get("target_take_profit_usd") and current_value >= float(pos["target_take_profit_usd"]):
                should_close = True
                close_reason = f"🎯 TAKE PROFIT OBJETIVO (${current_value:,.2f} USD / Cuota: ${current_price:.3f} / P&L: +${pnl:,.2f})"

            # 4. Retirada por máxima cotización en posición de convicción (precio sube a cota de victoria >= 0.95)
            elif hold_until_resolution and current_price >= 0.95:
                should_close = True
                close_reason = f"🎯 RETIRADA MÁXIMA TRAS SALIDA/VICTORIA (${current_price:.3f} - +{pnl_pct*100:.1f}%)"

            # 5. Take Profit estándar (solo para posiciones normales sin hold_until_resolution)
            elif not hold_until_resolution and pnl_pct >= config.POLYMARKET_TAKE_PROFIT_PCT:
                should_close = True
                close_reason = f"🎯 TAKE PROFIT (+{pnl_pct*100:.1f}%)"

            # 5. Stop Loss estándar (solo para posiciones normales sin no_stop_loss ni hold_until_resolution)
            elif not no_stop_loss and not hold_until_resolution and pnl_pct <= -config.POLYMARKET_STOP_LOSS_PCT:
                should_close = True
                close_reason = f"🛑 STOP LOSS ({pnl_pct*100:.1f}%)"

            if should_close:
                # Cerrar posición
                self.data["cash_usdc"] += current_value
                self.data["total_realized_pnl"] += pnl
                if pnl >= 0:
                    self.data["win_count"] = self.data.get("win_count", 0) + 1
                else:
                    self.data["loss_count"] = self.data.get("loss_count", 0) + 1

                trade_record = {
                    **pos,
                    "exit_price": current_price,
                    "final_value": current_value,
                    "realized_pnl": pnl,
                    "realized_pnl_pct": pnl_pct * 100.0,
                    "close_reason": close_reason,
                    "closed_at": datetime.now(timezone.utc).isoformat()
                }
                self.data["closed_trades"].append(trade_record)
                del self.data["active_positions"][market_id]
                closed_events.append(trade_record)
                logger.info(f"[PAPER POLYMARKET CIERRE] {close_reason} en '{pos['question']}': P&L ${pnl:+.2f} ({pnl_pct*100:+.1f}%)")

        self._save_ledger()
        return closed_events
