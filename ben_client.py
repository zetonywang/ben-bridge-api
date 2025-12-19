"""
Python client for Ben Bridge Bidding API
Usage example:
    from ben_client import BenClient
    
    client = BenClient("http://localhost:8000")
    result = client.suggest_bid(
        hand="6.AKJT82.762.K63",
        auction=["1D", "3S"],
        seat=2,
        dealer=0
    )
    print(result)
"""

import requests
from typing import List, Optional, Dict, Any


class BenClient:
    """Client for interacting with Ben Bridge Bidding API"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize client
        
        Args:
            base_url: Base URL of the API server
        """
        self.base_url = base_url.rstrip('/')
    
    def health_check(self) -> Dict[str, Any]:
        """Check if API is ready"""
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def is_ready(self) -> bool:
        """Check if models are loaded and ready"""
        try:
            health = self.health_check()
            return health.get('status') == 'healthy'
        except:
            return False
    
    def suggest_bid(
        self,
        hand: str,
        auction: List[str] = None,
        seat: int = 2,
        dealer: int = 0,
        vuln_ns: bool = False,
        vuln_ew: bool = False,
        verbose: bool = False,
        simple: bool = False
    ) -> Dict[str, Any]:
        """
        Get bid suggestions
        
        Args:
            hand: Hand in format 'SPADES.HEARTS.DIAMONDS.CLUBS'
            auction: List of previous bids (default: empty)
            seat: Your position (0=N, 1=E, 2=S, 3=W)
            dealer: Who dealt (0=N, 1=E, 2=S, 3=W)
            vuln_ns: North-South vulnerable
            vuln_ew: East-West vulnerable
            verbose: Enable verbose output
            simple: Use simple endpoint (less validation)
        
        Returns:
            Dictionary with 'passout' and 'candidates' keys
        """
        if auction is None:
            auction = []
        
        payload = {
            "hand": hand,
            "auction": auction,
            "seat": seat,
            "dealer": dealer,
            "vuln_ns": vuln_ns,
            "vuln_ew": vuln_ew,
            "verbose": verbose
        }
        
        endpoint = "/suggest-simple" if simple else "/suggest"
        response = requests.post(
            f"{self.base_url}{endpoint}",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_best_bid(
        self,
        hand: str,
        auction: List[str] = None,
        seat: int = 2,
        dealer: int = 0,
        vuln_ns: bool = False,
        vuln_ew: bool = False
    ) -> str:
        """
        Get the single best bid recommendation
        
        Returns:
            The recommended bid as a string (e.g., "4H", "PASS", "X")
        """
        result = self.suggest_bid(
            hand=hand,
            auction=auction,
            seat=seat,
            dealer=dealer,
            vuln_ns=vuln_ns,
            vuln_ew=vuln_ew,
            simple=True
        )
        
        if result.get('passout', False):
            return "PASS (auction ended)"
        
        candidates = result.get('candidates', [])
        if not candidates:
            return "PASS"
        
        # Return the first candidate (highest score)
        return candidates[0]['call']


# Example usage
if __name__ == "__main__":
    client = BenClient("http://localhost:8000")
    
    # Check if ready
    if not client.is_ready():
        print("⏳ Waiting for API to be ready...")
        import time
        while not client.is_ready():
            time.sleep(1)
    
    print("✅ API is ready!")
    
    # Example 1: Get full suggestions
    result = client.suggest_bid(
        hand="6.AKJT82.762.K63",
        auction=["1D", "3S"],
        seat=2,
        dealer=0
    )
    
    print("\n📋 Full suggestions:")
    for i, candidate in enumerate(result['candidates'], 1):
        print(f"{i}. {candidate['call']} (score: {candidate['insta_score']:.3f})")
    
    # Example 2: Get just the best bid
    best = client.get_best_bid(
        hand="KQJ97432.Q2.Q.52",
        auction=["1D", "X", "XX", "1H", "X", "PASS", "4S", "PASS", "PASS", "X"],
        seat=2,
        dealer=0
    )
    
    print(f"\n🎯 Best bid: {best}")
