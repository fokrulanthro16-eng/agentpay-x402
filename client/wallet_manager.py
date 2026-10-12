"""AgentPay-x402 Solana Wallet Manager.

Handles Solana keypair generation, local persistence in standard Solana CLI format,
balance inquiries, and automated Devnet airdrop requests for autonomous agents.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Union

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.pubkey import Pubkey

logger = logging.getLogger("agentpay.wallet")


class SolanaWalletManager:
    """Manages agent Solana keypair, on-disk storage, balances, and Devnet airdrops."""

    def __init__(
        self,
        keypair_path: Union[str, Path] = "agent_keypair.json",
        rpc_url: str = "https://api.devnet.solana.com",
    ):
        self.keypair_path = Path(keypair_path)
        self.rpc_url = rpc_url
        self.keypair = self._load_or_create_keypair()

    def _load_or_create_keypair(self) -> Keypair:
        """Load keypair from file or generate a new one and persist it."""
        if self.keypair_path.exists():
            try:
                with open(self.keypair_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    kp = Keypair.from_bytes(bytes(data))
                    logger.info(
                        f"Loaded existing agent keypair from {self.keypair_path} (pubkey: {kp.pubkey()})"
                    )
                    return kp
            except Exception as e:
                logger.warning(
                    f"Failed to load keypair from {self.keypair_path} ({e}). Generating new keypair."
                )

        # Generate fresh keypair
        kp = Keypair()
        try:
            self.keypair_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.keypair_path, "w", encoding="utf-8") as f:
                json.dump(list(bytes(kp)), f)
            logger.info(
                f"Generated and saved new agent keypair to {self.keypair_path} (pubkey: {kp.pubkey()})"
            )
        except Exception as e:
            logger.warning(f"Could not persist agent keypair to {self.keypair_path}: {e}")
        return kp

    @property
    def pubkey(self) -> Pubkey:
        """Return agent public key."""
        return self.keypair.pubkey()

    @property
    def pubkey_str(self) -> str:
        """Return agent public key as base58 string."""
        return str(self.keypair.pubkey())

    async def get_balance(self, client: Optional[AsyncClient] = None) -> int:
        """Fetch current balance in lamports."""
        rpc = client or AsyncClient(self.rpc_url)
        should_close = client is None
        try:
            resp = await rpc.get_balance(self.pubkey, commitment=Confirmed)
            if resp and resp.value is not None:
                return resp.value
            return 0
        finally:
            if should_close:
                await rpc.close()

    async def get_balance_sol(self, client: Optional[AsyncClient] = None) -> float:
        """Fetch current balance in SOL."""
        lamports = await self.get_balance(client)
        return lamports / 1_000_000_000

    async def request_airdrop_if_needed(
        self,
        min_sol: float = 0.05,
        airdrop_sol: float = 1.0,
        client: Optional[AsyncClient] = None,
    ) -> bool:
        """Automated airdrop request on Devnet if balance is below threshold.

        Handles faucet rate-limiting gracefully and logs instructions.

        Returns:
            True if balance is sufficient (either already was or after airdrop),
            False if balance remains insufficient due to faucet throttling.
        """
        current_balance_sol = await self.get_balance_sol(client)
        logger.info(
            f"Agent balance check: {current_balance_sol:.6f} SOL (pubkey: {self.pubkey_str})"
        )

        if current_balance_sol >= min_sol:
            logger.info(
                f"Sufficient balance available ({current_balance_sol:.6f} SOL >= {min_sol} SOL threshold)."
            )
            return True

        logger.info(
            f"Balance {current_balance_sol:.6f} SOL is below {min_sol} SOL threshold. "
            f"Requesting {airdrop_sol} SOL airdrop on Devnet..."
        )

        rpc = client or AsyncClient(self.rpc_url)
        should_close = client is None
        lamports_to_request = int(airdrop_sol * 1_000_000_000)

        try:
            airdrop_resp = await rpc.request_airdrop(
                self.pubkey,
                lamports_to_request,
                commitment=Confirmed,
            )
            sig = airdrop_resp.value
            logger.info(
                f"Airdrop requested successfully (sig: {sig}). Awaiting confirmation..."
            )

            # Await confirmation
            await rpc.confirm_transaction(sig, commitment=Confirmed)
            new_balance = await self.get_balance_sol(rpc)
            logger.info(
                f"Airdrop confirmed! Updated balance: {new_balance:.6f} SOL."
            )
            return True

        except Exception as e:
            logger.warning(
                f"Devnet airdrop faucet failed: {e}\n"
                f"----------------------------------------------------------------------\n"
                f"[NOTICE] Solana Devnet public faucet is often rate-limited.\n"
                f"To fund this autonomous agent manually, run:\n"
                f"  solana airdrop {airdrop_sol} {self.pubkey_str} --url devnet\n"
                f"Or use the web faucet at: https://faucet.solana.com\n"
                f"----------------------------------------------------------------------"
            )
            return current_balance_sol > 0
        finally:
            if should_close:
                await rpc.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def _test():
        mgr = SolanaWalletManager()
        print(f"Agent Pubkey: {mgr.pubkey_str}")
        bal = await mgr.get_balance_sol()
        print(f"Current Balance: {bal:.6f} SOL")
        await mgr.request_airdrop_if_needed(min_sol=0.05, airdrop_sol=0.5)

    asyncio.run(_test())
