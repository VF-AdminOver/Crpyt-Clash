from __future__ import annotations

import asyncio
import unittest


class OnlineServerTests(unittest.TestCase):
    def test_security_manager_hash_and_verify(self) -> None:
        try:
            from dnd_cli.server.security import SecurityManager
        except ModuleNotFoundError:
            self.skipTest("server dependencies not installed")
            return

        security = SecurityManager("secret", 30, 14)
        password_hash = security.hash_password("my-password-123")
        self.assertTrue(security.verify_password("my-password-123", password_hash))
        self.assertFalse(security.verify_password("wrong-password", password_hash))

    def test_access_token_decode(self) -> None:
        try:
            from dnd_cli.server.security import SecurityManager
        except ModuleNotFoundError:
            self.skipTest("server dependencies not installed")
            return

        security = SecurityManager("secret", 30, 14)
        tokens = security.mint_tokens("account-123")
        payload = security.decode_access_token(tokens.access_token)
        self.assertEqual(payload.get("sub"), "account-123")
        self.assertEqual(payload.get("typ"), "access")

    def test_hub_state_queue(self) -> None:
        try:
            from dnd_cli.server.hub import HubState
        except ModuleNotFoundError:
            self.skipTest("server dependencies not installed")
            return

        async def run_test() -> None:
            hub = HubState(presence_limit=50)
            party = await hub.create_party("char-1")
            self.assertEqual(party.leader_character_id, "char-1")
            position = await hub.join_queue(party.party_id, "standard")
            self.assertEqual(position, 1)
            popped = await hub.pop_match_party("standard")
            self.assertEqual(popped, party.party_id)

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
