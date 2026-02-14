# Next Steps - Getting Arrmate Running

You now have a complete Arrmate implementation! Here's what to do next.

## 📋 Pre-flight Checklist

Before you begin, make sure you have:

- [ ] Sonarr installed and running (or access to Sonarr instance)
- [ ] Radarr installed and running (or access to Radarr instance)
- [ ] Sonarr API key (Settings → General → Security)
- [ ] Radarr API key (Settings → General → Security)
- [ ] Docker installed (for Docker deployment) OR Python 3.11+ (for local)

## 🚀 Option 1: Docker Deployment (Recommended)

### 1. Configure Environment

```bash
cd /mnt/c/tools/arrmate
cp .env.example .env
```

Edit `.env` with your favorite editor:
```bash
nano .env
# or
vim .env
# or
code .env
```

**Required changes:**
```env
# Update these with your actual values
SONARR_URL=http://localhost:8989  # or http://sonarr:8989 if on Docker network
SONARR_API_KEY=your-actual-sonarr-api-key-here

RADARR_URL=http://localhost:7878  # or http://radarr:7878 if on Docker network
RADARR_API_KEY=your-actual-radarr-api-key-here
```

**Optional (LLM provider):**
```env
# Default is Ollama (free, runs locally)
LLM_PROVIDER=ollama

# Or use OpenAI:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

# Or use Anthropic:
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...
```

### 2. Start Services

```bash
cd docker
docker-compose up -d
```

This will:
- Build the Arrmate container
- Start Ollama container (for local LLM)
- Connect to your media services

### 3. Pull LLM Model (if using Ollama)

```bash
# Pull the default model
docker exec -it arrmate-ollama ollama pull llama3.1

# Or try other models:
# docker exec -it arrmate-ollama ollama pull mistral
```

### 4. Test It!

```bash
# Check service connections
docker exec -it arrmate arrmate services

# Try a command
docker exec -it arrmate arrmate execute "list my TV shows"

# Interactive mode
docker exec -it arrmate arrmate interactive

# Or use the API
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{"command": "list my TV shows"}'
```

### 5. View API Documentation

Open in browser: http://localhost:8000/docs

---

## 🐍 Option 2: Local Python Development

### 1. Run Setup Script

```bash
cd /mnt/c/tools/arrmate
bash scripts/dev-setup.sh
```

This will:
- Create a virtual environment
- Install all dependencies
- Install the package in editable mode
- Create .env from template

### 2. Configure Environment

Edit `.env` with your settings:
```bash
nano .env
```

Use `localhost` for local services:
```env
SONARR_URL=http://localhost:8989
SONARR_API_KEY=your-actual-key

RADARR_URL=http://localhost:7878
RADARR_API_KEY=your-actual-key

# For local LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
```

### 3. Install Ollama (if using local LLM)

Visit https://ollama.ai and install for your OS, then:

```bash
# Start Ollama
ollama serve

# In another terminal, pull a model
ollama pull llama3.1
```

### 4. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 5. Test It!

```bash
# Check services
arrmate services

# Execute commands
arrmate execute "list my TV shows"
arrmate execute "add Breaking Bad"

# Interactive mode
arrmate interactive

# Start API server
python -m arrmate.interfaces.api.app
# Then visit: http://localhost:8000/docs
```

---

## 🧪 Testing Your Setup

### 1. Verify Service Connections

```bash
arrmate services
```

Should show:
- ✓ Available status for configured services
- Service versions
- No connection errors

### 2. Test Parsing (Dry Run)

```bash
arrmate execute --dry-run "remove episode 1 of Angel"
```

Should show:
- Parsed intent with action, media_type, title, season, episodes
- No validation errors

### 3. Test List Action (Safe)

```bash
arrmate execute "list my TV shows"
```

Should show:
- Success message
- List of your TV shows

### 4. Test Add Action

```bash
# Dry run first
arrmate execute --dry-run "add The Expanse to my library"

# Then actually add
arrmate execute "add The Expanse to my library"
```

---

## 🔧 Troubleshooting

### "Could not connect to Sonarr/Radarr"

**Check URLs:**
```bash
# Test manually
curl http://localhost:8989/api/v3/system/status?apikey=YOUR_SONARR_API_KEY
curl http://localhost:7878/api/v3/system/status?apikey=YOUR_RADARR_API_KEY
```

**Common issues:**
- Wrong URL (check port numbers)
- Wrong API key (copy from Sonarr/Radarr settings)
- Service not running
- Firewall blocking connection

### "LLM did not use the parse_media_command function"

**Solution:**
- Make sure you're using a model that supports tool calling
- Ollama: Use `llama3.1` or `mistral` (NOT `llama2`)
- OpenAI: Use `gpt-4` or `gpt-3.5-turbo`
- Anthropic: Any Claude 3+ model

**Check your model:**
```bash
# Ollama
ollama list
```

### Docker: Services not found

**If Sonarr/Radarr are in a different Docker network:**

1. Find your network:
```bash
docker network ls
docker network inspect <network-name>
```

2. Update `docker-compose.yml`:
```yaml
networks:
  media-network:
    external: true
    name: your-actual-network-name
```

3. Update service URLs in `.env`:
```env
SONARR_URL=http://sonarr:8989  # Use container name
```

### Python: Module not found

```bash
# Make sure you're in the venv
source venv/bin/activate

# Reinstall package
pip install -e .
```

---

## 📝 Example Commands to Try

Once everything is working, try these:

```bash
# List content
"show me all my TV shows"
"list my movies"

# Add new content
"add Breaking Bad to my library"
"add The Matrix"
"add The Expanse"

# Remove content (be careful!)
"remove episode 1 of Angel season 1"
"delete episodes 1 and 2 of The Office season 2"

# Search for upgrades
"search for 4K version of Blade Runner"
"search for all English version of Narcos"

# Get info
"tell me about Breaking Bad"
```

---

## 🎯 Next Development Steps

If you want to extend Arrmate:

### Add Lidarr Support
1. Create `src/arrmate/clients/lidarr.py` based on `radarr.py`
2. Update `discovery.py` to include Lidarr
3. Add to `.env.example`

### Add Web UI
1. Install Streamlit: `pip install streamlit`
2. Create `src/arrmate/interfaces/web/app.py`
3. Add text input → execute command → display results

### Add More Actions
1. Add to `ActionType` enum in `core/models.py`
2. Update `llm/schemas.py` with new action
3. Add handler in `core/executor.py`

### Add Conversation Memory
1. Create `core/conversation.py`
2. Store conversation history
3. Pass to LLM for context-aware parsing

---

## 📚 Documentation Reference

- **QUICKSTART.md** - Fast setup guide
- **README.md** - Full documentation
- **IMPLEMENTATION_STATUS.md** - Implementation details
- **SUMMARY.md** - High-level overview

---

## 🆘 Getting Help

If you run into issues:

1. Check the troubleshooting section above
2. Verify your `.env` configuration
3. Check service status: `arrmate services`
4. Check logs:
   - Docker: `docker logs arrmate`
   - Local: Check console output
5. Test individual components:
   - LLM: `ollama list` / `ollama run llama3.1 "test"`
   - Sonarr: `curl http://localhost:8989/api/v3/system/status?apikey=KEY`

---

## ✅ Success Criteria

You'll know it's working when:

- [ ] `arrmate services` shows all services as "Available"
- [ ] `arrmate execute "list my TV shows"` returns your library
- [ ] API docs are accessible at http://localhost:8000/docs
- [ ] You can execute commands in natural language
- [ ] No Python import errors
- [ ] No connection errors

---

**Ready to go? Start with the Quick Start section above!**

Good luck! 🚀
