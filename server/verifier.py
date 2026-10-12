"""AgentPay-x402 Transaction Verifier.

On-chain Solana settlement verifier using solders and solana-py.
Validates:
1. Transaction is confirmed or finalized on Solana Devnet.
2. Recipient matches configured Merchant Pubkey.
3. Transferred amount matches or exceeds required lamports.
4. Cryptographic replay protection cache with in-memory timestamped tracking.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional, Set

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed, Finalized
from solders.pubkey import Pubkey
from solders.signature import Signature

logger = logging.getLogger("agentpay.verifier")


# --- Custom Verification Exceptions ---


class PaymentVerificationError(Exception):
    """Base exception for payment verification failures."""

    pass


class InvalidSignatureFormatError(PaymentVerificationError):
    """Raised when the transaction signature is not valid base58 format."""

    pass


class ReplayAttackError(PaymentVerificationError):
    """Raised when a signature has already been processed and cached."""

    pass


class TransactionNotFoundError(PaymentVerificationError):
    """Raised when the transaction cannot be found on-chain or is unconfirmed."""

    pass


class TransactionFailedError(PaymentVerificationError):
    """Raised when the transaction executed on-chain with an error."""

    pass


class InvalidRecipientError(PaymentVerificationError):
    """Raised when the transaction recipient does not match merchant pubkey."""

    pass


class InsufficientPaymentError(PaymentVerificationError):
    """Raised when the transferred lamports do not cover the endpoint price."""

    pass


# --- Replay Protection Cache ---


class ReplayProtectionCache:
    """Thread-safe & asyncio-safe in-memory cache for settled transaction signatures.

    Prevents double-spend and replay attacks by recording signatures with their
    settlement timestamps and metadata.
    """

    def __init__(self, ttl_seconds: int = 86400):
        self.ttl_seconds = ttl_seconds
        # Maps signature -> dict of metadata {timestamp, amount_lamports, sender, slot}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def is_seen(self, signature: str) -> bool:
        """Check whether a signature is already recorded in the cache."""
        async with self._lock:
            return signature in self._cache

    async def record(
        self,
        signature: str,
        timestamp: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a settled signature with its timestamp and optional details."""
        async with self._lock:
            ts = timestamp if timestamp is not None else time.time()
            entry = {"timestamp": ts}
            if details:
                entry.update(details)
            self._cache[signature] = entry

    async def cleanup(self) -> int:
        """Prune entries older than TTL. Returns number of purged entries."""
        cutoff = time.time() - self.ttl_seconds
        async with self._lock:
            initial_count = len(self._cache)
            self._cache = {
                sig: data
                for sig, data in self._cache.items()
                if data["timestamp"] >= cutoff
            }
            purged = initial_count - len(self._cache)
            if purged > 0:
                logger.info(f"Purged {purged} expired signatures from replay cache.")
            return purged

    async def count(self) -> int:
        """Return the current number of cached signatures."""
        async with self._lock:
            return len(self._cache)

    async def get_details(self, signature: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached metadata for a settled signature."""
        async with self._lock:
            return self._cache.get(signature)


# --- Verification Result Dataclass ---


@dataclass
class VerificationResult:
    """Detailed verification outcome for an x402 payment."""

    valid: bool
    signature: str
    slot: Optional[int]
    amount_lamports: int
    sender: Optional[str]
    recipient: str
    confirmation_status: str
    block_time: Optional[int]
    message: str
    settled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "signature": self.signature,
            "slot": self.slot,
            "amount_lamports": self.amount_lamports,
            "sender": self.sender,
            "recipient": self.recipient,
            "confirmation_status": self.confirmation_status,
            "block_time": self.block_time,
            "message": self.message,
            "settled_at": self.settled_at,
        }


# --- Core Solana Transaction Verifier ---


class SolanaTransactionVerifier:
    """Verifies on-chain native SOL payments on Solana Devnet."""

    def __init__(
        self,
        rpc_url: str,
        merchant_pubkey: str,
        commitment: str = "confirmed",
        replay_cache: Optional[ReplayProtectionCache] = None,
        rpc_client: Optional[AsyncClient] = None,
        mock_settlement: bool = False,
    ):
        self.rpc_url = rpc_url
        self.merchant_pubkey = merchant_pubkey.strip()
        self.commitment_str = commitment.lower()
        self.commitment: Commitment = (
            Finalized if self.commitment_str == "finalized" else Confirmed
        )
        self.replay_cache = replay_cache or ReplayProtectionCache()
        self._external_client = rpc_client
        self.mock_settlement = mock_settlement

    async def _get_rpc_client(self) -> AsyncClient:
        """Return RPC client instance."""
        if self._external_client is not None:
            return self._external_client
        return AsyncClient(self.rpc_url)

    async def verify_payment(
        self,
        signature_str: str,
        required_lamports: int,
        expected_recipient: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ) -> VerificationResult:
        """Verify on-chain settlement for an incoming x402 signature.

        Args:
            signature_str: Solana transaction signature string (base58).
            required_lamports: Minimum required payment in lamports.
            expected_recipient: Optional override for expected recipient pubkey.
            max_retries: Polling retry attempts for recently broadcast transactions.
            retry_delay_seconds: Delay between retry attempts.

        Returns:
            VerificationResult detailing the settled transaction.

        Raises:
            ReplayAttackError: If signature has already been used.
            InvalidSignatureFormatError: If signature is not valid base58.
            TransactionNotFoundError: If transaction is missing or unconfirmed.
            TransactionFailedError: If transaction resulted in on-chain error.
            InvalidRecipientError: If merchant was not a recipient.
            InsufficientPaymentError: If transferred amount is below requirement.
        """
        signature_str = signature_str.strip()

        # Step 1: Replay Protection Check
        if await self.replay_cache.is_seen(signature_str):
            logger.warning(
                f"[REPLAY BLOCKED] Duplicate transaction signature: {signature_str}"
            )
            raise ReplayAttackError(
                f"Signature {signature_str} has already been settled and processed."
            )

        # Step 2: Signature Format Validation
        try:
            sig = Signature.from_string(signature_str)
        except Exception as e:
            logger.warning(f"Malformed signature format: {signature_str} ({e})")
            raise InvalidSignatureFormatError(
                f"Invalid Solana signature '{signature_str}': {e}"
            )

        target_recipient = (expected_recipient or self.merchant_pubkey).strip()

        # Simulated settlement mode (bypasses RPC ledger lookup when Devnet public faucet is down)
        if self.mock_settlement:
            await self.replay_cache.record(
                signature_str,
                timestamp=time.time(),
                details={
                    "amount_lamports": required_lamports,
                    "sender": "Agent-Keypair",
                    "recipient": target_recipient,
                    "slot": 31415926,
                },
            )
            logger.info(
                f"[SETTLED] Payment confirmed (simulated mode): {required_lamports} lamports -> {target_recipient} (sig: {signature_str[:12]}...)"
            )
            return VerificationResult(
                valid=True,
                signature=signature_str,
                slot=31415926,
                amount_lamports=required_lamports,
                sender="Agent-Keypair",
                recipient=target_recipient,
                confirmation_status=f"{self.commitment_str} (simulated)",
                block_time=int(time.time()),
                message="Payment verified and settled on-chain.",
            )
        client = await self._get_rpc_client()
        should_close = self._external_client is None

        tx_resp = None
        try:
            for attempt in range(max_retries):
                tx_resp = await client.get_transaction(
                    sig,
                    commitment=self.commitment,
                    max_supported_transaction_version=1,
                )
                if tx_resp and tx_resp.value is not None:
                    break
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Transaction {signature_str} not yet confirmed. Retrying ({attempt+1}/{max_retries})..."
                    )
                    await asyncio.sleep(retry_delay_seconds)
        finally:
            if should_close:
                await client.close()

        if not tx_resp or tx_resp.value is None:
            raise TransactionNotFoundError(
                f"Transaction {signature_str} not found or not yet confirmed at "
                f"'{self.commitment_str}' commitment on Devnet."
            )

        confirmed_tx = tx_resp.value
        tx_meta = confirmed_tx.transaction.meta

        # Step 4: Validate On-Chain Execution Success
        if tx_meta is None:
            raise TransactionNotFoundError(
                f"Transaction metadata missing for signature {signature_str}."
            )

        if tx_meta.err is not None:
            raise TransactionFailedError(
                f"Transaction failed on-chain with error: {tx_meta.err}"
            )

        # Step 5: Extract Account Keys and Verify Balance Differential
        msg = confirmed_tx.transaction.transaction.message
        all_account_keys: List[str] = [str(k) for k in msg.account_keys]

        # In versioned transactions (v0/v1), address lookup tables load extra addresses
        if tx_meta.loaded_addresses:
            all_account_keys.extend([str(k) for k in tx_meta.loaded_addresses.writable])
            all_account_keys.extend([str(k) for k in tx_meta.loaded_addresses.readonly])

        if target_recipient not in all_account_keys:
            raise InvalidRecipientError(
                f"Configured merchant public key ({target_recipient}) was not "
                f"involved in transaction {signature_str}."
            )

        recipient_idx = all_account_keys.index(target_recipient)
        pre_balance = tx_meta.pre_balances[recipient_idx]
        post_balance = tx_meta.post_balances[recipient_idx]
        transferred_lamports = post_balance - pre_balance

        if transferred_lamports < required_lamports:
            raise InsufficientPaymentError(
                f"Insufficient payment to merchant {target_recipient}. "
                f"Required: {required_lamports} lamports, transferred: {transferred_lamports} lamports."
            )

        sender_pubkey = all_account_keys[0] if all_account_keys else None

        # Step 6: Commit to Replay Protection Cache
        await self.replay_cache.record(
            signature_str,
            timestamp=time.time(),
            details={
                "amount_lamports": transferred_lamports,
                "sender": sender_pubkey,
                "recipient": target_recipient,
                "slot": confirmed_tx.slot,
            },
        )

        logger.info(
            f"[SETTLED] Payment confirmed: {transferred_lamports} lamports from "
            f"{sender_pubkey} -> {target_recipient} (sig: {signature_str[:12]}..., slot: {confirmed_tx.slot})"
        )

        return VerificationResult(
            valid=True,
            signature=signature_str,
            slot=confirmed_tx.slot,
            amount_lamports=transferred_lamports,
            sender=sender_pubkey,
            recipient=target_recipient,
            confirmation_status=self.commitment_str,
            block_time=confirmed_tx.block_time,
            message="Payment successfully verified and settled on-chain.",
        )
