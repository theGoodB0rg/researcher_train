from typing import List, Dict, Any
from openai import OpenAI
from src.utils.console import colored
from src.config import get_settings

class Agent:
    def __init__(self, name: str, role: str, system_prompt: str, color: str = "white"):
        settings = get_settings()
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.color = color
        self.memory: List[Dict[str, str]] = []
        
        # Initialize OpenAI
        if settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.model_name = settings.openai_model
        else:
            self.client = None
            print(colored(f"[{self.name}] WARNING: No OpenAI API Key found. Running in Mock Mode.", "red"))

    def speak(self, message: str) -> None:
        """Prints the agent's message to the console with their specific color."""
        print(colored(f"\n[{self.name} - {self.role}]:", self.color, attrs=['bold']))
        print(colored(message, self.color))
        self.memory.append({"role": "assistant", "content": message})

    def process(self, input_data: str, context: List[Dict[str, str]] = None, system_overrides: str = None) -> str:
        """
        Processes input and returns a response.
        If API key is present, calls LLM. Otherwise, returns a mock response.
        """
        system_content = self.system_prompt
        if system_overrides:
            system_content += f"\n\nPROJECT SETTINGS / CONSTRAINTS:\n{system_overrides}"

        messages = [
            {"role": "system", "content": system_content}
        ]

        if context:
             # Basic context injection
             for msg in context:
                 messages.append({"role": "user", "content": f"{msg['role']}: {msg['content']}"})
        
        messages.append({"role": "user", "content": input_data})

        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages
                )
                reply = response.choices[0].message.content
            except Exception as e:
                reply = f"Error generating response: {str(e)}"
        else:
            # Mock behavior for testing structure without valid API key
            reply = f"[MOCK OUTPUT from {self.name}] I have analyzed '{input_data[:20]}...' based on my role as {self.role}."

        self.speak(reply)
        return reply
