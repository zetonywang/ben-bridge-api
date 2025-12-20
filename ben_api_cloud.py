"""
FastAPI server for Ben Bridge Bidding Engine - FIXED Config Path
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import sys
import os
import logging
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models = None
sampler = None
BotBid = None
app_state = {'ready': False, 'error': None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global models, sampler, BotBid, app_state
    
    logger.info("🔄 Loading Ben bridge bidding models...")
    
    try:
        ben_path = "/app/ben"
        src_path = os.path.join(ben_path, "src")
        
        if not os.path.exists(ben_path):
            raise RuntimeError(f"Ben not found at {ben_path}")
        
        logger.info(f"✅ Found Ben at: {ben_path}")
        
        os.chdir(ben_path)
        sys.path.insert(0, src_path)
        
        from nn.models_tf2 import Models
        from botbidder import BotBid as BB
        from sample import Sample
        import conf
        
        BotBid = BB
        
        # Try multiple config paths
        config_paths = [
            'config/default.conf',
            'src/config/default.conf',
            '/app/ben/config/default.conf',
            '/app/ben/src/config/default.conf',
        ]
        
        config_path = None
        for path in config_paths:
            full_path = os.path.join(ben_path, path) if not os.path.isabs(path) else path
            logger.info(f"Trying config path: {full_path}")
            if os.path.exists(full_path):
                config_path = path if not os.path.isabs(path) else full_path
                logger.info(f"✅ Found config at: {full_path}")
                break
        
        if not config_path:
            # List what's actually in the ben directory
            logger.error(f"Config not found. Ben directory contents:")
            for root, dirs, files in os.walk(ben_path):
                level = root.replace(ben_path, '').count(os.sep)
                indent = ' ' * 2 * level
                logger.error(f'{indent}{os.path.basename(root)}/')
                subindent = ' ' * 2 * (level + 1)
                for file in files[:10]:  # First 10 files
                    logger.error(f'{subindent}{file}')
                if level > 2:  # Don't go too deep
                    break
            raise RuntimeError("Config file not found in any expected location")
        
        logger.info(f"📋 Loading config from: {config_path}")
        conf_obj = conf.load(config_path)
        
        logger.info("🧠 Loading neural network models...")
        models = Models.from_conf(conf_obj, '..')
        sampler = Sample.from_conf(conf_obj, False)
        
        for attr in ["consult_bba", "use_bba_to_count_aces", "use_bba_to_count_keycards", 
                     "use_bba_to_estimate_shape", "use_bba_for_sampling", "use_bba"]:
            if hasattr(models, attr):
                setattr(models, attr, False)
        
        BB.bbabot = property(lambda self: None)
        
        app_state['ready'] = True
        logger.info("✅ Models loaded and ready!")
        
    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}", exc_info=True)
        app_state['error'] = str(e)
        raise
    
    yield
    
    logger.info("🔴 Shutting down...")


app = FastAPI(title="Ben Bridge Bidding API", version="3.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BidRequest(BaseModel):
    hand: str = Field(..., description="Hand in format: 'KQJ.AT2.9876.AK3'")
    auction: List[str] = Field(default=[], description="List of bids")
    seat: int = Field(..., ge=0, le=3)
    dealer: int = Field(..., ge=0, le=3)
    vuln_ns: bool = Field(default=False)
    vuln_ew: bool = Field(default=False)
    verbose: bool = Field(default=False)


class BidCandidate(BaseModel):
    call: str
    insta_score: float
    expected_score: Optional[float] = None
    explanation: Optional[str] = None


class BidResponse(BaseModel):
    passout: bool
    candidates: List[BidCandidate]
    hand: str
    auction: List[str]


@app.get("/")
def root():
    return {
        "status": "online",
        "ready": app_state.get('ready', False),
        "error": app_state.get('error'),
        "service": "Ben Bridge Bidding API"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy" if app_state.get('ready') else "loading",
        "models_loaded": app_state.get('ready', False),
        "error": app_state.get('error')
    }


@app.post("/suggest", response_model=BidResponse)
def suggest_bid(request: BidRequest):
    if not app_state.get('ready'):
        raise HTTPException(
            status_code=503,
            detail=f"Models not ready. Error: {app_state.get('error', 'Still loading...')}"
        )
    
    try:
        bot = BotBid(
            [request.vuln_ns, request.vuln_ew],
            request.hand,
            models,
            sampler,
            seat=request.seat,
            dealer=request.dealer,
            ddsolver=None,
            bba_is_controlling=False,
            verbose=request.verbose,
        )
        
        candidates, passout = bot.get_bid_candidates(request.auction)
        
        formatted_candidates = []
        for c in candidates:
            d = {"call": c.bid, "insta_score": float(c.insta_score)}
            es = getattr(c, "expected_score", None)
            if es is not None:
                try:
                    d["expected_score"] = float(es)
                except (TypeError, ValueError):
                    pass
            if hasattr(c, "explanation"):
                d["explanation"] = c.explanation
            formatted_candidates.append(BidCandidate(**d))
        
        return BidResponse(
            passout=bool(passout),
            candidates=formatted_candidates,
            hand=request.hand,
            auction=request.auction
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
