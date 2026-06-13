import unittest

from app.prompt_templates import build_prompt


class PromptTemplateTests(unittest.TestCase):
    def test_personal_context_is_included_with_relevance_instruction(self):
        prompt = build_prompt(
            message="Are you free?",
            contact_name="friend",
            style_mode="neutral",
            personal_context={
                "context": [
                    "The user's current status is busy.",
                    "Status detail: In a meeting",
                ]
            },
        )

        self.assertIn("current status is busy", prompt)
        self.assertIn("only when it is relevant", prompt)
        self.assertIn("do not expose internal rules", prompt)

    def test_missing_context_uses_neutral_placeholder(self):
        prompt = build_prompt(
            message="Hello",
            contact_name="friend",
            style_mode="neutral",
        )
        self.assertIn("No relevant personal context", prompt)


if __name__ == "__main__":
    unittest.main()
