import requests
import settings
import os 
import importlib
import json
import platform
import textwrap
import traceback

class Conversation:
    """DODA conversation manager for Ollama (pure requests)."""

    def __init__(self) -> None:
        self.llm_model = settings.OLLAMA_MODEL
        self.base_url = settings.OLLAMA_BASE_URL.rstrip('/')
        
        self.messages: list[dict] = [
            {"role": "system", "content": self.generate_system_content().replace('\n', '').strip() },
        ]
        self.load_functions()
        self.pending_confirmation = False
        self.last_pending_message = None

        if not os.path.exists('./workspace'):
            os.makedirs('./workspace')

    def generate_system_content(self):
        template_path = os.path.join(os.path.dirname(__file__), 'internal', 'custom_instructions.txt')
        try:
            with open(template_path, 'r') as file:
                template = file.read()
            
            content = template.format(
                platform=platform.platform(),
                cwd=os.getcwd(),
                shell=os.environ.get('SHELL', '/bin/sh'),
                path=os.environ.get('PATH', ''),
                user=os.environ.get('USER', 'developer')
            )
            return textwrap.dedent(content)
        except Exception as e:
            print(f"Error loading system content template: {e}")
            return "You are DODA, a developer assistant. Use tools when needed."

    def load_functions(self):
        """Load function configurations from JSON and dynamically import functions."""
        try:
            functions_path = os.path.join(os.path.dirname(__file__), 'internal', 'functions.json')
            with open(functions_path, 'r') as file:
                self.tools = json.load(file)

            self.available_functions = {}
            self.functions_confirmation_required = []
            for tool in self.tools:
                function_name = tool['function']['name']
                if os.environ.get('FUNCTION_CONFIRMATION_REQUIRED') != "false":
                    self.functions_confirmation_required.append(function_name)
                module_name = f"internal.functions.{function_name}"
                function_module = importlib.import_module(module_name)
                self.available_functions[function_name] = getattr(function_module, function_name)

        except Exception as e:
            print(f"Error loading functions: {e}")

    async def handle_confirmation(self, tool_call, response_message):
        """Handle the creation of a confirmation dialog."""
        function_name = tool_call.get('function', {}).get('name')
        arguments = tool_call.get('function', {}).get('arguments')
        
        confirmation_dialog = f"🔧 I'm about to run {function_name}, args: {arguments}\n"
        confirmation_dialog += "To confirm, reply with: 'y'\n"
        confirmation_dialog += "To cancel, reply with: 'n'"
        self.pending_confirmation = True
        self.last_pending_message = response_message
        return confirmation_dialog

    async def process_tool_calls(self, tool_calls):
        """Process tool calls and append responses to self.messages."""
        function_response = None
        for tool_call in tool_calls:
            function_data = tool_call.get('function', {})
            function_name = function_data.get('name')
            function_to_call = self.available_functions[function_name]
            
            try:
                function_args = json.loads(function_data.get('arguments', '{}'))
                if not function_args:
                    function_response = function_to_call()
                else:
                    function_response = function_to_call(**function_args)
            except Exception as e:
                print(f"💥 process_tool_calls error: {str(e)}")
                self.messages.pop() # rollback tool call
                return False
            
            self.messages.append({
                "tool_call_id": tool_call.get('id'),
                "role": "tool",
                "name": function_name,
                "content": str(function_response),
            })
        return function_response

    async def generate_response(self):
        """Generate and handle the model's response (follow-up after tool)."""
        payload = {
            "model": self.llm_model,
            "messages": self.messages
        }
        
        response = requests.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        
        response_message = data['choices'][0]['message']
        self.messages.append({"role": "assistant", "content": response_message.get('content')})
        return response_message.get('content')

    async def send(self, message: str) -> dict:
        """Send a message to Ollama and handle choices."""
        collapsible_data = None
        if self.pending_confirmation:
            self.pending_confirmation = False
            if message.lower() == "y":
                tool_calls = self.last_pending_message.get('tool_calls', [])
                tool_call_status = await self.process_tool_calls(tool_calls)
                if not tool_call_status:
                    response_content = "Sorry, I ran into an error while processing the tool call."
                else:
                    response_content = await self.generate_response()
            else:
                self.messages.pop()
                response_content = "OK, what would you like to do instead?"
        else:
            self.messages.append({"role": "user", "content": message})
            
            payload = {
                "model": self.llm_model,
                "messages": self.messages,
                "tools": self.tools,
                "tool_choice": "auto"
            }
            
            try:
                print(f"Sending request to {self.base_url}/chat/completions with model {self.llm_model}")
                response = requests.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                # Retry without tools if failure
                print(f"Error calling Ollama with tools: {e}. Retrying without tools.")
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                response = requests.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()

            response_message = data['choices'][0]['message']

            if response_message.get('tool_calls'):
                self.messages.append({
                    "role": "assistant", 
                    "content": response_message.get('content'), 
                    "tool_calls": response_message.get('tool_calls')
                })
                
                # Check confirmation for first tool call
                tool_call = response_message['tool_calls'][0]
                function_name = tool_call.get('function', {}).get('name')
                
                if function_name in self.functions_confirmation_required:
                    response_content = await self.handle_confirmation(tool_call, response_message)
                    return { 'response_content': response_content }
                
                tool_call_function_response = await self.process_tool_calls(response_message['tool_calls'])
                if not tool_call_function_response:
                    return { 'response_content': "Sorry, I ran into an error while processing the tool call." }
                
                if isinstance(tool_call_function_response, dict) and tool_call_function_response.get('show_collapsible'):
                    collapsible_data = tool_call_function_response.get('output')
                
                response_content = await self.generate_response()
            else:
                self.messages.append({"role": "assistant", "content": response_message.get('content')})
                response_content = response_message.get('content')
                
        return { 'response_content': response_content, 'collapsible_data': collapsible_data }

    def clear(self) -> None:
        """Clear current conversation."""
        self.messages = [
            {"role": "system", "content": self.generate_system_content().replace('\n', '').strip() },
        ]