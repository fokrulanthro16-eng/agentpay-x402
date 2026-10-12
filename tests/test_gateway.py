"""Comprehensive Unit and Integration Tests for AgentPay-x402."""

import asyncio
import json
from pathlib import Path
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature

from client.wallet_manager import SolanaWalletManager
from server.config import ServerSettings
from server.main import app
from server.verifier import (
    InsufficientPaymentError,
    InvalidRecipientError,
    InvalidSignatureFormatError,
    PaymentVerificationError,
    ReplayAttackError,
    ReplayProtectionCache,
    SolanaTransactionVerifier,
    TransactionFailedError,
    TransactionNotFoundError,
    VerificationResult,
)


@pytest.fixture
def temp_keypair_file():
    """Create a temporary keypair file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_keypair.json"


@pytest.fixture
def sample_merchant_keypair():
    """Return a generated Keypair for merchant testing."""
    return Keypair()


@pytest.fixture
def sample_agent_keypair():
    """Return a generated Keypair for agent testing."""
    return Keypair()


# --- Configuration Tests ---


def test_server_config_defaults():
    """Test ServerSettings defaults and dynamic pricing lookup."""
    settings = ServerSettings()
    assert settings.solana_rpc_url == "https://api.devnet.solana.com"
    assert settings.network == "solana-devnet"
    assert settings.commitment == "confirmed"
    assert settings.get_price("/api/v1/market-feed") == 20_000
    assert settings.get_price("/api/v1/agent-inference") == 5_000
    assert settings.get_price("/unknown/endpoint") == 5_000
    assert len(settings.merchant_public_key) > 30


# --- Replay Protection Cache Tests ---


@pytest.mark.asyncio
async def test_replay_protection_cache():
    """Test replay cache record, check, and TTL cleanup."""
    cache = ReplayProtectionCache(ttl_seconds=1)
    sig = str(Signature.default())

    assert not await cache.is_seen(sig)
    await cache.record(sig, details={"amount": 5000})
    assert await cache.is_seen(sig)

    details = await cache.get_details(sig)
    assert details is not None
    assert details["amount"] == 5000

    # Wait for TTL expiry
    await asyncio.sleep(1.1)
    purged = await cache.cleanup()
    assert purged == 1
    assert not await cache.is_seen(sig)


# --- Verifier Validation Tests ---


@pytest.mark.asyncio
async def test_verifier_malformed_signature():
    """Test that malformed signature strings raise InvalidSignatureFormatError."""
    verifier = SolanaTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        merchant_pubkey=str(Keypair().pubkey()),
    )

    with pytest.raises(InvalidSignatureFormatError):
        await verifier.verify_payment(
            signature_str="NOT_A_VALID_BASE58_SIGNATURE!!!",
            required_lamports=5000,
        )


@pytest.mark.asyncio
async def test_verifier_replay_detection():
    """Test that already processed signatures trigger ReplayAttackError."""
    cache = ReplayProtectionCache()
    sig = str(Keypair().sign_message(b"dummy_tx"))
    await cache.record(sig)

    verifier = SolanaTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        merchant_pubkey=str(Keypair().pubkey()),
        replay_cache=cache,
    )

    with pytest.raises(ReplayAttackError):
        await verifier.verify_payment(
            signature_str=sig,
            required_lamports=5000,
        )


@pytest.mark.asyncio
async def test_verifier_mocked_settlement_success(sample_merchant_keypair, sample_agent_keypair):
    """Test complete successful verification workflow with a mocked RPC client."""
    merchant_pubkey = str(sample_merchant_keypair.pubkey())
    agent_pubkey = str(sample_agent_keypair.pubkey())
    dummy_sig = str(Keypair().sign_message(b"settlement_tx"))

    # Mock RPC get_transaction response
    mock_rpc = AsyncMock()

    # Build simulated Solders object structure
    mock_tx_resp = MagicMock()
    mock_confirmed_tx = MagicMock()
    mock_confirmed_tx.slot = 12345678
    mock_confirmed_tx.block_time = int(time.time())

    mock_msg = MagicMock()
    mock_msg.account_keys = [sample_agent_keypair.pubkey(), sample_merchant_keypair.pubkey()]

    mock_meta = MagicMock()
    mock_meta.err = None
    mock_meta.loaded_addresses = None
    # Agent balance: drops by 20,005 lamports (20,000 + 5 fee)
    # Merchant balance: increases from 100,000 to 120,000 (+20,000 lamports)
    mock_meta.pre_balances = [500_000, 100_000]
    mock_meta.post_balances = [479_995, 120_000]

    mock_confirmed_tx.transaction.transaction.message = mock_msg
    mock_confirmed_tx.transaction.meta = mock_meta
    mock_tx_resp.value = mock_confirmed_tx

    mock_rpc.get_transaction.return_value = mock_tx_resp

    verifier = SolanaTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        merchant_pubkey=merchant_pubkey,
        rpc_client=mock_rpc,
    )

    result = await verifier.verify_payment(
        signature_str=dummy_sig,
        required_lamports=20_000,
    )

    assert result.valid is True
    assert result.amount_lamports == 20_000
    assert result.recipient == merchant_pubkey
    assert result.sender == agent_pubkey
    assert result.slot == 12345678

    # Ensure signature was placed into replay cache
    assert await verifier.replay_cache.is_seen(dummy_sig)


@pytest.mark.asyncio
async def test_verifier_mocked_insufficient_payment(sample_merchant_keypair, sample_agent_keypair):
    """Test that transferring less than required lamports raises InsufficientPaymentError."""
    merchant_pubkey = str(sample_merchant_keypair.pubkey())
    dummy_sig = str(Keypair().sign_message(b"underpaid_tx"))

    mock_rpc = AsyncMock()
    mock_tx_resp = MagicMock()
    mock_confirmed_tx = MagicMock()
    mock_msg = MagicMock()
    mock_msg.account_keys = [sample_agent_keypair.pubkey(), sample_merchant_keypair.pubkey()]

    mock_meta = MagicMock()
    mock_meta.err = None
    mock_meta.loaded_addresses = None
    # Merchant only received 5,000 lamports, but 20,000 was required
    mock_meta.pre_balances = [500_000, 100_000]
    mock_meta.post_balances = [495_000, 105_000]

    mock_confirmed_tx.transaction.transaction.message = mock_msg
    mock_confirmed_tx.transaction.meta = mock_meta
    mock_tx_resp.value = mock_confirmed_tx
    mock_rpc.get_transaction.return_value = mock_tx_resp

    verifier = SolanaTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        merchant_pubkey=merchant_pubkey,
        rpc_client=mock_rpc,
    )

    with pytest.raises(InsufficientPaymentError):
        await verifier.verify_payment(
            signature_str=dummy_sig,
            required_lamports=20_000,
        )


@pytest.mark.asyncio
async def test_verifier_mocked_wrong_recipient(sample_agent_keypair):
    """Test that a transaction without the merchant pubkey raises InvalidRecipientError."""
    actual_merchant = str(Keypair().pubkey())
    unrelated_pubkey = Keypair().pubkey()
    dummy_sig = str(Keypair().sign_message(b"wrong_recipient_tx"))

    mock_rpc = AsyncMock()
    mock_tx_resp = MagicMock()
    mock_confirmed_tx = MagicMock()
    mock_msg = MagicMock()
    # Merchant is not in the account keys
    mock_msg.account_keys = [sample_agent_keypair.pubkey(), unrelated_pubkey]

    mock_meta = MagicMock()
    mock_meta.err = None
    mock_meta.loaded_addresses = None
    mock_meta.pre_balances = [500_000, 100_000]
    mock_meta.post_balances = [480_000, 120_000]

    mock_confirmed_tx.transaction.transaction.message = mock_msg
    mock_confirmed_tx.transaction.meta = mock_meta
    mock_tx_resp.value = mock_confirmed_tx
    mock_rpc.get_transaction.return_value = mock_tx_resp

    verifier = SolanaTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        merchant_pubkey=actual_merchant,
        rpc_client=mock_rpc,
    )

    with pytest.raises(InvalidRecipientError):
        await verifier.verify_payment(
            signature_str=dummy_sig,
            required_lamports=20_000,
        )


# --- Wallet Manager Tests ---


def test_wallet_manager_create_and_reload(temp_keypair_file):
    """Test generating, saving, and reloading a wallet keypair."""
    mgr1 = SolanaWalletManager(keypair_path=temp_keypair_file)
    pubkey1 = mgr1.pubkey_str
    assert temp_keypair_file.exists()

    mgr2 = SolanaWalletManager(keypair_path=temp_keypair_file)
    pubkey2 = mgr2.pubkey_str
    assert pubkey1 == pubkey2


# --- FastAPI HTTP 402 Integration Tests ---


@pytest.mark.asyncio
async def test_gateway_health_endpoint():
    """Test GET /health returns metadata and pricing registry."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["network"] == "solana-devnet"
        assert "/api/v1/market-feed" in data["pricing"]
        assert "/api/v1/agent-inference" in data["pricing"]


@pytest.mark.asyncio
async def test_gateway_402_challenge_market_feed():
    """Test GET /api/v1/market-feed returns HTTP 402 with headers and matching body."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/market-feed")
        assert resp.status_code == 402

        # Verify RFC/x402 compliant response headers
        assert "X-402-Recipient" in resp.headers
        assert resp.headers["X-402-Amount"] == "20000"
        assert resp.headers["X-402-Network"] == "solana-devnet"
        assert resp.headers["X-402-Token"] == "SOL"

        # Verify response body
        body = resp.json()
        assert body["error"] == "Payment Required"
        assert body["amount_lamports"] == 20000
        assert body["token"] == "SOL"
        assert body["network"] == "solana-devnet"
        assert body["recipient"] == resp.headers["X-402-Recipient"]


@pytest.mark.asyncio
async def test_gateway_402_challenge_agent_inference():
    """Test POST /api/v1/agent-inference returns HTTP 402 with 5000 lamports challenge."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/agent-inference",
            json={"prompt": "Compute optimal Raydium route"},
        )
        assert resp.status_code == 402

        # Verify headers and body
        assert resp.headers["X-402-Amount"] == "5000"
        body = resp.json()
        assert body["amount_lamports"] == 5000
        assert body["token"] == "SOL"


@pytest.mark.asyncio
async def test_gateway_settled_payment_market_feed(sample_merchant_keypair, sample_agent_keypair):
    """Test accessing /api/v1/market-feed with verified X-402-Signature delivers 200 OK."""
    transport = httpx.ASGITransport(app=app)
    dummy_sig = str(Keypair().sign_message(b"live_call_feed"))

    # Mock the app's verifier to accept dummy_sig
    mock_verifier = MagicMock()
    mock_result = VerificationResult(
        valid=True,
        signature=dummy_sig,
        slot=987654,
        amount_lamports=20_000,
        sender=str(sample_agent_keypair.pubkey()),
        recipient=str(sample_merchant_keypair.pubkey()),
        confirmation_status="confirmed",
        block_time=int(time.time()),
        message="Payment verified.",
    )
    mock_verifier.verify_payment = AsyncMock(return_value=mock_result)

    # Temporarily override verifier in app state
    original_verifier = getattr(app.state, "verifier", None)
    app.state.verifier = mock_verifier

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/market-feed",
                headers={"X-402-Signature": dummy_sig},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["feed"] == "solana_defi_deep_alpha"
            assert "market_snapshot" in data
            assert data["settlement_receipt"]["signature"] == dummy_sig
            assert data["settlement_receipt"]["amount_lamports"] == 20_000
    finally:
        if original_verifier:
            app.state.verifier = original_verifier


@pytest.mark.asyncio
async def test_gateway_settled_payment_agent_inference(sample_merchant_keypair, sample_agent_keypair):
    """Test accessing /api/v1/agent-inference with verified signature delivers compute."""
    transport = httpx.ASGITransport(app=app)
    dummy_sig = str(Keypair().sign_message(b"live_call_infer"))

    mock_verifier = MagicMock()
    mock_result = VerificationResult(
        valid=True,
        signature=dummy_sig,
        slot=987655,
        amount_lamports=5_000,
        sender=str(sample_agent_keypair.pubkey()),
        recipient=str(sample_merchant_keypair.pubkey()),
        confirmation_status="confirmed",
        block_time=int(time.time()),
        message="Payment verified.",
    )
    mock_verifier.verify_payment = AsyncMock(return_value=mock_result)

    original_verifier = getattr(app.state, "verifier", None)
    app.state.verifier = mock_verifier

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/agent-inference",
                headers={"X-402-Signature": dummy_sig},
                json={"prompt": "Analyze optimal tick range", "model": "deep-alpha-v1"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"
            assert data["model"] == "deep-alpha-v1"
            assert "action_plan" in data["output"]
            assert data["settlement_receipt"]["signature"] == dummy_sig
    finally:
        if original_verifier:
            app.state.verifier = original_verifier
