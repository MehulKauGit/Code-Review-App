from groq import Groq
import os

client = Groq(api_key=os.environ["GROQ_API_KEY"])

models = client.models.list()

for model in models.data:
    print(model.id)


model = client.models.retrieve("llama-3.3-70b-versatile")
print(model)