import httpx
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from ..config import settings
from ..utils import get_logger
from .metrics import metrics

logger = get_logger(__name__)


class OryAuthService:
    """Service for handling OAuth2 authentication with Ory Hydra"""
    
    def __init__(self):
        self.hydra_admin_url = settings.hydra_admin_url
        self.hydra_public_url = settings.hydra_public_url
        self.client_id = settings.oauth2_client_id
        self.client_secret = settings.oauth2_client_secret
        self.scope = settings.oauth2_scope
        
        # Token caching
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._token_lock = asyncio.Lock()
    
    async def get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary"""
        async with self._token_lock:
            if self._is_token_valid():
                return self._access_token
            
            logger.info("Generating new OAuth2 access token")
            return await self._generate_client_credentials_token()
    
    def _is_token_valid(self) -> bool:
        """Check if current token is valid and not expired"""
        if not self._access_token or not self._token_expires_at:
            return False
        
        # Add 60 second buffer before expiry
        return datetime.now() < (self._token_expires_at - timedelta(seconds=60))
    
    async def _generate_client_credentials_token(self) -> str:
        """Generate access token using client credentials flow"""
        import base64
        
        # Use Basic Authentication (client_secret_basic) instead of client_secret_post
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        form_data = {
            "grant_type": "client_credentials",
            "scope": self.scope,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                start_time = time.time()
                response = await client.post(
                    f"{self.hydra_public_url}/oauth2/token",
                    headers=headers,
                    data=form_data
                )
                
                duration = time.time() - start_time
                metrics.record_api_request("/oauth2/token", "POST", response.status_code, duration)
                
                if response.status_code != 200:
                    logger.error(
                        "Failed to generate OAuth2 token",
                        status_code=response.status_code,
                        response=response.text
                    )
                    raise Exception(f"OAuth2 token generation failed: {response.status_code}")
                
                token_data = response.json()
                
                # Cache the token
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info(
                    "Successfully generated OAuth2 token",
                    expires_in=expires_in,
                    token_type=token_data.get("token_type", "bearer")
                )
                
                return self._access_token
                
        except httpx.TimeoutException:
            logger.error("Timeout while generating OAuth2 token")
            raise Exception("OAuth2 token generation timeout")
        except Exception as e:
            logger.error("Error generating OAuth2 token", error=str(e))
            raise
    
    async def introspect_token(self, token: str) -> Dict[str, Any]:
        """Introspect a token to validate it"""
        form_data = {
            "token": token
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                start_time = time.time()
                response = await client.post(
                    f"{self.hydra_admin_url}/oauth2/introspect",
                    headers=headers,
                    data=form_data
                )
                
                duration = time.time() - start_time
                metrics.record_api_request("/oauth2/introspect", "POST", response.status_code, duration)
                
                if response.status_code != 200:
                    logger.error(
                        "Failed to introspect token",
                        status_code=response.status_code
                    )
                    raise Exception(f"Token introspection failed: {response.status_code}")
                
                return response.json()
                
        except httpx.TimeoutException:
            logger.error("Timeout while introspecting token")
            raise Exception("Token introspection timeout")
        except Exception as e:
            logger.error("Error introspecting token", error=str(e))
            raise
    
    async def create_oauth2_client(self, client_name: str, scopes: list[str]) -> Dict[str, Any]:
        """Create a new OAuth2 client (admin operation)"""
        client_data = {
            "client_name": client_name,
            "grant_types": ["client_credentials"],
            "response_types": ["token"],
            "scope": " ".join(scopes),
            "token_endpoint_auth_method": "client_secret_post",
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                start_time = time.time()
                response = await client.post(
                    f"{self.hydra_admin_url}/clients",
                    headers=headers,
                    json=client_data
                )
                
                duration = time.time() - start_time
                metrics.record_api_request("/clients", "POST", response.status_code, duration)
                
                if response.status_code not in [200, 201]:
                    logger.error(
                        "Failed to create OAuth2 client",
                        status_code=response.status_code,
                        response=response.text
                    )
                    raise Exception(f"OAuth2 client creation failed: {response.status_code}")
                
                logger.info("Successfully created OAuth2 client", client_name=client_name)
                return response.json()
                
        except httpx.TimeoutException:
            logger.error("Timeout while creating OAuth2 client")
            raise Exception("OAuth2 client creation timeout")
        except Exception as e:
            logger.error("Error creating OAuth2 client", error=str(e))
            raise


# Global instance
ory_auth = OryAuthService()