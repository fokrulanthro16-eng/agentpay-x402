"""AgentPay-x402 Server Configuration.

Handles environment configuration using Pydantic Settings, including:
- Merchant public key configuration and auto-initialization.
- Solana RPC endpoint configuration (default: Devnet).
- Dynamic price registry mapping protected endpoints to lamports.
- Gateway networking and commitment configurations.
"""

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Dict

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from solders.keypair import Keypair
from solders.pubkey import Pubkey

logger = logging.getLogger("agentpay.config")


def get_or_create_merchant_keypair(keypair_path: Path) -> Keypair:
    """Load existing merchant keypair or generate and persist a new one."""
    if keypair_path.exists():
        try:
            with open(keypair_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Keypair.from_bytes(bytes(data))
        except Exception as e:
            logger.warning(
                f"Failed to read existing keypair from {keypair_path}: {e}. Generating new keypair."
            )

    keypair = Keypair()
    try:
        keypair_path.parent.mkdir(parents=True, exist_ok=True)
        with open(keypair_path, "w", encoding="utf-8") as f:
            json.dump(list(bytes(keypair)), f)
        logger.info(f"Initialized merchant keypair at {keypair_path}")
    except Exception as e:
        logger.warning(f"Could not persist merchant keypair to {keypair_path}: {e}")
    return keypair


class ServerSettings(BaseSettings):
    """Production server settings with Pydantic v2 Settings."""

    # Solana Devnet RPC endpoint
    solana_rpc_url: str = Field(
        default="https://api.devnet.solana.com",
        description="Solana RPC endpoint URL (Devnet)",
        validation_alias="SOLANA_RPC_URL",
    )

    # Merchant receiving public key
    merchant_public_key: str = Field(
        default="",
        description="Base58 Solana public key of the merchant receiving payment",
        validation_alias="MERCHANT_PUBLIC_KEY",
    )

    # Merchant keypair file path (used if merchant_public_key is not explicitly set)
    merchant_keypair_path: str = Field(
        default="merchant_keypair.json",
        description="Path to merchant keypair JSON file",
        validation_alias="MERCHANT_KEYPAIR_PATH",
    )

    # Network identification
    network: str = Field(
        default="solana-devnet",
        description="Target Solana network identifier",
        validation_alias="SOLANA_NETWORK",
    )

    # RPC commitment level ('confirmed' or 'finalized')
    commitment: str = Field(
        default="confirmed",
        description="Target Solana RPC confirmation commitment",
        validation_alias="SOLANA_COMMITMENT",
    )

    # Gateway Replay Protection TTL
    replay_cache_ttl_seconds: int = Field(
        default=86400,
        description="Time-to-live for signature cache entries in seconds (24h default)",
        validation_alias="REPLAY_CACHE_TTL_SECONDS",
    )

    # Dynamic price registry per protected endpoint (in lamports)
    # Default: 20,000 lamports for deep alpha market feed, 5,000 lamports for standard agent inference
    price_registry: Dict[str, int] = Field(
        default_factory=lambda: {
            "/api/v1/market-feed": 20_000,
            "/api/v1/agent-inference": 5_000,
        },
        description="Dynamic price mapping from endpoint path to required lamports",
    )

    # Server binding
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")

    # Simulation / Mock settlement mode (enables testing when Devnet faucet is throttled)
    mock_settlement: bool = Field(
        default=False,
        description="Enable simulated settlement validation when public Devnet faucets are rate-limited",
        validation_alias="MOCK_SETTLEMENT",
    )

    # Alpaca Paper Trading Credentials & URL
    ALPACA_API_KEY: str = Field(
        default="PKV6FTKSBFEBUW45T4ME6AVBBE",
        description="Alpaca Paper Trading API Key ID",
        validation_alias="ALPACA_API_KEY",
    )
    ALPACA_SECRET_KEY: str = Field(
        default="AxTbThigrfmXChC7H1ywTEgQehvvwR7fy1z3LfP4VhWgv",
        description="Alpaca Paper Trading Secret Key",
        validation_alias="ALPACA_SECRET_KEY",
    )
    ALPACA_BASE_URL: str = Field(
        default="https://paper-api.alpaca.markets",
        description="Alpaca Base API Endpoint",
        validation_alias="ALPACA_BASE_URL",
    )

    # Nebius Token Factory Credentials & Configuration
    NEBIUS_BASE_URL: str = Field(
        default="https://api.tokenfactory.nebius.com/v1",
        description="Nebius Token Factory OpenAI-compatible base URL",
        validation_alias="NEBIUS_BASE_URL",
    )
    NEBIUS_API_KEY: str = Field(
        default="v1.CmQKHHN0YXRpY2tleS1lMDB4c3Nnc2tjZDY3Z3I4M3gSIXNlcnZpY2VhY2NvdW50LWUwMGcwMDlqeXR3M2tjMGplODIMCOzrqdYGEJGLmYABOgwI6-7BoQcQgLSSjQFAAloDZTAw.AAAAAAAAAAFAIcPNAJx40-O8nE3XMudUQdcjLdjApF4SJfqVcLad7uUWbXFcVHMrtd33GqVe2EKgy0khWLFF3wXCBLRDjbMJ",
        description="Nebius Token Factory API Bearer Token",
        validation_alias="NEBIUS_API_KEY",
    )
    NEBIUS_MODEL: str = Field(
        default="nvidia/Llama-3.1-Nemotron-70B-Instruct",
        description="Primary Nebius AI Model for Agent Inference",
        validation_alias="NEBIUS_MODEL",
    )
    NEBIUS_FALLBACK_MODEL: str = Field(
        default="nvidia/Nemotron-3_5-Lightning",
        description="Fallback Nebius Model (e.g. meta-llama/Meta-Llama-3.1-70B-Instruct or nvidia/Nemotron-3_5-Lightning)",
        validation_alias="NEBIUS_FALLBACK_MODEL",
    )

    # Lowercase property aliases for backward compatibility
    @property
    def alpaca_api_key(self) -> str:
        return self.ALPACA_API_KEY

    @property
    def alpaca_secret_key(self) -> str:
        return self.ALPACA_SECRET_KEY

    @property
    def alpaca_base_url(self) -> str:
        return self.ALPACA_BASE_URL

    @property
    def nebius_base_url(self) -> str:
        return self.NEBIUS_BASE_URL

    @property
    def nebius_api_key(self) -> str:
        return self.NEBIUS_API_KEY

    @property
    def nebius_model(self) -> str:
        return self.NEBIUS_MODEL

    @property
    def nebius_fallback_model(self) -> str:
        return self.NEBIUS_FALLBACK_MODEL

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("merchant_public_key", mode="after")
    @classmethod
    def validate_or_populate_merchant_key(cls, v: str) -> str:
        """Validate base58 pubkey or auto-generate fallback merchant pubkey."""
        v = v.strip()
        if v:
            try:
                # Validate pubkey format using solders
                Pubkey.from_string(v)
                return v
            except Exception as e:
                raise ValueError(f"Invalid Solana base58 public key for merchant: {e}")

        # Auto-generate or load default merchant keypair
        keypair_file = Path("merchant_keypair.json")
        merchant_kp = get_or_create_merchant_keypair(keypair_file)
        return str(merchant_kp.pubkey())

    def get_price(self, endpoint_path: str) -> int:
        """Retrieve dynamic price for an endpoint in lamports.

        Falls back to 5,000 lamports if endpoint is not registered.
        """
        # Exact match
        if endpoint_path in self.price_registry:
            return self.price_registry[endpoint_path]

        # Normalized path match (strip trailing slash)
        normalized = endpoint_path.rstrip("/")
        if normalized in self.price_registry:
            return self.price_registry[normalized]

        for path, price in self.price_registry.items():
            if normalized.endswith(path.rstrip("/")):
                return price

        return 5_000


@lru_cache()
def get_settings() -> ServerSettings:
    """Retrieve cached singleton instance of ServerSettings."""
    return ServerSettings()
