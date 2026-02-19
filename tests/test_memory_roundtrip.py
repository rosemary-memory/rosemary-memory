import os
import unittest
import asyncio

from rosemary_memory.storage.age import AgeClient
from rosemary_memory.memory.store import GraphStore


class MemoryRoundtripTest(unittest.TestCase):
    def setUp(self):
        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            self.skipTest("DATABASE_URL not set")

    def test_roundtrip(self):
        async def _run():
            age = AgeClient(self.database_url)
            store = GraphStore(age, "gmemory_test")
            await store.ensure_graph()
            await store.insert_cluster_summary_detail(
                cluster_label="testing",
                summary_text="unit test summary",
                detail_text="unit test detail",
                source="test",
            )
            results = await store.retrieve("unit test", 5)
            await age.close()
            return results

        results = asyncio.run(_run())
        self.assertTrue(results)


if __name__ == "__main__":
    unittest.main()
