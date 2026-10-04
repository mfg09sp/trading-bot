#!/usr/bin/env bash
# ==============================================================================
# Script de Despliegue Automático en la Nube (Oracle Cloud / Google Cloud / VPS)
# ==============================================================================
set -e

echo "=========================================================="
echo "  🚀 INSTALANDO BOT DE TRADING AUTÓNOMO 24/7 EN LA NUBE   "
echo "=========================================================="

# 1. Actualizar sistema e instalar Python y Git
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv git curl tmux

# 2. Configurar entorno virtual
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# 3. Instalar librerías necesarias
pip install --upgrade pip
pip install -r requirements.txt
pip install python-dotenv requests openai

# 4. Configurar servicio para que arranque solo al encender el servidor
SERVICE_FILE="/etc/systemd/system/trading-bot.service"
CURRENT_DIR=$(pwd)
USER_NAME=$(whoami)

echo "[Unit]
Description=Trading Bot Autonomo 24/7 con Gemini IA
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${CURRENT_DIR}
ExecStart=${CURRENT_DIR}/venv/bin/python ${CURRENT_DIR}/start_all.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target" | sudo tee ${SERVICE_FILE} > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable trading-bot.service
sudo systemctl restart trading-bot.service

echo "=========================================================="
echo "  ✅ INSTALACIÓN COMPLETADA CON ÉXITO                     "
echo "  El bot ya está corriendo 24/7 como un servicio en la nube."
echo "  Puedes apagar tu ordenador personal con total tranquilidad."
echo "  Comandos útiles:"
echo "    - Ver estado:  sudo systemctl status trading-bot"
echo "    - Ver registros: sudo journalctl -u trading-bot -f"
echo "    - Reiniciar:   sudo systemctl restart trading-bot"
echo "=========================================================="
