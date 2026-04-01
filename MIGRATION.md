# Vel Migration Guide

## Moving to new hardware

### What to transfer
1. The entire `~/engine-analysis/` folder
2. Your `.env` file (keep this secret, never commit it)
3. Your Tailscale account (just login on new machine)

### Steps
1. Install CachyOS or any Arch based distro
2. Install dependencies:
```bash
curl -fsSL https://tailscale.com/install.sh | sh
curl -fsSL https://ollama.com/install.sh | sh
sudo pacman -S docker docker-compose python-pip
pip install llama-index llama-index-llms-ollama llama-index-embeddings-ollama fastapi uvicorn slowapi textual psutil pandas openpyxl beautifulsoup4 requests python-dotenv tqdm --break-system-packages
```
3. Copy engine-analysis folder to new machine
4. Pull your model:
```bash
ollama pull mistral
```
5. Copy systemd service files:
```bash
sudo cp engine-analysis/services/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ollama vel vel-watchdog vel-scraper.timer
```
6. Start Docker Compose:
```bash
cd engine-analysis && sudo docker-compose up -d
```
7. Connect Tailscale:
```bash
sudo tailscale up
```

### If you get a bigger GPU
Nothing to change — Ollama auto detects and uses it.
If you want a bigger model:
```bash
ollama pull llama3.1:70b
```
Then update MODEL_NAME in `.env` and restart Vel.

### Verify everything works
```bash
curl http://localhost:8001/health
velframe
```
