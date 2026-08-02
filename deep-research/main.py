from google import genai
from dotenv import load_dotenv
from os import getenv
load_dotenv()
api_key = getenv("GEMINI_API_KEY")


client = genai.Client()

interaction = client.interactions.create(
    model="gemini-3.6-flash",
    input="Explain how AI works in a few words"
)
print(interaction.output_text)
