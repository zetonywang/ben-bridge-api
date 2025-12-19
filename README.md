# Ben Bridge Bidding Engine API

Fast REST API for the Ben bridge bidding engine. Loads models once at startup and keeps them in memory for instant responses.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install fastapi uvicorn pydantic
# Also ensure you have Ben's requirements installed
```

### 2. Update Configuration

Edit `ben_api.py` and change the `ben_path` variable to point to your Ben installation:

```python
ben_path = "/content/ben"  # Change this to your actual path
```

### 3. Start the Server

```bash
python ben_api.py
```

Or with uvicorn directly:

```bash
uvicorn ben_api:app --host 0.0.0.0 --port 8000 --reload
```

The server will:
- ✅ Load models on startup (takes ~30 seconds, happens only once)
- ✅ Keep models in memory for fast responses
- ✅ Start accepting requests at `http://localhost:8000`

### 4. Test the API

Visit `http://localhost:8000/docs` for interactive API documentation (Swagger UI).

## 📡 API Endpoints

### `POST /suggest` - Get Bid Suggestions

```bash
curl -X POST "http://localhost:8000/suggest" \
  -H "Content-Type: application/json" \
  -d '{
    "hand": "6.AKJT82.762.K63",
    "auction": ["1D", "3S"],
    "seat": 2,
    "dealer": 0,
    "vuln_ns": false,
    "vuln_ew": false
  }'
```

Response:
```json
{
  "passout": false,
  "candidates": [
    {
      "call": "4H",
      "insta_score": 0.85,
      "expected_score": 420.5,
      "explanation": "Natural heart bid"
    },
    {
      "call": "PASS",
      "insta_score": 0.12,
      "expected_score": -50.0
    }
  ],
  "hand": "6.AKJT82.762.K63",
  "auction": ["1D", "3S"]
}
```

### `GET /health` - Check API Status

```bash
curl http://localhost:8000/health
```

## 🐍 Python Client Usage

```python
from ben_client import BenClient

# Initialize client
client = BenClient("http://localhost:8000")

# Wait for models to load
if not client.is_ready():
    print("Waiting for API...")
    import time
    while not client.is_ready():
        time.sleep(1)

# Get bid suggestions
result = client.suggest_bid(
    hand="6.AKJT82.762.K63",
    auction=["1D", "3S"],
    seat=2,  # 0=North, 1=East, 2=South, 3=West
    dealer=0,
    vuln_ns=False,
    vuln_ew=False
)

print("Candidates:")
for candidate in result['candidates']:
    print(f"  {candidate['call']}: {candidate['insta_score']:.3f}")

# Or just get the best bid
best_bid = client.get_best_bid(
    hand="6.AKJT82.762.K63",
    auction=["1D", "3S"],
    seat=2,
    dealer=0
)
print(f"Best bid: {best_bid}")
```

## 🔧 Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `hand` | string | Yes | Hand in format `SPADES.HEARTS.DIAMONDS.CLUBS` (e.g., `"AKQ.JT9.8765.43"`) |
| `auction` | list[string] | No | Previous bids (e.g., `["1D", "PASS", "1H"]`) |
| `seat` | int | Yes | Your position: 0=North, 1=East, 2=South, 3=West |
| `dealer` | int | Yes | Who dealt: 0=North, 1=East, 2=South, 3=West |
| `vuln_ns` | bool | No | North-South vulnerable (default: false) |
| `vuln_ew` | bool | No | East-West vulnerable (default: false) |
| `verbose` | bool | No | Enable verbose output (default: false) |

## 🎮 Bid Format

Valid bid formats:
- **Suit bids**: `1C`, `1D`, `1H`, `1S`, `1N`, `2C`, ..., `7N`
- **Special calls**: `PASS`, `X` (double), `XX` (redouble)

## ⚡ Performance

- **First request**: ~50-100ms (models already loaded)
- **Subsequent requests**: ~30-80ms
- **Model loading**: ~30 seconds (happens once at startup)

## 🔒 Production Deployment

### Docker (Recommended)

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install Ben
RUN apt-get update && apt-get install -y git
RUN git clone https://github.com/lorserker/ben.git /app/ben
WORKDIR /app/ben
RUN pip install -r requirements.txt

# Install API dependencies
COPY requirements_api.txt .
RUN pip install -r requirements_api.txt

# Copy API files
COPY ben_api.py .

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "ben_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:
```bash
docker build -t ben-api .
docker run -p 8000:8000 ben-api
```

### systemd Service (Linux)

Create `/etc/systemd/system/ben-api.service`:

```ini
[Unit]
Description=Ben Bridge Bidding API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/ben
ExecStart=/usr/bin/python3 /path/to/ben_api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable ben-api
sudo systemctl start ben-api
```

## 🧪 Testing

```python
# test_api.py
import requests
import time

base_url = "http://localhost:8000"

# Wait for startup
print("Waiting for API to start...")
for _ in range(60):
    try:
        r = requests.get(f"{base_url}/health")
        if r.json().get('status') == 'healthy':
            break
    except:
        pass
    time.sleep(1)

print("✅ API ready!")

# Test bid suggestion
response = requests.post(f"{base_url}/suggest", json={
    "hand": "6.AKJT82.762.K63",
    "auction": ["1D", "3S"],
    "seat": 2,
    "dealer": 0,
    "vuln_ns": False,
    "vuln_ew": False
})

assert response.status_code == 200
result = response.json()
assert 'candidates' in result
assert len(result['candidates']) > 0

print(f"✅ Test passed! Got {len(result['candidates'])} candidates")
print(f"Best bid: {result['candidates'][0]['call']}")
```

## 🐛 Troubleshooting

**Problem**: "Models still loading, please wait"
- Solution: Wait 30-60 seconds after starting the server for models to load

**Problem**: "ModuleNotFoundError: No module named 'ben'"
- Solution: Update `ben_path` in `ben_api.py` to your Ben installation path

**Problem**: Slow first request
- Solution: This is normal - models are large. Subsequent requests are fast.

**Problem**: Out of memory
- Solution: Ben models require ~2-4GB RAM. Ensure sufficient memory is available.

## 📊 Monitoring

The API includes health check endpoints for monitoring:

```bash
# Check if ready
curl http://localhost:8000/health

# Basic status
curl http://localhost:8000/
```

Add these to your monitoring system (Prometheus, Datadog, etc.)

## 🔐 Security Notes

- The API has no authentication by default
- For production, add authentication (API keys, OAuth, etc.)
- Consider rate limiting for public deployments
- Run behind a reverse proxy (nginx, Caddy) for HTTPS

## 📝 License

Same as Ben bridge bidding engine.
