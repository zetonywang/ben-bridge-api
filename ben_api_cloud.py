"""
FastAPI server for Ben Bridge Bidding Engine - Cloud Ready Version
Loads models once at startup and keeps them in memory for fast responses
Optimized for cloud deployment (Railway, Cloud Run, DigitalOcean, Fly.io)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import sys
import os
import numpy as np
from contextlib import asynccontextmanager
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables to store loaded models
models = None
sampler = None
BotBid = None
app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models on startup, keep in memory during app lifetime"""
    global models, sampler, BotBid, app_state
    
    logger.info("🔄 Loading Ben bridge bidding models...")
    
    # Flexible path detection for different cloud environments
    possible_paths = [
        "/app/ben",           # Docker default
        "/content/ben",       # Colab
        "./ben",              # Local
        "../ben",             # Local alternative
        os.environ.get("BEN_PATH", "")  # Environment variable
    ]
    
    ben_path = None
    for path in possible_paths:
        if path and os.path.exists(path):
            ben_path = path
            logger.info(f"✅ Found Ben at: {ben_path}")
            break
    
    if not ben_path:
        logger.error("❌ Ben repository not found in any expected location")
        logger.error(f"Searched: {possible_paths}")
        raise RuntimeError("Ben repository not found. Set BEN_PATH environment variable.")
    
    src_path = os.path.join(ben_path, "src")
    
    os.chdir(ben_path)
    sys.path.insert(0, src_path)
    
    try:
        # Import Ben modules
        from nn.models_tf2 import Models
        from botbidder import BotBid as BB
        from sample import Sample
        import conf
        
        BotBid = BB
        
        # Load configuration
        config_path = './config/default.conf'
        if not os.path.exists(config_path):
            config_path = os.path.join(ben_path, 'config', 'default.conf')
        
        logger.info(f"📋 Loading config from: {config_path}")
        conf_obj = conf.load(config_path)
        
        # Load models (this is slow - only happens once!)
        logger.info("🧠 Loading neural network models (this takes ~30 seconds)...")
        models = Models.from_conf(conf_obj, '..')
        sampler = Sample.from_conf(conf_obj, False)
        
        # Disable all BBA features
        logger.info("🔧 Configuring model settings...")
        for attr in [
            "consult_bba",
            "use_bba_to_count_aces",
            "use_bba_to_count_keycards",
            "use_bba_to_estimate_shape",
            "use_bba_for_sampling",
            "use_bba"
        ]:
            if hasattr(models, attr):
                setattr(models, attr, False)
        
        # Monkeypatch BBA
        BB.bbabot = property(lambda self: None)
        
        app_state['ready'] = True
        app_state['ben_path'] = ben_path
        logger.info("✅ Models loaded and ready!")
        logger.info(f"💾 Memory usage: Models cached in RAM for fast responses")
        
    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}")
        raise
    
    yield
    
    # Cleanup (if needed)
    logger.info("🔴 Shutting down...")
    app_state['ready'] = False


app = FastAPI(
    title="Ben Bridge Bidding API",
    description="Fast API for Ben bridge bidding suggestions - Cloud Ready",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BidRequest(BaseModel):
    """Request model for bid suggestions"""
    hand: str = Field(..., description="Hand in format: 'KQJ.AT2.9876.AK3'")
    auction: List[str] = Field(default=[], description="List of bids so far, e.g. ['1D', '3S']")
    seat: int = Field(..., ge=0, le=3, description="Seat position (0=North, 1=East, 2=South, 3=West)")
    dealer: int = Field(..., ge=0, le=3, description="Dealer position (0=North, 1=East, 2=South, 3=West)")
    vuln_ns: bool = Field(default=False, description="North-South vulnerable")
    vuln_ew: bool = Field(default=False, description="East-West vulnerable")
    verbose: bool = Field(default=False, description="Enable verbose output")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hand": "6.AKJT82.762.K63",
                "auction": ["1D", "3S"],
                "seat": 2,
                "dealer": 0,
                "vuln_ns": False,
                "vuln_ew": False
            }
        }


class BidCandidate(BaseModel):
    """A single bid candidate with scoring"""
    call: str
    insta_score: float
    expected_score: Optional[float] = None
    explanation: Optional[str] = None


class BidResponse(BaseModel):
    """Response model for bid suggestions"""
    passout: bool
    candidates: List[BidCandidate]
    hand: str
    auction: List[str]


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "ready": app_state.get('ready', False),
        "service": "Ben Bridge Bidding API",
        "version": "2.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "suggest": "/suggest",
            "suggest_simple": "/suggest-simple"
        }
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    ready = app_state.get('ready', False)
    return {
        "status": "healthy" if ready else "loading",
        "models_loaded": models is not None,
        "sampler_loaded": sampler is not None,
        "ben_path": app_state.get('ben_path', 'unknown'),
        "ready_for_requests": ready
    }


@app.post("/suggest", response_model=BidResponse)
async def suggest_bid(request: BidRequest):
    """
    Get bid suggestions for a given hand and auction
    
    - **hand**: Hand in format 'SPADES.HEARTS.DIAMONDS.CLUBS' (e.g., 'KQJ97.AT2.9876.AK3')
    - **auction**: List of previous bids (e.g., ['1D', '3S', 'PASS'])
    - **seat**: Your position (0=North, 1=East, 2=South, 3=West)
    - **dealer**: Who dealt (0=North, 1=East, 2=South, 3=West)
    - **vuln_ns**: Are North-South vulnerable?
    - **vuln_ew**: Are East-West vulnerable?
    """
    
    if not app_state.get('ready', False):
        raise HTTPException(
            status_code=503, 
            detail="Models still loading, please wait 30-60 seconds and try again"
        )
    
    try:
        # Create BotBid instance
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
        
        # Get bid candidates
        candidates, passout = bot.get_bid_candidates(request.auction)
        
        # Format response
        formatted_candidates = []
        for c in candidates:
            candidate_dict = {
                "call": c.bid,
                "insta_score": float(c.insta_score),
            }
            
            # Add expected_score if available
            es = getattr(c, "expected_score", None)
            if es is not None:
                try:
                    candidate_dict["expected_score"] = float(es)
                except (TypeError, ValueError):
                    pass
            
            # Add explanation if available
            if hasattr(c, "explanation"):
                candidate_dict["explanation"] = c.explanation
            
            formatted_candidates.append(BidCandidate(**candidate_dict))
        
        return BidResponse(
            passout=bool(passout),
            candidates=formatted_candidates,
            hand=request.hand,
            auction=request.auction
        )
        
    except Exception as e:
        logger.error(f"Error processing bid: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing bid: {str(e)}")


@app.post("/suggest-simple")
async def suggest_bid_simple(request: BidRequest):
    """
    Simplified endpoint that returns raw dict (no strict validation)
    Faster and more flexible than /suggest
    """
    if not app_state.get('ready', False):
        raise HTTPException(
            status_code=503, 
            detail="Models still loading, please wait 30-60 seconds and try again"
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
        
        out = []
        for c in candidates:
            d = {
                "call": c.bid,
                "insta_score": float(c.insta_score),
            }
            es = getattr(c, "expected_score", None)
            if es is not None:
                try:
                    d["expected_score"] = float(es)
                except (TypeError, ValueError):
                    pass
            if hasattr(c, "explanation"):
                d["explanation"] = c.explanation
            out.append(d)
        
        return {
            "passout": bool(passout),
            "candidates": out,
            "hand": request.hand,
            "auction": request.auction
        }
        
    except Exception as e:
        logger.error(f"Error processing bid: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing bid: {str(e)}")


# Optional: Add a simple test endpoint
@app.get("/test")
async def test_endpoint():
    """Quick test to verify API is working"""
    if not app_state.get('ready', False):
        return {"status": "Models still loading..."}
    
    try:
        # Simple test bid
        bot = BotBid(
            [False, False],
            "KQJ97.AT2.9876.AK3",
            models,
            sampler,
            seat=2,
            dealer=0,
            ddsolver=None,
            bba_is_controlling=False,
            verbose=False,
        )
        candidates, _ = bot.get_bid_candidates([])
        
        return {
            "status": "Working!",
            "test_result": f"Opening bid suggestion: {candidates[0].bid if candidates else 'PASS'}",
            "ready": True
        }
    except Exception as e:
        return {
            "status": "Error in test",
            "error": str(e),
            "ready": False
        }


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (for cloud platforms)
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )
