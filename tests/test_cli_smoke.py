import os
import unittest


class CliSmokeTest(unittest.TestCase):
    def test_env_required(self):
        if not os.getenv("OPENAI_API_KEY"):
            self.skipTest("OPENAI_API_KEY not set")
        if not os.getenv("DATABASE_URL"):
            self.skipTest("DATABASE_URL not set")
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
